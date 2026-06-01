"""
Phase 3: LLM-powered threat model generation.

Sends Phase 1 & 2 empirical findings to Claude, which reasons through
five analyst steps and streams a structured threat model report.
"""

import json
import os
import sys

import anthropic

sys.path.insert(0, os.path.dirname(__file__))

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

SYSTEM_PROMPT = """\
You are a network security analyst specializing in satellite communications \
and protocol-layer attacks. You produce rigorous, empirically-grounded threat models.

When given measurement data you:
1. Characterize the attack surface using the specific numbers provided
2. Generate concrete threat scenarios with attacker capability requirements
3. Assess severity honestly, noting what is novel vs. already documented
4. Propose mitigations at each network layer (link, transport, application)

Your analysis cites empirical values throughout. You do not pad with generic security \
advice and do not make claims that go beyond what the data supports.\
"""

ANALYST_STEPS = """\
Work through the following five steps. Show your reasoning at each step before \
moving to the next.

Step 1 — CHARACTERIZE THE ATTACK SURFACE
- What does the disruption window look like empirically?
- Is the timing predictable enough for a targeted attacker?
- What protocol-layer sessions would be disrupted? (TCP, QUIC, TLS, real-time \
  applications — reason from disruption duration vs. typical timeout values)

Step 2 — THREAT SCENARIO GENERATION
Generate at least 3 concrete threat scenarios:
  a) Volumetric DoS timed to handoff windows
  b) Session hijack / desynchronization during handoff
  c) Timing-based traffic analysis to infer user location / orbit position
For each: attacker capability required, victim impact, feasibility given the data.

Step 3 — SEVERITY ASSESSMENT
For each scenario:
- Likelihood (given attacker capability)
- Impact (what does the victim lose?)
- Is this novel or already documented in literature?

Step 4 — MITIGATIONS
Propose mitigations at link, transport, and application layers. For each, \
note which threat scenarios it addresses.

Step 5 — WRITE THE FINAL REPORT
Produce the complete structured threat model in Markdown.  Begin with:

# Threat Model: LEO Satellite Handoff Security Analysis

Include: executive summary, empirical metrics table, per-scenario detail, \
severity summary table, and layered mitigations.  All claims must cite \
specific numbers from the empirical data.\
"""


def load_report(name: str) -> dict:
    with open(os.path.join(REPORTS_DIR, name)) as f:
        return json.load(f)


def section(title: str) -> None:
    print(f"\n{'='*70}\n  {title}\n{'='*70}\n")


def run_threat_model() -> str:
    section("Phase 3: LEO Handoff Security Threat Model  [Claude API]")

    client = anthropic.Anthropic()

    p1 = load_report("handoff_detection.json")
    p2 = load_report("predictability_analysis.json")

    context_json = json.dumps(
        {"handoff_detection": p1, "predictability_analysis": p2}, indent=2
    )

    print("Sending empirical findings to Claude (streaming)...\n")
    print("-" * 70)

    full_text = ""

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=8192,
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
                    # Cache the large empirical context
                    {
                        "type": "text",
                        "text": f"EMPIRICAL DATA:\n{context_json}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    # Uncached: the instructions (stable but small)
                    {
                        "type": "text",
                        "text": ANALYST_STEPS,
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
                    print()  # newline after thinking section
            elif event.type == "content_block_delta":
                if event.delta.type == "thinking_delta":
                    print(".", end="", flush=True)
                elif event.delta.type == "text_delta":
                    print(event.delta.text, end="", flush=True)
                    full_text += event.delta.text
            elif event.type == "content_block_stop":
                if hasattr(event, "index"):
                    # Close the thinking indicator if it was open
                    pass

        final = stream.get_final_message()

    print("\n" + "-" * 70)

    cache_info = (
        f"  cache_read={final.usage.cache_read_input_tokens or 0}  "
        f"cache_write={final.usage.cache_creation_input_tokens or 0}  "
        f"uncached={final.usage.input_tokens}"
    )
    print(f"\nToken usage: {cache_info}")

    out_path = os.path.join(REPORTS_DIR, "threat_model.md")
    with open(out_path, "w") as f:
        f.write(full_text)
    print(f"Report written to: {out_path}")

    return full_text


if __name__ == "__main__":
    run_threat_model()
