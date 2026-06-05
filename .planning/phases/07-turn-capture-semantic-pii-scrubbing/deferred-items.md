# Deferred Items — Phase 07

Out-of-scope discoveries logged during execution. NOT fixed by the owning plan.

## From 07-03 (turn capture + hook dispatch)

- **`tests/test_scrubber_semantic.py` — 8 RED tests failing.** These are RED
  scaffolds committed by plan 07-02 (`2c8ded3`) that pin the `kajiba.scrubber_semantic`
  module (GLiNER semantic PII, PRIV-01/02/03). That module is the deliverable of the
  sibling Wave 2 plan **07-04**, not 07-03. 07-03 only modifies `collector.py` and
  `plugin/hooks.py`. These failures are expected RED until 07-04 lands and are out of
  scope here. Do NOT fix in 07-03.
