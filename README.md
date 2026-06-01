# LEO Handoff Security Agent

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
| `reports/handoff_detection.json` | 40 events, mean interval 14.74s ± 2.16s |
| `reports/predictability_analysis.json` | CV=0.147 (highly predictable), disruption window 0.323s, P(hit)=5.9% |
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
```
