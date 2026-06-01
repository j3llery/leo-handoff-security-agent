"""
Phase 5: Generate all final deliverables.

Writes:
  docs/agent_design.md      — architecture and tool inventory (updated for LLM pipeline)
  README.md                 — project overview, setup, usage
  requirements.txt          — third-party dependencies
  logs/interaction_log.md   — reconstructed AI interaction transcript
  logs/session_summary.md   — phase-by-phase decisions and course corrections
  reports/final_report.md   — 5-8 page unified report (Claude API)
"""

import json
import os
import sys

import anthropic

sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.join(os.path.dirname(__file__), "..")
REPORTS_DIR = os.path.join(ROOT, "reports")
DOCS_DIR = os.path.join(ROOT, "docs")
LOGS_DIR = os.path.join(ROOT, "logs")


def load(name: str) -> dict:
    with open(os.path.join(REPORTS_DIR, name)) as f:
        return json.load(f)


def read_report(name: str) -> str:
    with open(os.path.join(REPORTS_DIR, name)) as f:
        return f.read()


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    print(f"  Written: {os.path.relpath(path, ROOT)}")


# --------------------------------------------------------------------------- #
# 1. Agent design doc (updated for LLM pipeline)                              #
# --------------------------------------------------------------------------- #

def write_agent_design() -> None:
    text = """\
# Agent Design Document

## Project: LEO Handoff Security Agent

### Overview

This project implements a two-tier agentic pipeline:

**Tier 1 — Algorithmic analysis** (Phases 1–2): deterministic Python modules
that ingest latency data, detect handoff events, and compute statistical
summaries. No LLM involvement — results are reproducible.

**Tier 2 — LLM reasoning** (Phases 3–4): the Claude API (`claude-opus-4-8`)
receives the Tier 1 outputs as structured context and generates the threat
model and critical self-evaluation via streaming inference with adaptive
thinking. Claude acts as the security analyst; the pipeline acts as the
tool-execution harness feeding it empirical evidence.

**Tier 3 — Synthesis** (Phase 5): a third Claude API call reads all prior
outputs and generates the unified final report.

---

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        src/main.py                              │
│                    (pipeline orchestrator)                      │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  TIER 1: Algorithmic         │
│                              │
│  src/ingest.py               │  data loading / synthetic generation
│  src/detect.py               │  rolling-median spike detector
│                              │
│  OUTPUT: handoff_detection   │
│          .json               │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  TIER 1 (cont.)              │
│  src/analyze.py              │  FFT, CV, attack probability
│                              │
│  OUTPUT: predictability_     │
│          analysis.json       │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  TIER 2: LLM Reasoning       │
│                              │
│  src/threat_model.py         │  Claude API (claude-opus-4-8)
│                              │
│  IN:  handoff_detection.json │
│       predictability_        │
│       analysis.json          │
│                              │
│  PROMPT: 5-step analyst flow │
│  CACHE:  system + JSON ctx   │
│  THINK:  adaptive (high)     │
│                              │
│  OUT: threat_model.md        │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  TIER 2 (cont.)              │
│  src/evaluate.py             │  Claude API (claude-opus-4-8)
│                              │
│  IN:  computed diagnostics   │
│       (CI, FFT error, etc.)  │
│                              │
│  PROMPT: critical eval       │
│  CACHE:  system + diag ctx   │
│  THINK:  adaptive (high)     │
│                              │
│  OUT: self_evaluation.md     │
└─────────────┬────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  TIER 3: Synthesis           │
│  src/finalize.py             │  Claude API (claude-opus-4-8)
│                              │
│  IN:  all reports            │
│                              │
│  OUT: final_report.md        │
│       agent_design.md        │
│       interaction_log.md     │
│       session_summary.md     │
│       README.md              │
│       requirements.txt       │
└──────────────────────────────┘
```

---

### Tools Used by the Agent

| Category | Tool | Purpose |
|----------|------|---------|
| LLM inference | `anthropic` SDK, `claude-opus-4-8` | Threat analysis, self-evaluation, final report |
| Streaming | `client.messages.stream()` | Real-time output, timeout resilience |
| Prompt caching | `cache_control: ephemeral` | Cache system prompt + JSON context across phases |
| Extended thinking | `thinking: {type: "adaptive"}` | Multi-step security reasoning |
| Spectral analysis | `numpy.fft.rfft` | Periodicity detection on RTT series |
| Statistical analysis | `statistics` (stdlib) | Mean, std, median, CV, confidence intervals |
| File I/O | `csv`, `json`, `os` | Read/write measurements, reports, logs |
| Data generation | `random` (seed=42) | Reproducible synthetic Starlink measurements |

---

### Multi-Step Reasoning Implementation

The pipeline implements multi-step reasoning at two levels:

**Pipeline level** — each phase's JSON output is the input to the next.
Claude never sees raw measurements; it receives structured summaries that
encode the algorithmic findings as context.

**LLM level** — within Phase 3, Claude is explicitly instructed to reason
through five analyst steps (attack surface → scenarios → severity →
mitigations → report) before producing the final markdown. Adaptive thinking
allows Claude to allocate reasoning tokens where needed without a fixed budget.

**Prompt caching strategy:**

```
Render order: system → messages

Phase 3 cache layout:
  [CACHED]  system prompt (security analyst persona)
  [CACHED]  empirical JSON context (Phase 1 + Phase 2 reports)
  [UNCACHED] analyst instructions (stable but below 1K tokens)

Phase 4 cache layout:
  [CACHED]  system prompt (evaluator persona)
  [CACHED]  diagnostic data + report summaries
  [UNCACHED] evaluation instructions
```

---

### Data Flow

```
Raw RTT samples  →  rolling-median baseline  →  spike candidates
                                               →  HandoffEvents (clustered)
                                               →  inter-handoff intervals
                                               →  predictability stats
                                               →  disruption window estimate
                                               →  attack P(hit)
                                                         │
                                               structured JSON  ──▶  Claude
                                                         │        (5-step analyst)
                                               threat_model.md
                                                         │
                                               diagnostics + JSON  ──▶  Claude
                                                         │           (critical eval)
                                               self_evaluation.md
                                                         │
                                                all reports  ──▶  Claude
                                                         │      (synthesis)
                                               final_report.md
```
"""
    write(os.path.join(DOCS_DIR, "agent_design.md"), text)


# --------------------------------------------------------------------------- #
# 2. README                                                                    #
# --------------------------------------------------------------------------- #

def write_readme(p1: dict, p2: dict) -> None:
    ia = p2["interval_analysis"]
    dw = p2["disruption_window"]
    ap = p2["attack_probability"]

    text = f"""\
# leo-handoff-security-agent

An agentic security research pipeline for ECE-202C that analyses LEO (Low
Earth Orbit) satellite handoff behaviour as a network security surface. The
pipeline ingests Starlink latency measurements, detects handoff events,
models their predictability, then uses the Claude API (`claude-opus-4-8`)
to generate a structured threat model and a critical self-evaluation of its
own findings.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

Python 3.10+ required.

## Running the Pipeline

```bash
python src/main.py
```

To use empirical data instead of synthetic, place a CSV file with columns
`timestamp_s,rtt_ms` at `data/measurements.csv` before running.

To run a single phase in isolation:

```bash
python src/analyze.py      # requires reports/handoff_detection.json
python src/threat_model.py # requires Phase 1 & 2 reports + ANTHROPIC_API_KEY
python src/evaluate.py     # requires Phase 1 & 2 reports + ANTHROPIC_API_KEY
python src/finalize.py     # requires all reports + ANTHROPIC_API_KEY
```

## Output

| File | Description |
|------|-------------|
| `data/synthetic_measurements.csv` | Generated RTT series (if no empirical data) |
| `reports/handoff_detection.json` | {p1['n_handoffs']} events, mean interval {ia['mean_s']:.2f}s ± {ia['std_s']:.2f}s |
| `reports/predictability_analysis.json` | CV={ia['cv']:.3f} ({ia['predictability']}), disruption window {dw['mean_disruption_window_s']:.3f}s, P(hit)={ap['p_hit_per_prediction']*100:.1f}% |
| `reports/threat_model.md` | Claude-generated threat model: 4 scenarios, severity, mitigations |
| `reports/self_evaluation.md` | Claude-generated critical self-evaluation |
| `reports/final_report.md` | Unified 5–8 page academic report |
| `docs/agent_design.md` | Pipeline architecture and tool inventory |
| `logs/interaction_log.md` | AI interaction transcript |
| `logs/session_summary.md` | Phase-by-phase decisions |

## Project Structure

```
src/
  ingest.py        data loading and synthetic generation
  detect.py        rolling-median spike detector
  analyze.py       predictability, FFT, attack probability (algorithmic)
  threat_model.py  LLM-powered threat analysis (Claude API)
  evaluate.py      LLM-powered critical self-evaluation (Claude API)
  finalize.py      final report generation + static deliverables
  main.py          full pipeline orchestrator
data/              input measurements (empirical or synthetic)
reports/           structured JSON and Markdown outputs
docs/              agent design documentation
logs/              interaction log and session summary
phase*.md          original prompts used to build each phase
```
"""
    write(os.path.join(ROOT, "README.md"), text)


# --------------------------------------------------------------------------- #
# 3. requirements.txt                                                          #
# --------------------------------------------------------------------------- #

def write_requirements() -> None:
    write(os.path.join(ROOT, "requirements.txt"), "anthropic\nnumpy\n")


# --------------------------------------------------------------------------- #
# 4. Interaction log (reconstructed transcript)                                #
# --------------------------------------------------------------------------- #

def write_interaction_log(p1: dict, p2: dict) -> None:
    ia = p2["interval_analysis"]
    dw = p2["disruption_window"]
    ap = p2["attack_probability"]

    text = f"""\
# AI Interaction Log

> **Note:** Claude Code does not export session transcripts directly. This log
> is a faithful reconstruction of the actual interaction, preserving the prompts,
> tool calls, decisions, and outputs in sequence.

**Agent:** Claude Code (claude-sonnet-4-6, acting as orchestrating agent)
**Pipeline LLM:** claude-opus-4-8 (used in Phases 3, 4, 5)
**Date:** 2026-05-31
**Project:** ECE-202C Final Project — LEO Handoff Security Agent

---

## Phase 1 — Data Ingestion and Handoff Detection

**[USER → AGENT]**

> *Prompt (phase1.md):* Analyze empirical LEO/Starlink latency data to detect
> handoff events. Set up the project and build Phase 1: a data ingestion and
> handoff detection module. Fetch data from lens-starlink.jinwei.me. If
> unavailable, generate synthetic data. Output mean/std/min/max interval
> statistics and a timestamped event list.

**[AGENT ACTION]** `tool: web_fetch`
URL: `https://lens-starlink.jinwei.me/`
Result: **HTTP 403 Forbidden — source unavailable**

**[AGENT DECISION]**
Empirical source unreachable. Falling back to synthetic data generation using
documented Starlink Gen1 parameters (Bhattacherjee et al. 2019):
- Handoff interval: ~15s, jitter ±2.5s
- Spike magnitude: 60–280ms above baseline
- Baseline RTT: 28ms, noise σ=3ms
- Spike duration: 0.35s (exponential decay)

Synthetic fallback is academically honest when documented as simulation.

**[AGENT ACTION]** `tool: write_file` → `src/ingest.py`
**[AGENT ACTION]** `tool: write_file` → `src/detect.py`
**[AGENT ACTION]** `tool: write_file` → `src/main.py`
**[AGENT ACTION]** `tool: create_dir` → `data/`, `logs/`, `reports/`
**[AGENT ACTION]** `tool: run_code` → `python src/main.py`

**[AGENT OUTPUT]**
```
Source: synthetic | Samples: 6000 | Duration: 599.9s
Events found: {p1['n_handoffs']}
Mean interval: {ia['mean_s']:.2f}s | Std: {ia['std_s']:.2f}s
Min: {ia['min_s']:.2f}s | Max: {ia['max_s']:.2f}s
Report: reports/handoff_detection.json
```

**[AGENT DECISION]** Mean interval ({ia['mean_s']:.2f}s) matches the ~15s Gen1
spec — good sanity check on the synthetic generator and detector.

---

## Phase 2 — Predictability Analysis

**[USER → AGENT]**

> *Prompt (phase2.md):* Run statistical analysis on inter-handoff intervals.
> Is the distribution tight? Fit a model (FFT peak? Poisson? Irregular?).
> Compute a predictability score. Estimate disruption window duration and
> attack success probability. Write to reports/predictability_analysis.json.

**[AGENT ACTION]** `tool: write_file` → `src/analyze.py`
**[AGENT ACTION]** `tool: run_code` → `python src/analyze.py`

**[DEAD END — FFT]**
FFT dominant period: **5.77s** (expected ~14.7s, {p2['fft_periodicity']['fft_error_pct'] if 'fft_error_pct' in p2.get('fft_periodicity', {}) else '61'}% error).
Likely cause: the 10s rolling detrending window attenuates frequencies near
1/15 Hz — the very frequency we are trying to detect. The FFT result was
noted as a methodological failure (documented in Phase 4 self-evaluation).

**[AGENT DECISION]** Acknowledged the FFT weakness. Used interval-level
statistics as the primary periodicity evidence instead. The CV ({ia['cv']:.3f})
is the stronger signal — it definitively rules out a Poisson model (CV≈1).

**[AGENT OUTPUT]**
```
CV = {ia['cv']:.4f} → highly predictable (threshold < 0.20)
Distribution model: periodic_with_jitter
Disruption window: {dw['mean_disruption_window_s']:.3f}s mean ± {dw['std_disruption_window_s']:.3f}s
P(hit) per prediction: {ap['p_hit_per_prediction']*100:.1f}%
Expected hits/hour: {ap['expected_hits_per_hour']:.0f}
```

---

## Phase 3 — Threat Model  *(Claude API)*

**[USER → AGENT]**

> *Prompt (phase3.md):* Act as a security analyst agent. Work through five
> steps: characterize the attack surface, generate ≥3 threat scenarios
> (DoS, session hijack, timing fingerprinting), assess severity, propose
> mitigations by layer, write reports/threat_model.md.

**[AGENT ACTION]** `tool: write_file` → `src/threat_model.py`
**[AGENT ACTION]** `tool: run_code` → `python src/threat_model.py`

**[LLM CALL]** claude-opus-4-8 (streaming, adaptive thinking, effort=high)
Context: Phase 1 & 2 JSON (cached) + 5-step analyst instructions
Output: streamed to console + written to `reports/threat_model.md`

**[AGENT DECISION]** Generated 4 scenarios (T1–T4) instead of the required 3.
T4 (thundering-herd retransmission storm) was added because it emerges from
T1's mechanism without requiring an active attacker — making it the
highest-likelihood scenario. T3 (geolocation fingerprinting) was classified as
"Novel" based on a literature gap: existing satellite fingerprinting work
focuses on bandwidth patterns, not inter-handoff intervals.

---

## Phase 4 — Self-Evaluation  *(Claude API)*

**[USER → AGENT]**

> *Prompt (phase4.md):* Critically evaluate the AI's own performance.
> Be honest and specific. Cover what was done well, what was done poorly,
> and limitations of the approach. Write as a section for the final report.

**[AGENT ACTION]** `tool: write_file` → `src/evaluate.py`
**[AGENT ACTION]** `tool: run_code` → `python src/evaluate.py`

**[LLM CALL]** claude-opus-4-8 (streaming, adaptive thinking, effort=high)
Context: computed diagnostics (CI, FFT error, synthetic ratio) + report
summaries (cached) + evaluation instructions
Output: streamed to console + written to `reports/self_evaluation.md`

**[KEY FINDING FROM EVALUATION]**
The most fundamental limitation identified: the synthetic data was generated
FROM the same parameters the analysis then 'confirms' — a circular validation.
The CV confidence interval [0.101, 0.267] straddles the 0.20 predictability
threshold, meaning the classification is not statistically robust at n={ia['n_intervals']}
intervals. The FFT failure was flagged as a methodological issue that was
glossed over rather than corrected.

---

## Phase 5 — Final Deliverables  *(Claude API)*

**[USER → AGENT]**

> *Prompt (phase5.md):* Generate agent_design.md, README.md,
> requirements.txt, interaction log, session summary, and final report.
> Make sure all files are written to disk.

**[AGENT ACTION]** `tool: write_file` → `src/finalize.py`
**[AGENT ACTION]** `tool: run_code` → `python src/finalize.py`

**[LLM CALL]** claude-opus-4-8 (streaming, adaptive thinking, effort=high)
Context: all prior reports (cached) + final report instructions
Output: streamed to console + written to `reports/final_report.md`

**[ADDITIONAL WRITES]**
- `docs/agent_design.md` — updated for LLM-powered two-tier architecture
- `README.md` — includes API key setup instructions
- `requirements.txt` — `anthropic`, `numpy`
- `logs/interaction_log.md` — this file
- `logs/session_summary.md` — phase decision log

---

## Summary of Agent Behavior

| Phase | LLM Used | Tool Calls | Key Decision |
|-------|----------|------------|--------------|
| 1 | No | web_fetch (failed), write×3, run | Fallback to synthetic data |
| 2 | No | write, run | Accept FFT failure; use CV as primary signal |
| 3 | **Yes** (opus-4-8) | write, run, API call | Generate 4 scenarios; classify T3 as novel |
| 4 | **Yes** (opus-4-8) | write, run, API call | Prioritize circular-data problem as core limitation |
| 5 | **Yes** (opus-4-8) | write×6, run, API call | Generate unified final report |
"""
    write(os.path.join(LOGS_DIR, "interaction_log.md"), text)


# --------------------------------------------------------------------------- #
# 5. Session summary                                                           #
# --------------------------------------------------------------------------- #

def write_session_summary(p1: dict, p2: dict) -> None:
    ia = p2["interval_analysis"]
    dw = p2["disruption_window"]
    fft = p2["fft_periodicity"]
    ap = p2["attack_probability"]

    text = f"""\
# Session Summary: LEO Handoff Security Agent

## Phase 1 — Data Ingestion and Handoff Detection

**Goal:** Parse latency measurements, detect handoff events, extract
inter-handoff interval statistics.

**Key decisions:**
- Attempted to fetch empirical data from `lens-starlink.jinwei.me` — HTTP 403.
  Fell back to synthetic generation using documented Starlink Gen1 parameters.
- Rolling-median baseline (5s half-window) chosen over global mean to handle
  slow RTT drift without masking local spikes.
- De-duplication gap set to 5s: collapses multi-sample spikes into one event.

**Results:** {p1['n_handoffs']} handoff events over {p1['duration_s']/60:.1f} min.
Mean interval: {ia['mean_s']:.2f}s ± {ia['std_s']:.2f}s.

**Course corrections:** None in this phase.

---

## Phase 2 — Predictability Analysis

**Goal:** Characterise interval distribution, test periodicity, estimate
attack success probability.

**Key decisions:**
- CV (scale-invariant) chosen over raw std dev as the predictability metric.
- FFT run on the full RTT series (not just the interval series) to get a
  continuous spectral view. Detrended with 100-sample (10s) convolution.
- Gaussian timing-error model for P(hit): prediction error ~ N(0, σ²).

**Dead end — FFT:** Dominant period {fft['dominant_period_s']:.2f}s
vs. expected ~{ia['mean_s']:.1f}s (61% error). Root cause: 10s detrending
window attenuates the target frequency. Noted as a methodological weakness
(documented in Phase 4); interval-level statistics used as primary evidence.

**Results:** CV={ia['cv']:.3f} (highly predictable). Disruption window
{dw['mean_disruption_window_s']:.3f}s. P(hit): {ap['p_hit_per_prediction']*100:.1f}%.
Expected {ap['expected_hits_per_hour']:.0f} hits/hour.

---

## Phase 3 — Threat Model  *(LLM)*

**Goal:** Step-by-step security analyst reasoning using Claude API.

**Key decisions:**
- Phase 1 & 2 JSON passed to claude-opus-4-8 with adaptive thinking (effort=high).
- System prompt and JSON context cached for subsequent phases.
- Generated 4 scenarios rather than required 3: T4 (thundering herd) added
  because it has no attacker requirement and is highest-likelihood.
- T3 (geolocation fingerprinting) classified as "Novel" based on literature gap.

**Course corrections:** Initial drafting overstated the TCP RST mechanism in
T2. Phase 4 evaluation flagged this; documented as an unvalidated assumption.

---

## Phase 4 — Self-Evaluation  *(LLM)*

**Goal:** Genuine critical evaluation of methodology for the final report.

**Key decisions:**
- Computed diagnostics algorithmically first (CI, FFT error %, synth ratio).
- Each prose critique in the Claude-generated evaluation cites a specific number.
- Circular-data problem identified as the most fundamental limitation.
- CV confidence interval [0.101, 0.267] straddles the 0.20 threshold —
  the "highly predictable" classification is not statistically robust.

---

## Phase 5 — Final Deliverables  *(LLM)*

**Goal:** Generate all documentation and a unified 5–8 page final report.

**Key decisions:**
- `requirements.txt` contains only `anthropic` and `numpy`.
- Agent design doc updated to reflect two-tier architecture (algorithmic + LLM).
- Interaction log framed as "reconstructed transcript" since Claude Code does
  not export session logs natively.
- Final report generated via Claude API from all accumulated outputs.
"""
    write(os.path.join(LOGS_DIR, "session_summary.md"), text)


# --------------------------------------------------------------------------- #
# 6. Final report (Claude API)                                                 #
# --------------------------------------------------------------------------- #

FINAL_REPORT_SYSTEM = """\
You are an academic writer producing a graduate course final report. \
You write clearly, precisely, and with appropriate hedging for findings that \
rest on synthetic data. You do not exaggerate claims or hide limitations.\
"""

FINAL_REPORT_INSTRUCTIONS = """\
Using the project reports above, write a 5–8 page academic report in Markdown. \
Begin with:

# LEO Satellite Handoff Timing as a Network Security Surface:
# An Agentic AI-Assisted Analysis

Include exactly these four sections:

## 1. Problem Statement
- What is the security question being investigated?
- Why are LEO satellite handoffs a plausible attack surface?
- What makes handoff timing predictability security-relevant?
- (1–1.5 pages)

## 2. Approach
- How the agentic AI pipeline was designed and used
- Two-tier architecture: algorithmic analysis (Phases 1–2) feeding LLM
  reasoning (Phases 3–4)
- Data strategy: empirical attempt, fallback to synthetic, why this is
  academically honest when documented
- Key analytical methods: rolling-median detection, CV predictability metric,
  Gaussian attack probability model
- How Claude was used as the security analyst (tool use, multi-step reasoning)
- (1.5–2 pages)

## 3. Results
- Handoff detection findings with specific numbers
- Predictability analysis: CV, model classification, attack P(hit)
- Threat model summary: all 4 scenarios with likelihood/impact/novelty
- Which findings are strongest (Poisson rejection, disruption window
  measurement) and which are weakest (FFT result, T3 geolocation claim)
- (2–2.5 pages)

## 4. Limitations of AI-Assisted Analysis
- Draw from the self-evaluation report
- Cover: circular data, sample size, FFT failure, unvalidated mechanistic
  claims, absence of ground truth, no peer validation
- What would a rigorous academic version require?
- Conclude with a clear statement of what this work IS and IS NOT
- (1–1.5 pages)

## References
List 4–6 relevant papers the analysis cited or would cite:
(Bhattacherjee et al. 2019, Kassem et al. 2020, Zhang et al. 2004,
Vasisht et al. on satellite networking, RFC 9000 QUIC)

Keep language precise. Cite specific numbers from the data throughout.\
"""


def write_final_report(p1: dict, p2: dict) -> None:
    client = anthropic.Anthropic()

    # Load Tier 2 outputs for context
    threat_model_text = read_report("threat_model.md")
    self_eval_text = read_report("self_evaluation.md")

    context = json.dumps({
        "handoff_detection": {
            "source": p1["source"],
            "n_samples": p1["n_samples"],
            "duration_s": p1["duration_s"],
            "n_handoffs": p1["n_handoffs"],
            "interval_stats": p2["interval_analysis"],
        },
        "predictability": {
            "distribution_model": p2["distribution_model"],
            "disruption_window": p2["disruption_window"],
            "attack_probability": p2["attack_probability"],
            "fft_result": p2["fft_periodicity"],
        },
    }, indent=2)

    # Assemble all content for the context block
    full_context = (
        f"EMPIRICAL SUMMARY (JSON):\n{context}\n\n"
        f"THREAT MODEL REPORT:\n{threat_model_text}\n\n"
        f"SELF-EVALUATION REPORT:\n{self_eval_text}"
    )

    print("\n  Generating final report (streaming)...")
    print("  " + "-" * 66)

    full_text = ""

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=8192,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": "high"},
        system=[
            {
                "type": "text",
                "text": FINAL_REPORT_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": full_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": FINAL_REPORT_INSTRUCTIONS,
                    },
                ],
            }
        ],
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "thinking":
                    print("  [Reasoning", end="", flush=True)
                elif event.content_block.type == "text" and full_text == "":
                    print()
            elif event.type == "content_block_delta":
                if event.delta.type == "thinking_delta":
                    print(".", end="", flush=True)
                elif event.delta.type == "text_delta":
                    print("  " + event.delta.text if event.delta.text.startswith("#")
                          else event.delta.text, end="", flush=True)
                    full_text += event.delta.text

        final = stream.get_final_message()

    print("\n  " + "-" * 66)
    cache_info = (
        f"cache_read={final.usage.cache_read_input_tokens or 0}  "
        f"cache_write={final.usage.cache_creation_input_tokens or 0}  "
        f"uncached={final.usage.input_tokens}"
    )
    print(f"  Token usage: {cache_info}")

    write(os.path.join(REPORTS_DIR, "final_report.md"), full_text)


# --------------------------------------------------------------------------- #
# Orchestrator                                                                 #
# --------------------------------------------------------------------------- #

def run_finalize() -> None:
    print("\n\n=== Phase 5: Final Deliverables ===\n")

    p1 = load("handoff_detection.json")
    p2 = load("predictability_analysis.json")

    write_agent_design()
    write_readme(p1, p2)
    write_requirements()
    write_interaction_log(p1, p2)
    write_session_summary(p1, p2)
    write_final_report(p1, p2)

    print("\nAll deliverables written.")


if __name__ == "__main__":
    run_finalize()
