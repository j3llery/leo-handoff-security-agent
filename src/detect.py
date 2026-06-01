"""
Handoff detection logic.

Uses a rolling-median baseline to identify RTT spikes that exceed
a dynamic threshold, then clusters nearby detections into single
handoff events and extracts inter-handoff intervals.
"""

import statistics
from dataclasses import dataclass
from typing import List

from ingest import Measurement


@dataclass
class HandoffEvent:
    timestamp_s: float
    spike_magnitude_ms: float   # RTT at peak minus local baseline
    peak_rtt_ms: float


@dataclass
class DetectionResult:
    events: List[HandoffEvent]
    mean_interval_s: float
    std_interval_s: float
    min_interval_s: float
    max_interval_s: float
    intervals_s: List[float]


def _rolling_median(values: List[float], window: int) -> List[float]:
    half = window // 2
    result = []
    n = len(values)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        result.append(statistics.median(values[lo:hi]))
    return result


def detect_handoffs(
    measurements: List[Measurement],
    spike_threshold_ms: float = 30.0,
    window_s: float = 5.0,
    min_gap_s: float = 5.0,
) -> DetectionResult:
    """
    spike_threshold_ms: RTT must exceed rolling median by at least this much.
    window_s:           Half-width of the rolling median window used as baseline.
    min_gap_s:          Minimum time between distinct handoff events (de-duplication).
    """
    if not measurements:
        raise ValueError("Empty measurement list")

    sample_interval = measurements[1].timestamp_s - measurements[0].timestamp_s
    window_samples = max(3, int(window_s / sample_interval))

    rtts = [m.rtt_ms for m in measurements]
    baseline = _rolling_median(rtts, window_samples)

    # Find samples that exceed threshold
    candidates: List[tuple[float, float, float]] = []  # (ts, spike_mag, rtt)
    for m, b in zip(measurements, baseline):
        excess = m.rtt_ms - b
        if excess >= spike_threshold_ms:
            candidates.append((m.timestamp_s, excess, m.rtt_ms))

    # Cluster candidates: keep the peak sample within each gap window
    events: List[HandoffEvent] = []
    if candidates:
        cluster = [candidates[0]]
        for cand in candidates[1:]:
            if cand[0] - cluster[-1][0] <= min_gap_s:
                cluster.append(cand)
            else:
                # Commit peak of previous cluster
                peak = max(cluster, key=lambda x: x[1])
                events.append(HandoffEvent(
                    timestamp_s=peak[0],
                    spike_magnitude_ms=round(peak[1], 2),
                    peak_rtt_ms=round(peak[2], 2),
                ))
                cluster = [cand]
        peak = max(cluster, key=lambda x: x[1])
        events.append(HandoffEvent(
            timestamp_s=peak[0],
            spike_magnitude_ms=round(peak[1], 2),
            peak_rtt_ms=round(peak[2], 2),
        ))

    intervals = [
        round(events[i + 1].timestamp_s - events[i].timestamp_s, 3)
        for i in range(len(events) - 1)
    ]

    if intervals:
        mean_i = statistics.mean(intervals)
        std_i = statistics.stdev(intervals) if len(intervals) > 1 else 0.0
        min_i = min(intervals)
        max_i = max(intervals)
    else:
        mean_i = std_i = min_i = max_i = 0.0

    return DetectionResult(
        events=events,
        mean_interval_s=round(mean_i, 3),
        std_interval_s=round(std_i, 3),
        min_interval_s=round(min_i, 3),
        max_interval_s=round(max_i, 3),
        intervals_s=intervals,
    )
