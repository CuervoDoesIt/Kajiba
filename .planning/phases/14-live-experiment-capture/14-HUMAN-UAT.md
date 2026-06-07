---
status: partial
phase: 14-live-experiment-capture
source: [14-VERIFICATION.md]
started: 2026-06-07T00:59:50Z
updated: 2026-06-07T00:59:50Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live Hermes v0.15.x experiment-capture end-to-end (SC#1)
expected: Run a multi-turn-then-exit evaluation session in live Hermes v0.15.x with `KAJIBA_EXPERIMENT=1` (recommended on the DGX Spark, the Kajiba lab). After the session ends, confirm exactly ONE `exp_*.json` exists in `EXPERIMENTS_DIR` (`~/.hermes/kajiba/experiments/`) and that NOTHING was written to `STAGING_DIR`/`OUTBOX_DIR`. The captured record should carry real runtime metadata (model name/quant via `ollama.show()` when local) and a populated trajectory, structurally matching a deliberately-logged `kajiba experiment log` record.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
