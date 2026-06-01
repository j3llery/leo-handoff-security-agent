# Working Notes (Steps 1–4)

Before the report, a standing caveat that conditions everything below: `source: "synthetic"`, `n_handoffs = 40`, `duration_s = 599.9`. These are model-generated values, not live captures. Conclusions are valid for the *modeled* system; field validation is required before operational claims.

---

## Step 1 — Characterize the Attack Surface

**The disruption window (empirical shape):**
- Mean duration `0.323 s`, std `0.053 s`, bounded `[0.2 s, 0.4 s]`. This is tight — the window is short and low-variance.
- Baseline RTT is `25.51 ms`. During handoff, peak RTT ranges `78.21–196.81 ms` and spike magnitude `49.86–168.18 ms`. So a handoff elevates RTT to roughly **3×–7.7× baseline**.
- Implication: the event is *brief* (sub-second) but *loud* — the RTT spike is 2–7× the noise floor, making each handoff trivially detectable by passive observation. This is the key asymmetry: the outage is hard to exploit (short) but easy to detect (large SNR).

**Timing predictability:**
- Interval mean `14.738 s`, std `2.163 s`, **CV = 0.1467**. CV ≪ 1 rules out a Poisson process and confirms `periodic_with_jitter`. An attacker can lock onto the `~14.7 s` cadence.
- The `±2.163 s` jitter is what limits precision. The FFT result (`dominant_period_s = 5.77`, `band_power_fraction = 0.0043`) is a **weak/spurious** spectral signal — only 0.4% of power, and 5.77 s doesn't even match the 14.7 s interval. **The predictability comes from the interval statistics, not the spectrum.** I will not lean on the FFT.
- Quantified exploitability: `p_hit_per_prediction = 0.0595`, `exploitable_fraction_of_cycle = 0.0219`. A single blind shot at the predicted time hits the `0.323 s` window 6% of the time. Across `244.3 handoffs/hour`, that's `~14.5 hits/hour` — meaningful, not trivial.

**Affected protocol-layer sessions (reasoning from `0.2–0.4 s` outage vs. timeouts):**
- **TCP:** With baseline RTT `25.51 ms`, a Linux SRTT-derived RTO sits near the `200 ms` minimum. A `0.323 s` outage exceeds that → **spurious RTO, retransmit, and `cwnd` collapse**. The damage is not the 0.32 s gap itself but the multi-RTT congestion-control recovery it triggers. This is the most exposed layer.
- **QUIC/TLS-over-QUIC:** PTO and connection migration absorb `0.32 s` more gracefully; degraded but resilient. TLS itself sees nothing unless the underlying transport drops.
- **Real-time (VoIP/RTC/gaming):** Jitter buffers are typically `60–200 ms`. A `0.323 s` (max `0.4 s`) gap **exceeds the buffer → audible dropout / frame loss**. The `78–197 ms` peak RTT is itself tolerable one-way; the *outage* is the problem.

---

## Step 2 — Threat Scenarios

**(a) Handoff-synchronized volumetric DoS**
- *Capability:* Passive RTT monitoring of the victim path (handoffs are visible as 3–7× baseline spikes — near-zero detection cost) + ability to inject load toward the victim/gateway or jam the RF link. Predict next handoff from the `14.738 s` cadence.
- *Impact:* Fire a burst into the `0.323 s` window when the link is already at peak stress (`up to 196.81 ms` RTT, queues full). This compounds the natural outage and reliably triggers the TCP RTO/`cwnd`-collapse cascade described above, converting a `0.32 s` blip into multi-second throughput loss.
- *Feasibility:* **High.** With `±2.16 s` jitter, a single shot has `5.95%` hit probability; widening the burst to cover ±1–2σ raises hit rate toward certainty but the duty cost is bounded — the exploitable window is only `2.19%` of the cycle, so timed attacks remain far cheaper/stealthier than continuous flooding.

**(b) Session desync / injection during handoff reconvergence**
- *Capability:* Predict the handoff window *and* on-path position or sequence/ACK estimation (off-path injection). Significantly higher bar than (a).
- *Impact:* During the `0.323 s` path transition (possible beam/gateway/NAT remap), inject spoofed segments to desynchronize or RST a TCP session while legitimate packets are delayed.
- *Feasibility:* **Low–moderate.** The data supports the *timing* of a vulnerable window but says nothing about sequence-state exposure during handoff. This scenario is plausible but **partly speculative relative to the dataset.**

**(c) Orbital/location traffic-analysis via handoff cadence**
- *Capability:* Passive RTT observation only. No injection.
- *Impact:* The `mean 14.738 s` interval with `CV = 0.147` is a distinctive periodic fingerprint of beam-switching geometry. Logging handoff timestamps reveals the satellite pass schedule, which constrains the user's ground location and the constellation's orbital phase — a deanonymization/geolocation primitive. The `periodic_with_jitter` signature also cleanly distinguishes LEO-satellite users from terrestrial links.
- *Feasibility:* **High.** Requires only the ability to time the RTT spikes that the data shows are 2–7× baseline.

---

## Step 3 — Severity Assessment

| Scenario | Likelihood | Impact | Novelty |
|---|---|---|---|
| (a) Timed DoS | High — passive detection trivial (3–7× spike), `14.5 hits/hr` per blind shot, predictable `14.7 s` cadence | Moderate–High — amplifies `0.32 s` outage into transport-layer backoff cascades | Incremental — handoff-timed jamming is discussed in LEO security work; the precise quantified timing exploitation is a sharpening, not a new class |
| (b) Desync/injection | Low–Moderate — needs seq/on-path capability the data doesn't evidence | High if successful — session takeover/teardown | TCP injection is well-documented; handoff-window framing is novel but **unsupported by this dataset** |
| (c) Timing traffic analysis | High — passive, single-capability | Moderate — location/orbit inference, LEO-user fingerprinting (privacy, not integrity) | Emerging — LEO timing-side-channel fingerprinting is an active, under-explored area |

---

## Step 4 — Mitigations

**Link layer**
- **Make-before-break handoff** to shrink/eliminate the `0.323 s` gap → directly defeats (a) and the transport-cascade trigger.
- **Schedule dithering:** raise jitter so `CV` rises from `0.147` toward ≥1 (decorrelate intervals). This cuts the `5.95%` per-shot hit probability and degrades the (c) fingerprint. Addresses (a) and (c).
- **Cover traffic / RTT-spike masking** so the 3–7× spike is not externally observable → attacks (a) and (c).
- **Encrypted/authenticated handoff signaling** → reduces (b) surface.

**Transport layer**
- **Prefer QUIC with connection migration + path validation** → absorbs `0.32 s` gaps and blocks the (b) injection/migration race.
- **TCP RTO hardening:** enable F-RTO / RACK and raise min-RTO above the `0.4 s` max window so a single handoff does not force spurious `cwnd` collapse → blunts (a)'s amplification.
- **Handoff-aware PEPs** that suppress retransmit during known `~0.32 s` windows → (a).

**Application layer**
- **Jitter buffers ≥ 400 ms** (covers `max_disruption_window_s = 0.4`) for real-time media → mitigates the dropout from (a) and natural handoffs.
- **Session-resumption / 0-RTT** so application sessions survive transport resets → (a), (b).
- **Constant-rate / padded application traffic** to deny the timing side channel → (c).

---

# Threat Model: LEO Satellite Handoff Security Analysis

## Executive Summary

Analysis of a (synthetic, `n = 40` handoffs over `599.9 s`) LEO handoff dataset shows a system with a **short but highly conspicuous, highly predictable** vulnerability rhythm. Handoffs recur every `14.738 s` (std `2.163 s`, **CV = 0.147** → periodic-with-jitter, not random), each producing a `0.323 s` (range `0.2–0.4 s`) disruption window in which RTT spikes from a `25.51 ms` baseline to `78–197 ms` (3–7.7× baseline). This combination — easy to detect, predictable to within `±2.16 s`, but only `2.19%` of the duty cycle — makes **timed denial-of-service (Scenario a)** and **passive timing-based location inference (Scenario c)** the realistic threats. A single blind attack shot lands inside the window `5.95%` of the time, yielding `~14.5` exploitable windows per hour out of `244.3` handoffs. Session-hijack during handoff (Scenario b) is plausible in principle but **not supported by this dataset**. The strongest single mitigation is make-before-break handoff plus schedule dithering at the link layer.

> **Caveat:** Data is `source: synthetic`. The reported FFT periodicity (`band_power_fraction = 0.0043`, period `5.77 s` inconsistent with the `14.7 s` interval) is statistically weak and **not** the basis for the predictability claim — that rests entirely on the interval `CV = 0.147`.

## Empirical Metrics

| Metric | Value |
|---|---|
| Samples / duration | `6000` / `599.9 s` |
| Handoffs observed | `40` (`244.3/hour`) |
| Interval mean ± std | `14.738 s` ± `2.163 s` |
| Interval CV (predictability) | `0.1467` → "highly predictable" |
| Disruption window mean ± std | `0.323 s` ± `0.053 s` (range `0.2–0.4 s`) |
| Baseline RTT | `25.51 ms` |
| Handoff peak RTT range | `78.21 – 196.81 ms` (3–7.7× baseline) |
| Spike magnitude range | `49.86 – 168.18 ms` |
| Exploitable fraction of cycle | `0.0219` (2.19%) |
| Per-shot hit probability | `0.0595` |
| Expected hits / hour | `14.5` |

## Scenario Detail

**(a) Handoff-synchronized volumetric DoS — Likelihood: High / Impact: Moderate–High.**
Passive RTT monitoring detects each handoff via its 3–7× spike at essentially zero cost; the `14.738 s` cadence predicts the next one. A burst fired into the `0.323 s` window, when the link is already at `~197 ms` peak RTT and `cwnd` is fragile, reliably triggers TCP spurious-RTO and congestion-window collapse, amplifying a sub-second outage into multi-RTT recovery. Cost stays low because the window is only `2.19%` of the cycle.

**(b) Session desync/injection during handoff — Likelihood: Low–Moderate / Impact: High.**
Exploiting the `0.323 s` path-reconvergence window for spoofed-segment injection or RST. Plausible but requires sequence/on-path capability the dataset does not characterize. **Flagged as speculative relative to the data.**

**(c) Timing traffic analysis for location/orbit inference — Likelihood: High / Impact: Moderate.**
The `14.738 s` / `CV = 0.147` periodic signature is an orbital fingerprint observable from the RTT spikes alone. It enables LEO-user identification and constrains ground location and orbital phase. Passive, single-capability, no injection.

## Severity Summary

| Scenario | Likelihood | Impact | Novelty | Priority |
|---|---|---|---|---|
| (a) Timed DoS | High | Moderate–High | Incremental | **P1** |
| (b) Desync/injection | Low–Moderate | High | Novel framing, unsupported by data | P3 |
| (c) Timing analysis | High | Moderate (privacy) | Emerging | **P2** |

## Layered Mitigations

| Layer | Control | Addresses |
|---|---|---|
| Link | Make-before-break handoff (eliminate `0.323 s` gap) | (a), (b) |
| Link | Schedule dithering (raise `CV` from `0.147`) | (a), (c) |
| Link | Cover traffic / mask the 3–7× RTT spike | (a), (c) |
| Link | Authenticated handoff signaling | (b) |
| Transport | QUIC connection migration + path validation | (a), (b) |
| Transport | RACK/F-RTO, min-RTO > `0.4 s` to stop spurious backoff | (a) |
| Transport | Handoff-aware PEP retransmit suppression | (a) |
| Application | Jitter buffer ≥ `400 ms` (covers `max 0.4 s`) | (a) + natural |
| Application | Session resumption / 0-RTT | (a), (b) |
| Application | Constant-rate / padded traffic | (c) |

**Top recommendation:** Make-before-break handoff with interval dithering simultaneously closes the exploitable window driving Scenario (a) and degrades the periodic fingerprint enabling Scenario (c) — the two threats the empirical data actually supports.