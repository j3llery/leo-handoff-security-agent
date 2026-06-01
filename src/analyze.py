"""
Phase 2: Handoff predictability analysis.

1. Statistical characterization of inter-handoff intervals
2. Periodicity test via FFT on the raw RTT time series
3. Distribution model identification (periodic vs. Poisson vs. irregular)
4. Disruption window estimation from raw measurements
5. Attack success probability given predictive timing
"""

import json
import math
import os
import statistics
from dataclasses import asdict, dataclass
from typing import List, Tuple

import numpy as np

from ingest import Measurement, load_or_generate
from detect import HandoffEvent, DetectionResult, detect_handoffs


# --------------------------------------------------------------------------- #
# Interval distribution analysis                                               #
# --------------------------------------------------------------------------- #

def _predictability_score(cv: float) -> str:
    if cv < 0.20:
        return "highly predictable"
    if cv < 0.50:
        return "moderately predictable"
    return "irregular"


def analyze_intervals(intervals: List[float]) -> dict:
    mean = statistics.mean(intervals)
    std = statistics.stdev(intervals) if len(intervals) > 1 else 0.0
    cv = std / mean if mean > 0 else float("inf")
    return {
        "mean_s": round(mean, 3),
        "std_s": round(std, 3),
        "min_s": round(min(intervals), 3),
        "max_s": round(max(intervals), 3),
        "cv": round(cv, 4),
        "n_intervals": len(intervals),
        "predictability": _predictability_score(cv),
    }


# --------------------------------------------------------------------------- #
# Distribution model identification                                            #
# --------------------------------------------------------------------------- #

def identify_model(cv: float) -> dict:
    """
    For inter-event intervals:
      Exponential (Poisson process) → CV ≈ 1.0
      Periodic with Gaussian jitter → CV << 1
      High-variance / bursty        → CV >> 1
    """
    if cv < 0.35:
        model = "periodic_with_jitter"
        explanation = (
            f"CV={cv:.3f} is well below 1.0, inconsistent with a Poisson/exponential "
            "process (which requires CV≈1). The distribution resembles a periodic "
            "clock with small Gaussian jitter — consistent with scheduled satellite "
            "beam-switching."
        )
    elif cv < 0.75:
        model = "quasi_periodic"
        explanation = (
            f"CV={cv:.3f} is intermediate. The process shows regularity but with "
            "significant variability, possibly due to load-dependent scheduling."
        )
    else:
        model = "poisson_or_irregular"
        explanation = (
            f"CV={cv:.3f} is close to or above 1.0, consistent with a Poisson "
            "process or irregular scheduling."
        )
    return {"model": model, "explanation": explanation}


# --------------------------------------------------------------------------- #
# FFT periodicity detection on raw RTT series                                  #
# --------------------------------------------------------------------------- #

def fft_periodicity(measurements: List[Measurement], freq_lo: float = 0.03, freq_hi: float = 0.25) -> dict:
    """
    Run FFT on the RTT time series and find the dominant frequency
    within [freq_lo, freq_hi] Hz (periods 4–33 s).
    Returns dominant period, its power, and the fraction of total spectral
    power it represents.
    """
    rtts = np.array([m.rtt_ms for m in measurements])
    dt = measurements[1].timestamp_s - measurements[0].timestamp_s  # sample interval

    # Detrend by subtracting rolling mean to reduce DC and slow drift
    rtts_detrended = rtts - np.convolve(rtts, np.ones(100) / 100, mode="same")

    spectrum = np.abs(np.fft.rfft(rtts_detrended)) ** 2
    freqs = np.fft.rfftfreq(len(rtts), d=dt)

    # Restrict to the band of interest
    mask = (freqs >= freq_lo) & (freqs <= freq_hi)
    band_freqs = freqs[mask]
    band_power = spectrum[mask]

    if len(band_power) == 0 or band_power.max() == 0:
        return {"dominant_period_s": None, "band_power_fraction": 0.0}

    peak_idx = int(np.argmax(band_power))
    dominant_freq = float(band_freqs[peak_idx])
    dominant_period = round(1.0 / dominant_freq, 2) if dominant_freq > 0 else None
    band_fraction = round(float(band_power[peak_idx]) / float(spectrum.sum()), 4)

    return {
        "dominant_period_s": dominant_period,
        "dominant_freq_hz": round(dominant_freq, 5),
        "band_power_fraction": band_fraction,
        "interpretation": (
            f"Strongest spectral peak at {dominant_period}s period, carrying "
            f"{band_fraction*100:.1f}% of total signal power — "
            + ("consistent with regular handoff periodicity." if band_fraction > 0.10
               else "weak periodicity signal.")
        ),
    }


# --------------------------------------------------------------------------- #
# Disruption window estimation                                                 #
# --------------------------------------------------------------------------- #

def estimate_disruption_window(
    measurements: List[Measurement],
    events: List[HandoffEvent],
    baseline_buffer_ms: float = 10.0,
    search_window_s: float = 2.0,
) -> dict:
    """
    For each handoff event, find the contiguous span of samples whose RTT
    exceeds (peak_rtt - spike_magnitude + baseline_buffer) around the event
    timestamp to estimate how long the disruption lasts.
    """
    dt = measurements[1].timestamp_s - measurements[0].timestamp_s
    ts_array = np.array([m.timestamp_s for m in measurements])
    rtt_array = np.array([m.rtt_ms for m in measurements])

    # Estimate baseline globally from the 20th percentile (stable low RTT)
    global_baseline = float(np.percentile(rtt_array, 20))
    disruption_threshold = global_baseline + baseline_buffer_ms

    durations = []
    for ev in events:
        lo_ts = ev.timestamp_s - search_window_s
        hi_ts = ev.timestamp_s + search_window_s
        mask = (ts_array >= lo_ts) & (ts_array <= hi_ts)
        local_rtts = rtt_array[mask]

        if len(local_rtts) == 0:
            continue

        # Count consecutive samples above threshold starting from the peak
        above = local_rtts > disruption_threshold
        # Find the contiguous run that includes the maximum
        peak_local_idx = int(np.argmax(local_rtts))
        # Expand left and right from peak while above threshold
        left = peak_local_idx
        while left > 0 and above[left - 1]:
            left -= 1
        right = peak_local_idx
        while right < len(above) - 1 and above[right + 1]:
            right += 1
        duration = (right - left + 1) * dt
        durations.append(duration)

    if durations:
        mean_dur = statistics.mean(durations)
        std_dur = statistics.stdev(durations) if len(durations) > 1 else 0.0
    else:
        mean_dur = std_dur = 0.0

    return {
        "mean_disruption_window_s": round(mean_dur, 3),
        "std_disruption_window_s": round(std_dur, 3),
        "min_disruption_window_s": round(min(durations), 3) if durations else 0.0,
        "max_disruption_window_s": round(max(durations), 3) if durations else 0.0,
        "global_baseline_rtt_ms": round(global_baseline, 2),
        "n_measured": len(durations),
    }


# --------------------------------------------------------------------------- #
# Attack success probability                                                   #
# --------------------------------------------------------------------------- #

def attack_probability(
    mean_interval_s: float,
    std_interval_s: float,
    disruption_window_s: float,
) -> dict:
    """
    Models an attacker who:
      1. Observes N handoff events to build a timing estimate
      2. Predicts the next handoff time with uncertainty ~ N(0, std²)
      3. Launches an attack at the predicted time

    P(hit) = P(|timing_error| <= disruption_window / 2)
           = erf(disruption_window / (2 * std * sqrt(2)))

    Also computes the exploitable fraction of each handoff cycle
    and the expected hits per hour.
    """
    if std_interval_s <= 0 or disruption_window_s <= 0:
        return {"p_hit": 0.0, "exploitable_fraction": 0.0}

    half_window = disruption_window_s / 2.0
    p_hit = math.erf(half_window / (std_interval_s * math.sqrt(2)))

    exploitable_fraction = disruption_window_s / mean_interval_s
    handoffs_per_hour = 3600.0 / mean_interval_s
    expected_hits_per_hour = p_hit * handoffs_per_hour

    return {
        "p_hit_per_prediction": round(p_hit, 4),
        "exploitable_fraction_of_cycle": round(exploitable_fraction, 4),
        "handoffs_per_hour": round(handoffs_per_hour, 1),
        "expected_hits_per_hour": round(expected_hits_per_hour, 1),
        "interpretation": (
            f"An attacker predicting handoff timing with ±{std_interval_s:.2f}s uncertainty "
            f"has a {p_hit*100:.1f}% chance of launching within the {disruption_window_s:.2f}s "
            f"disruption window. Over one hour (~{handoffs_per_hour:.0f} handoffs) "
            f"this yields ~{expected_hits_per_hour:.0f} successful attack windows."
        ),
    }


# --------------------------------------------------------------------------- #
# Top-level runner                                                              #
# --------------------------------------------------------------------------- #

def run_analysis(
    measurements: List[Measurement],
    detection: DetectionResult,
    reports_dir: str,
) -> dict:
    intervals = detection.intervals_s
    events = detection.events

    print("--- Interval distribution ---")
    interval_stats = analyze_intervals(intervals)
    for k, v in interval_stats.items():
        print(f"  {k:<30}: {v}")

    print("\n--- Distribution model ---")
    model = identify_model(interval_stats["cv"])
    print(f"  model        : {model['model']}")
    print(f"  explanation  : {model['explanation']}")

    print("\n--- FFT periodicity (raw RTT series) ---")
    fft = fft_periodicity(measurements)
    print(f"  dominant period  : {fft['dominant_period_s']} s")
    print(f"  band power frac  : {fft['band_power_fraction']*100:.1f}%")
    print(f"  interpretation   : {fft['interpretation']}")

    print("\n--- Disruption window ---")
    disruption = estimate_disruption_window(measurements, events)
    print(f"  mean duration    : {disruption['mean_disruption_window_s']} s")
    print(f"  std duration     : {disruption['std_disruption_window_s']} s")
    print(f"  baseline RTT     : {disruption['global_baseline_rtt_ms']} ms")

    print("\n--- Attack success probability ---")
    attack = attack_probability(
        interval_stats["mean_s"],
        interval_stats["std_s"],
        disruption["mean_disruption_window_s"],
    )
    print(f"  P(hit) per prediction  : {attack['p_hit_per_prediction']*100:.1f}%")
    print(f"  Exploitable fraction   : {attack['exploitable_fraction_of_cycle']*100:.2f}% of cycle")
    print(f"  Expected hits/hour     : {attack['expected_hits_per_hour']}")
    print(f"  {attack['interpretation']}")

    result = {
        "interval_analysis": interval_stats,
        "distribution_model": model,
        "fft_periodicity": fft,
        "disruption_window": disruption,
        "attack_probability": attack,
    }

    os.makedirs(reports_dir, exist_ok=True)
    out_path = os.path.join(reports_dir, "predictability_analysis.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nReport written to: {out_path}")

    return result
