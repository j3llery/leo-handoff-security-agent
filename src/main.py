"""
Pipeline orchestrator — runs all completed phases in sequence.
"""

import json
import os
import sys

# Allow running from repo root or src/
sys.path.insert(0, os.path.dirname(__file__))


def _load_dotenv() -> None:
    """Load .env from the repo root into os.environ (no external deps)."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

from ingest import load_or_generate
from detect import detect_handoffs
from analyze import run_analysis
from threat_model import run_threat_model
from evaluate import run_evaluation
from finalize import run_finalize


REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def main():
    print("=== Phase 1: LEO Handoff Detection ===\n")

    # --- Ingest ---
    print("Loading data...")
    measurements, source = load_or_generate(DATA_DIR)
    print(f"  Source      : {source}")
    print(f"  Samples     : {len(measurements)}")
    duration = measurements[-1].timestamp_s - measurements[0].timestamp_s
    print(f"  Duration    : {duration:.1f} s ({duration/60:.1f} min)")
    rtts = [m.rtt_ms for m in measurements]
    print(f"  RTT range   : {min(rtts):.1f} – {max(rtts):.1f} ms")
    print()

    # --- Detect ---
    print("Detecting handoff events...")
    result = detect_handoffs(measurements, spike_threshold_ms=30.0, window_s=5.0, min_gap_s=5.0)
    print(f"  Events found: {len(result.events)}")
    print()

    # --- Summary ---
    print("Inter-handoff interval statistics:")
    print(f"  Mean        : {result.mean_interval_s:.2f} s")
    print(f"  Std dev     : {result.std_interval_s:.2f} s")
    print(f"  Min         : {result.min_interval_s:.2f} s")
    print(f"  Max         : {result.max_interval_s:.2f} s")
    print()

    print("Detected handoff events:")
    print(f"  {'Timestamp (s)':>14}  {'Spike (ms)':>10}  {'Peak RTT (ms)':>13}")
    print("  " + "-" * 42)
    for ev in result.events:
        print(f"  {ev.timestamp_s:>14.3f}  {ev.spike_magnitude_ms:>10.1f}  {ev.peak_rtt_ms:>13.1f}")
    print()

    # --- Write report ---
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "source": source,
        "n_samples": len(measurements),
        "duration_s": round(duration, 3),
        "n_handoffs": len(result.events),
        "interval_stats": {
            "mean_s": result.mean_interval_s,
            "std_s": result.std_interval_s,
            "min_s": result.min_interval_s,
            "max_s": result.max_interval_s,
        },
        "handoff_events": [
            {
                "timestamp_s": ev.timestamp_s,
                "spike_magnitude_ms": ev.spike_magnitude_ms,
                "peak_rtt_ms": ev.peak_rtt_ms,
            }
            for ev in result.events
        ],
    }
    report_path = os.path.join(REPORTS_DIR, "handoff_detection.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report written to: {report_path}")

    # ------------------------------------------------------------------ #
    # Phase 2: Predictability analysis                                     #
    # ------------------------------------------------------------------ #
    print("\n\n=== Phase 2: Predictability Analysis ===\n")
    run_analysis(measurements, result, REPORTS_DIR)

    # ------------------------------------------------------------------ #
    # Phase 3: Threat model                                                #
    # ------------------------------------------------------------------ #
    run_threat_model()

    # ------------------------------------------------------------------ #
    # Phase 4: Self-evaluation                                             #
    # ------------------------------------------------------------------ #
    run_evaluation()

    # ------------------------------------------------------------------ #
    # Phase 5: Final deliverables                                          #
    # ------------------------------------------------------------------ #
    run_finalize()


if __name__ == "__main__":
    main()
