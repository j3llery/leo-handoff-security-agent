"""
Data loading and normalization for LEO handoff analysis.

Attempts to load empirical data from data/measurements.csv.
If unavailable, generates a synthetic dataset based on known
Starlink Gen1 handoff parameters (documented in phase1.md).
"""

import csv
import math
import random
import os
from dataclasses import dataclass
from typing import List


@dataclass
class Measurement:
    timestamp_s: float   # seconds since start
    rtt_ms: float


def load_csv(path: str) -> List[Measurement]:
    measurements = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            measurements.append(Measurement(
                timestamp_s=float(row["timestamp_s"]),
                rtt_ms=float(row["rtt_ms"]),
            ))
    return measurements


def generate_synthetic(
    duration_s: float = 600.0,
    sample_interval_s: float = 0.1,
    baseline_rtt_ms: float = 28.0,
    baseline_noise_std_ms: float = 3.0,
    handoff_interval_s: float = 15.0,
    handoff_jitter_s: float = 2.5,
    spike_min_ms: float = 60.0,
    spike_max_ms: float = 280.0,
    spike_duration_s: float = 0.35,
    seed: int = 42,
) -> List[Measurement]:
    """
    Synthetic dataset modelling Starlink Gen1 handoff behavior.
    Documented parameters from Bhattacherjee et al. and Kassem et al.
    """
    rng = random.Random(seed)

    # Pre-compute handoff event times
    handoff_times = []
    t = handoff_interval_s + rng.gauss(0, handoff_jitter_s)
    while t < duration_s - 2.0:
        handoff_times.append(t)
        t += handoff_interval_s + rng.gauss(0, handoff_jitter_s)

    measurements = []
    n_samples = int(duration_s / sample_interval_s)
    for i in range(n_samples):
        ts = i * sample_interval_s
        rtt = baseline_rtt_ms + rng.gauss(0, baseline_noise_std_ms)

        # Add spike for any active handoff event
        for ht in handoff_times:
            if ht <= ts < ht + spike_duration_s:
                spike_mag = rng.uniform(spike_min_ms, spike_max_ms)
                # Exponential decay within the spike window
                frac = (ts - ht) / spike_duration_s
                decay = math.exp(-3.0 * frac)
                rtt += spike_mag * decay
                break

        measurements.append(Measurement(timestamp_s=round(ts, 3), rtt_ms=round(max(rtt, 1.0), 3)))

    return measurements


def save_csv(measurements: List[Measurement], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "rtt_ms"])
        for m in measurements:
            writer.writerow([m.timestamp_s, m.rtt_ms])


def load_or_generate(data_dir: str = "data") -> tuple[List[Measurement], str]:
    """Return (measurements, source_label)."""
    empirical_path = os.path.join(data_dir, "measurements.csv")
    if os.path.exists(empirical_path):
        measurements = load_csv(empirical_path)
        return measurements, "empirical"

    measurements = generate_synthetic()
    synthetic_path = os.path.join(data_dir, "synthetic_measurements.csv")
    save_csv(measurements, synthetic_path)
    return measurements, "synthetic"
