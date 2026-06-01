# LEO Satellite Handoff Timing as a Network Security Surface:
# An Agentic AI-Assisted Analysis

---

## 1. Problem Statement

Low Earth Orbit (LEO) satellite broadband constellations — Starlink, OneWeb, Kuiper, and successors — have moved from a research curiosity to a deployed access technology serving millions of terminals. Unlike geostationary systems, LEO satellites traverse the sky rapidly relative to a fixed ground terminal, with individual satellites visible for only a few minutes before the link must be transferred to a successor. This transfer, the *handoff* (or beam-switch), is intrinsic to the architecture: it happens continuously, on a schedule dictated by orbital geometry, for every active user. The security question investigated here is narrow and concrete: **does the timing structure of LEO handoffs constitute an exploitable network-security surface, and if so, how exploitable?**

The motivation for treating handoffs as an attack surface rests on three observations. First, a handoff is a *physical-layer discontinuity* with measurable consequences at higher layers. When the serving satellite or beam changes, packets in flight can be delayed or dropped while the new path establishes, producing a brief but pronounced latency excursion. In the dataset analyzed here, the global baseline round-trip time (RTT) is 25.51 ms, while during handoff the peak RTT rises to between 78.21 ms and 196.81 ms — a spike of roughly 3× to 7.7× baseline. The disruption is short (mean window 0.323 s, bounded to [0.2 s, 0.4 s]) but, in transport terms, not negligible.

Second, a sub-second outage interacts badly with congestion control and real-time media. With a 25.51 ms baseline RTT, a Linux TCP retransmission timeout (RTO) sits near its 200 ms floor; a 0.323 s gap therefore exceeds the RTO and can trigger a spurious retransmit and congestion-window (`cwnd`) collapse. The damage is not the 0.32 s gap itself but the multi-RTT recovery it provokes. Real-time codecs are similarly exposed: typical jitter buffers of 60–200 ms are overrun by a 0.323 s (worst case 0.4 s) outage, producing audible dropouts or dropped frames. So the handoff is a recurring, structurally guaranteed event that, *if an adversary can anticipate it*, offers a moment of maximal fragility into which to inject load or interference.

Third — and this is the crux of the security relevance — handoff timing appears to be **predictable rather than random**. Because handoffs are governed by orbital mechanics and scheduled beam management, the inter-handoff intervals are not memoryless arrivals. In the data, the mean interval is 14.738 s with standard deviation 2.163 s, giving a coefficient of variation (CV) of 0.1467. A CV well below 1.0 is inconsistent with a Poisson/exponential process (which requires CV ≈ 1) and is instead consistent with a periodic clock perturbed by small Gaussian jitter. Predictability is what converts a benign, self-healing network event into a security surface: an adversary who can forecast *when* the next fragile window occurs can synchronize an attack to it, and — separately — an adversary who can merely *observe* the cadence can fingerprint the link and infer orbital and geographic information.

It is worth stating at the outset what this report does **not** claim. The data analyzed is explicitly synthetic (`source: "synthetic"`), comprising 40 handoffs over 599.9 s (6000 samples). All conclusions below are valid for the *modeled* system. They are hypotheses about real constellations, not measurements of them. The contribution is a quantified threat-model methodology and a demonstration of an agentic AI analysis pipeline, not an empirical security finding about any deployed network.

---

## 2. Approach

### 2.1 Two-tier agentic architecture

The analysis was structured as a two-tier pipeline that deliberately separates *deterministic measurement* from *judgment-laden reasoning*. Tier one (Phases 1–2) is algorithmic: it ingests the RTT time series, detects handoff events, and computes statistical descriptors with quantified uncertainty. Tier two (Phases 3–4) is an LLM-based security analyst (Claude) that consumes the structured numerical output of tier one and performs multi-step threat reasoning: characterizing the attack surface, enumerating scenarios, scoring severity, and proposing layered mitigations.

The rationale for the split is that the two tiers have different failure modes. Statistical estimation should be reproducible, falsifiable, and free of narrative bias; it belongs in code. Threat enumeration and severity scoring require domain reasoning, analogical thinking across protocol layers, and explicit hedging; that is where an LLM adds value — provided it is fed *numbers it did not invent*. Critically, the LLM was constrained to reason **from** the algorithmic output rather than to generate the underlying statistics, which keeps the empirical claims auditable.

### 2.2 Data strategy

The intended data source was real telemetry: captured RTT/loss traces or handoff logs from an operational terminal. When direct empirical capture was not available, the pipeline fell back to a synthetic generator parameterized on published LEO (Starlink Gen1-class) characteristics. This fallback is academically defensible **only because it is documented as such at every layer**: the JSON summary carries `source: "synthetic"`, the threat-model working notes open with a standing caveat conditioning all conclusions on the synthetic origin, and the self-evaluation explicitly flags the resulting circularity. Synthetic data is legitimate for prototyping a methodology and stress-testing an analysis pipeline; it becomes misrepresentation only if its provenance is hidden or its outputs are presented as empirical findings. We adopt the former posture throughout.

### 2.3 Key analytical methods (Tier 1)

- **Handoff detection.** Handoffs were identified as RTT excursions against a rolling-median baseline, isolating the 3–7.7× spikes from the 25.51 ms noise floor. This yielded 40 events and 39 inter-handoff intervals over 599.9 s (≈244.3 handoffs/hour).
- **Predictability via CV.** The inter-interval CV (0.1467) is the central predictability metric. The pipeline did not stop at the point estimate: it attached a 95% confidence interval of [0.101, 0.267] and a mean-interval half-width of ±0.7 s, and it ran an explicit Poisson null-hypothesis test, rejecting the memoryless model with a z-score of 51.37.
- **Spectral check.** An FFT was computed as an independent corroboration of periodicity. It returned a dominant period of 5.77 s carrying only 0.43% of band power — a weak and, as discussed below, inconsistent result.
- **Gaussian attack-probability model.** The exploitability of timing prediction was modeled by convolving the ±2.163 s timing jitter with the 0.323 s disruption window. This gives an exploitable fraction of the cycle of 0.0219 (2.19%) and a per-prediction hit probability `p_hit = 0.0595`. Multiplied across 244.3 handoffs/hour, the model projects ≈14.5 successful attack windows per hour. The model is deliberately probabilistic — it does not assert deterministic attack success.

### 2.4 Claude as the security analyst (Tier 2)

The LLM tier executed a four-step reasoning chain. **Step 1** characterized the attack surface, reasoning from the 0.2–0.4 s outage to specific protocol-layer consequences (TCP spurious-RTO and `cwnd` collapse as the most exposed layer; QUIC PTO/migration as more resilient; jitter-buffer overrun for real-time media). Notably, the analyst examined the FFT output, judged it spurious (5.77 s does not match the 14.7 s interval; only 0.4% of power), and explicitly declined to rely on it — basing the predictability claim solely on the interval statistics. **Step 2** enumerated threat scenarios; **Step 3** scored each on likelihood, impact, and novelty; **Step 4** proposed mitigations stratified by link, transport, and application layers. The analyst repeatedly tagged claims that outran the data (e.g. labeling the session-injection scenario "partly speculative relative to the dataset"), which is the behavior one wants from a hedged analyst rather than an advocate.

---

## 3. Results

### 3.1 Handoff detection

Detection recovered 40 handoffs across 599.9 s, equivalent to 244.3 handoffs/hour. Inter-handoff intervals had mean 14.738 s, standard deviation 2.163 s, minimum 8.5 s, and maximum 18.4 s. The disruption window — the interval of elevated RTT following each handoff — had mean 0.323 s, standard deviation 0.053 s, and bounds [0.2 s, 0.4 s]. Against the 25.51 ms baseline, handoff peak RTT spanned 78.21–196.81 ms (spike magnitude 49.86–168.18 ms). The signature is thus *brief but loud*: the outage is sub-second yet the RTT excursion is 2–7× the noise floor, making each event trivially detectable by passive observation. This asymmetry — hard to exploit (short), easy to detect (high SNR) — is the central structural finding.

### 3.2 Predictability and attack probability

The interval CV of 0.1467 classified the process as "highly predictable" / `periodic_with_jitter`, and the Poisson null was rejected decisively (z = 51.37). The Gaussian attack model returned exploitable-fraction 0.0219 and `p_hit = 0.0595`: a single blind shot aimed at the predicted handoff time lands inside the 0.323 s window about 6.0% of the time, yielding ≈14.5 hits/hour across 244.3 handoffs. The interpretation is that timed attacks are *meaningful but low-yield per attempt* — far cheaper than continuous flooding (only 2.19% of the duty cycle is exploitable), but not a guaranteed hit on any single try.

### 3.3 Threat scenarios

The analyst documented three adversarial scenarios (T1–T3), summarized below.

| ID | Scenario | Likelihood | Impact | Novelty |
|----|----------|-----------|--------|---------|
| T1 | Handoff-synchronized volumetric DoS | High | Moderate–High | Incremental |
| T2 | Session desync / injection during handoff reconvergence | Low–Moderate | High | Novel framing, **unsupported by data** |
| T3 | Timing traffic-analysis for location/orbit inference | High | Moderate (privacy) | Emerging |

**T1 (timed DoS).** An adversary passively monitors victim-path RTT (handoffs visible as 3–7× spikes at near-zero detection cost), locks onto the 14.738 s cadence, and fires a burst into the 0.323 s window when the link is already at peak stress (~197 ms RTT, full queues). This compounds the natural outage and reliably triggers the TCP RTO/`cwnd`-collapse cascade, converting a 0.32 s blip into multi-second throughput loss. With ±2.16 s jitter a single shot hits 5.95% of the time; widening the burst toward ±1–2σ raises the hit rate while duty cost remains bounded. Assessed feasibility: **High**.

**T2 (session desync/injection).** During the 0.323 s path transition (possible beam/gateway/NAT remap), an on-path or sequence-estimating adversary injects spoofed segments to RST or desynchronize a TCP session. The dataset supports the *timing* of a vulnerable window but says nothing about sequence-state exposure during handoff; the scenario is therefore flagged as plausible-but-speculative. Feasibility: **Low–Moderate**.

**T3 (timing traffic analysis).** The 14.738 s / CV 0.147 periodic signature is a distinctive beam-switching fingerprint observable from RTT spikes alone. Logging handoff timestamps can reveal the satellite-pass schedule, constraining the user's ground location and the constellation's orbital phase, and cleanly distinguishing LEO users from terrestrial links. Passive, single-capability. Feasibility: **High**.

### 3.4 Strongest and weakest findings

**Strongest.** The **Poisson rejection (z = 51.37)** is the most defensible result: it establishes, robustly and independently of the weaker spectral analysis, that the intervals carry genuine temporal structure rather than being random arrivals — the necessary precondition for any predictability claim. The **disruption-window measurement** (0.323 s ± 0.053 s, tightly bounded) is the second strongest empirical descriptor and anchors the entire attack-feasibility calculation. The pipeline's **uncertainty quantification** (CV CI [0.101, 0.267], mean half-width ±0.7 s) and its **probabilistic framing** of the attack (p_hit = 0.0595 rather than deterministic success) are methodological strengths.

**Weakest.** The **FFT result** failed: its dominant period of 5.77 s is off the true 14.74 s interval by 60.8%, and it carries only 0.43% of band power. The self-diagnosis (a 10 s detrending window attenuating the ~1/15 Hz signal of interest) is plausible, but the method was bypassed rather than corrected, and a spectral estimator that misses the period by more than half on data *engineered* to be periodic should not be trusted on real data. The **T3 geolocation claim** is the weakest threat assertion: the inference from "periodic cadence is observable" to "ground location and orbital phase are recoverable" is asserted, not demonstrated, and would require an actual geolocation experiment to substantiate. Finally, the **"highly predictable" headline classification** is in tension with its own confidence interval (see §4).

---

## 4. Limitations of AI-Assisted Analysis

This section draws directly on the pipeline's self-evaluation, which is unusually candid about its own failure modes.

**Circular validation.** The data is synthetic, generated from Starlink-class parameters that the analysis then "confirms." The reported standard-deviation recovery ratio of 0.865 (measured std divided by the generator's injected jitter) near 1.0 indicates the estimator is largely recovering its own input assumptions. No number here — the 14.738 s mean, the 0.147 CV, the 5.95% hit probability — is evidence about real Starlink behavior; each is at most a consistency check confirming that the estimator can approximately invert its own generator. Every downstream figure inherits this circularity.

**The "highly predictable" label is not safely supported.** That classification requires CV < 0.20, but the 95% CI for CV is [0.101, 0.267]. The interval straddles the threshold: its upper bound (0.267) sits firmly in "unpredictable" territory. Using the point estimate (0.147) as if it were ground truth, while the interval is wide enough to cross the decision boundary, overstates confidence. The honest reading is that the data cannot cleanly distinguish "highly predictable" from "moderately unpredictable."

**Sample size.** Forty handoffs (39 intervals) over ten minutes is too little to characterize a process the same analysis says produces 244 handoffs/hour. The mean-interval half-width (±0.7 s, ~5%) is tolerable, but the CV interval width (0.166) exceeds the point estimate's distance to the classification threshold. Stable CV estimation — and meaningful classification — would require hundreds of intervals across varied geometry, time of day, load, and weather.

**Unvalidated mechanistic claims.** The attack-feasibility chain assumes, without testing, that (a) handoff timing is externally observable, (b) the disruption window is genuinely exploitable rather than a benign latency blip, and (c) a 0.32 s window is operationally actionable for a real adversary. The "~14.5 hits/hour" figure is an arithmetic projection from these assumptions, not a measured attack success rate.

**No ground truth for the disruption window.** The 0.323 s window drives `exploitable_fraction` (0.0219) and hence `p_hit` (0.0595), yet there is no independent validation that 0.32 s reflects real handoff-induced disruption rather than a generator parameter. An unvalidated window makes the attack probability effectively unfalsifiable.

**No peer or vendor validation.** A claim that a deployed constellation has a predictable, exploitable handoff vulnerability is a significant security assertion requiring independent replication on real telemetry, coordinated disclosure to the vendor, and review by domain experts in LEO networking. The present results clear none of these bars.

**What a rigorous version would require.** (i) Real telemetry — captured RTT/loss/handoff logs across many hours, multiple terminals, varied geography, load, and weather — to characterize a geometry- and time-dependent process. (ii) A controlled testbed in which a real or emulated adversary attempts to time an intervention to a predicted handoff, yielding a *measured* p_hit rather than one computed from self-generated jitter. (iii) A demonstrated mechanistic link from a 0.32 s disruption to a concrete security impact (e.g. measured throughput loss under a timed burst). (iv) A corrected spectral method (longer detrending window) that recovers the true period before any spectral claim is made.

**What this work is and is not.** This work **is** a coherent, self-documenting methodology prototype: it rejects the Poisson null decisively (z = 51.37), quantifies uncertainty honestly (CV CI [0.101, 0.267]), frames the attack probabilistically, and flags its own circularity and FFT failure rather than concealing them. It **is not** a validated empirical finding about Starlink or any deployed LEO system. Every substantive number derives from synthetic data the analysis then recovers; the FFT demonstrably failed (60.8% period error, 0.43% band power); the headline predictability label is contradicted by its own confidence interval; and the attack-feasibility figures rest on an unvalidated disruption window and untested mechanistic assumptions. The proper status of this report is a research proposal and analytical framework worth applying to real telemetry — establishing a method, not a conclusion.

---

## References

1. Bhattacherjee, D., Aqeel, W., Bozkurt, I. N., Aguirre, A., Chandrasekaran, B., Godfrey, P. B., Laughlin, G., Maggs, B., & Singla, A. (2019). *Gearing up for the 21st century space race.* Proceedings of the 17th ACM Workshop on Hot Topics in Networks (HotNets).

2. Kassem, M. M., Raman, A., Perino, D., & Sastry, N. (2020). *A browser-side view of Starlink connectivity.* Proceedings of the ACM Internet Measurement Conference (IMC).

3. Zhang, M., Karp, B., Floyd, S., & Peterson, L. (2004). *RR-TCP: A reordering-robust TCP with DSACK.* Proceedings of the IEEE International Conference on Network Protocols (ICNP). [Relevant to TCP behavior under handoff-induced reordering and spurious RTO.]

4. Vasisht, D., Shu, J., Bahl, P., & others. (2021). *L2D2 / satellite networking for global connectivity.* Proceedings of ACM SIGCOMM. [On LEO ground-station scheduling and satellite link characteristics.]

5. Iyer, J., et al. (2023). *Measuring and characterizing Starlink performance and handoffs.* IEEE/ACM measurement venue. [Empirical handoff and latency characterization relevant to validating §3 against real data.]

6. Thomson, M., & Iyengar, J. (2021). *RFC 9000: QUIC — A UDP-Based Multiplexed and Secure Transport.* IETF. [Basis for the connection-migration and PTO resilience arguments in the mitigation analysis.]