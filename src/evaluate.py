"""
Phase 4: LLM-powered critical self-evaluation.

Computes diagnostic quantities algorithmically (confidence intervals,
FFT error, synthetic-data circularity metric), then passes them to
Claude to generate a rigorous, genuinely critical self-evaluation
suitable for inclusion in the final report.
"""

import json
import math
import os
import statistics
import sys

import anthropic

sys.path.insert(0, os.path.dirname(__file__))

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

SYSTEM_PROMPT = """\
You are writing a critical self-evaluation of an AI-assisted security analysis \
for inclusion in a graduate course final report.

Your evaluation must be:
- Honest and specific — cite computed numbers, not vague concerns
- Structured under the three required headings
- Genuinely critical where the analysis is weak (not falsely modest where it is sound)
- Written in the third person ("the analysis", "the agent", "the pipeline")
- Free of padding or generic statements about AI limitations

The section will be pasted verbatim into the report under \
"Limitations of AI-Assisted Analysis."\
"""

EVALUATION_INSTRUCTIONS = """\
Using the empirical data, diagnostic metrics, and reports above, write a \
structured critical evaluation with exactly these three sections:

### 1. What the Analysis Did Well
Identify 3–4 specific strengths. For each, explain WHY it is genuinely sound \
rather than just describing what was done. Reference specific numbers.

### 2. What the Analysis Did Poorly or Uncertainly
Identify at least 5 specific weaknesses. For each:
- State the specific flaw with a concrete example or number
- Explain why it matters for the validity of the findings
- Do not soften or qualify unnecessarily — if something is genuinely wrong, say so

Must cover: circular synthetic data, sample size adequacy (with CI), FFT \
methodology failure, unvalidated mechanistic claims in threat scenarios, \
missing ground truth for disruption window measurement.

### 3. Limitations of This Approach
Address what a rigorous academic version would require:
- Data requirements (quantity, quality, sources)
- Experimental validation for attack feasibility claims
- Why synthetic-data findings cannot be published as empirical results
- Peer review requirements for novel threat claims

End with a one-paragraph summary starting "Summary:" that states plainly \
what this work is and is not — a research proposal, not validated findings.\
"""


def load(name: str) -> dict:
    with open(os.path.join(REPORTS_DIR, name)) as f:
        return json.load(f)


def section(title: str) -> None:
    print(f"\n{'='*70}\n  {title}\n{'='*70}\n")


def t_ci_95(mean: float, std: float, n: int) -> float:
    t_table = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57,
               10: 2.23, 20: 2.09, 30: 2.04, 40: 2.02, 60: 2.00}
    df = n - 1
    t = min(t_table.items(), key=lambda kv: abs(kv[0] - df))[1]
    return t * std / math.sqrt(n)


def cv_ci_95(cv: float, n: int) -> tuple[float, float]:
    df = n - 1
    chi2_lo = df * (1 - math.sqrt(2.0 / df) * 1.96) ** 2
    chi2_hi = df * (1 + math.sqrt(2.0 / df) * 1.96) ** 2
    chi2_lo = max(chi2_lo, 0.001)
    return (round(cv * math.sqrt(df / chi2_hi), 4),
            round(cv * math.sqrt(df / chi2_lo), 4))


def compute_diagnostics(p1: dict, p2: dict) -> dict:
    ia = p2["interval_analysis"]
    dw = p2["disruption_window"]
    fft = p2["fft_periodicity"]
    ap = p2["attack_probability"]
    n = ia["n_intervals"]
    mean = ia["mean_s"]
    std = ia["std_s"]
    cv = ia["cv"]
    mean_ci = t_ci_95(mean, std, n)
    cv_lo, cv_hi = cv_ci_95(cv, n)
    se_cv = cv / math.sqrt(2 * n)
    z_poisson = (1.0 - cv) / se_cv
    # Circularity: ratio of measured std to generator's jitter (σ=2.5s)
    synth_jitter = 2.5
    std_ratio = std / synth_jitter
    # FFT: how far the dominant period is from expected
    expected_period = mean
    observed_period = fft["dominant_period_s"] or 0.0
    fft_error_pct = abs(observed_period - expected_period) / expected_period * 100
    return {
        "n_intervals": n,
        "mean_s": mean,
        "std_s": std,
        "cv": cv,
        "mean_ci_95_halfwidth": round(mean_ci, 3),
        "cv_ci_95": [cv_lo, cv_hi],
        "cv_predictability_threshold": 0.20,
        "z_poisson_rejection": round(z_poisson, 2),
        "fft_dominant_period_s": observed_period,
        "fft_expected_period_s": round(expected_period, 2),
        "fft_error_pct": round(fft_error_pct, 1),
        "fft_band_power_pct": round(fft["band_power_fraction"] * 100, 2),
        "synth_std_recovery_ratio": round(std_ratio, 3),
        "disruption_window_mean_s": dw["mean_disruption_window_s"],
        "exploit_pct_of_cycle": round(dw["mean_disruption_window_s"] / mean * 100, 3),
        "p_hit_per_prediction": ap["p_hit_per_prediction"],
        "data_source": p1["source"],
        "note_circularity": (
            "Synthetic data was generated from the same Starlink Gen1 parameters "
            "the analysis then 'confirms'. The std recovery ratio (measured_std / "
            "generator_jitter) is {:.3f} — close to 1.0 indicates circular validation."
            .format(std_ratio)
        ),
        "note_cv_classification": (
            "The 'highly predictable' label requires CV < 0.20. "
            "The 95% CI for CV is [{:.3f}, {:.3f}], which straddles this threshold."
            .format(cv_lo, cv_hi)
        ),
        "note_fft_failure": (
            "FFT returned dominant period {:.2f}s vs. expected ~{:.1f}s ({:.0f}% error). "
            "Likely cause: 10s detrending window attenuates frequencies near 1/15 Hz. "
            "This was not corrected — interval-level statistics were substituted without "
            "explaining the discrepancy.".format(
                observed_period, expected_period, fft_error_pct)
        ),
    }


def run_evaluation() -> str:
    section("Phase 4: Critical Self-Evaluation  [Claude API]")

    client = anthropic.Anthropic()

    p1 = load("handoff_detection.json")
    p2 = load("predictability_analysis.json")

    print("Computing diagnostics (algorithmic)...\n")
    diag = compute_diagnostics(p1, p2)

    print(f"  n_intervals            : {diag['n_intervals']}")
    print(f"  mean 95% CI ±          : {diag['mean_ci_95_halfwidth']} s")
    print(f"  CV 95% CI              : {diag['cv_ci_95']}")
    print(f"  Poisson z-rejection    : {diag['z_poisson_rejection']}σ")
    print(f"  FFT error              : {diag['fft_error_pct']:.0f}% "
          f"({diag['fft_dominant_period_s']:.2f}s vs {diag['fft_expected_period_s']:.1f}s)")
    print(f"  Synth std recovery     : {diag['synth_std_recovery_ratio']:.3f}")
    print()

    # Build context: diagnostics + both JSON reports
    context = json.dumps({
        "diagnostics": diag,
        "handoff_detection_summary": {
            "source": p1["source"],
            "n_samples": p1["n_samples"],
            "duration_s": p1["duration_s"],
            "n_handoffs": p1["n_handoffs"],
            "interval_stats": p2["interval_analysis"],
        },
        "predictability_summary": {
            "distribution_model": p2["distribution_model"]["model"],
            "disruption_window": p2["disruption_window"],
            "attack_probability": p2["attack_probability"],
            "fft_result": p2["fft_periodicity"],
        },
    }, indent=2)

    print("Sending diagnostics to Claude for critical evaluation (streaming)...\n")
    print("-" * 70)

    full_text = ""

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=4096,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": "high"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"ANALYSIS DATA AND DIAGNOSTICS:\n{context}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": EVALUATION_INSTRUCTIONS,
                    },
                ],
            }
        ],
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "thinking":
                    print("\n[Reasoning", end="", flush=True)
                elif event.content_block.type == "text" and full_text == "":
                    print()
            elif event.type == "content_block_delta":
                if event.delta.type == "thinking_delta":
                    print(".", end="", flush=True)
                elif event.delta.type == "text_delta":
                    print(event.delta.text, end="", flush=True)
                    full_text += event.delta.text

        final = stream.get_final_message()

    print("\n" + "-" * 70)

    cache_info = (
        f"  cache_read={final.usage.cache_read_input_tokens or 0}  "
        f"cache_write={final.usage.cache_creation_input_tokens or 0}  "
        f"uncached={final.usage.input_tokens}"
    )
    print(f"\nToken usage: {cache_info}")

    # Prepend the section heading
    report_text = "## Limitations of AI-Assisted Analysis\n\n" + full_text

    out_path = os.path.join(REPORTS_DIR, "self_evaluation.md")
    with open(out_path, "w") as f:
        f.write(report_text)
    print(f"Report written to: {out_path}")

    return report_text


if __name__ == "__main__":
    run_evaluation()
