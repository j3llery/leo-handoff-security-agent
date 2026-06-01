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

**Results:** 40 handoff events over 10.0 min.
Mean interval: 14.74s ± 2.16s.

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

**Dead end — FFT:** Dominant period 5.77s
vs. expected ~14.7s (61% error). Root cause: 10s detrending
window attenuates the target frequency. Noted as a methodological weakness
(documented in Phase 4); interval-level statistics used as primary evidence.

**Results:** CV=0.147 (highly predictable). Disruption window
0.323s. P(hit): 5.9%.
Expected 14 hits/hour.

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
