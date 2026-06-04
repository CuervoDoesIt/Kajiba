---
phase: 12
slug: eval-scoring-scrub-tuning
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-04
---

# Phase 12 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Eval confidence scorer (`eval_scorer.py`), experiment-aware PII scrub
> (`experiment_scrub.py`), and CLI wiring (`experiment score`/`scrub`, Confidence
> column, `_load_experiment` guard). Register authored at plan time across all four
> PLANs; this audit verifies each declared mitigation exists in the implemented code
> with a concrete file:line match (FORCE stance — every mitigation assumed absent
> until proven present).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| fixture / store JSON → `load_record()` | Untrusted-shaped JSON parsed by Pydantic; malformed/non-experiment records must fail at validation, not silently mis-load | Experiment record JSON (may contain PII) |
| user CLI arg (`record_id`) → store path | Untrusted `<id>` string used to construct a filesystem path; must be constrained to `EXPERIMENTS_DIR` | Filename fragment |
| raw `ExperimentRecord` (private store) → `scrub_experiment` → shareable copy | Share-boundary transform; free text scrubbed out, model/hardware identity deliberately preserved | Free-text PII out; model_hash/hardware preserved |
| scrubbed output → stdout / `--out` file | Scrub fires at the share boundary; the raw `exp_<id>.json` must never be overwritten (D-08) | Scrubbed record JSON |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-12-01 | Tampering | `tests/fixtures/experiment_pii.json` | mitigate | Fixture carries a REAL 64-hex `model_hash` + real GPU name so Plan 03's preservation test cannot pass vacuously — verified `model_hash="deadbeef…eeff11"` is 64 hex chars (`experiment_pii.json:12`) and `gpu_name="NVIDIA GeForce RTX 4070"` (`experiment_pii.json:23`) | closed |
| T-12-02 | Information Disclosure | RED test design (inline PII in fixtures) | accept | Inline PII in private test fixtures, never published (experiments are no-publish per D-08 / ELOG-03) — see AR-12-02 | closed |
| T-12-SC | Tampering (supply chain) | npm/pip/cargo installs | accept | Phase installs ZERO packages (`tech-stack.added: []` in all four SUMMARYs) — see AR-12-SC | closed |
| T-12-03 | Tampering (schema drift) | `eval_scorer` reads `ExperimentRecord` | mitigate | Read-only / compute-on-read (D-03): grep found NO assignment to any `record.*` attribute and NO persistence call in `eval_scorer.py`; sub-scores only read `record.outcome.*` / `record.experiment.*` / `record.hardware.*` and return a new `EvalConfidenceResult` (`eval_scorer.py:65-210`) | closed |
| T-12-04 | Information Disclosure (band/score confusion) | confidence band vs eval_score | mitigate | Distinct band vocabulary `complete`/`partial`/`thin` (`eval_scorer.py:199-204`); grep for `gold\|silver\|bronze\|review_needed` in `eval_scorer.py` → **zero matches** (forbidden tier words also stripped from docstring per 12-02 SUMMARY) | closed |
| T-12-07 | Repudiation/Logging | `eval_scorer` logger usage | mitigate | grep for `logger.(info\|debug\|warning\|error\|exception)` in `eval_scorer.py` → **zero matches**; the scorer reads `local_model_output` but never logs it (logger declared at `eval_scorer.py:23`, never invoked) | closed |
| T-12-05 | Information Disclosure | free-text allowlist | mitigate | All FIVE caller-supplied free-text surfaces routed through `scrub_text` via the `_apply` closure: `task_category` (`experiment_scrub.py:82`), `task_description` (:83), `local_model_output` (:84), `reviewer_critique` (:87-88), `lessons_learned[]` per-element (:91-93). CR-01 expansion (4→5 surfaces) verified present. **Residual:** the shared `scrubber.py` `api_keys` regex `sk-[a-zA-Z0-9]{32,}` (`scrubber.py:71`) misses `sk-live-…` keys (internal hyphen) — declared control is present but partially effective; see AR-12-01 | closed |
| T-12-06 | Tampering (over-scrub destroys analysis fields) | model_hash / hardware preservation | mitigate | Field allowlist NOT pattern denylist (D-06): `model`/`hardware`/`model_hash`/`experiment_id` never touched (`experiment_scrub.py:95-97`). grep for `import privacy` / `from kajiba.privacy` / `anonymize_hardware\|generalize_gpu_name\|round_to_tier\|apply_consent_level` → only prose docstring (`:19`) + comment (`:97`), NO import and NO call (D-05 honored) | closed |
| T-12-08 | Information Disclosure (raw PII at rest) | store-raw invariant | accept | AR-11-01 accepted at rest in the private no-publish store (D-08); `scrub_experiment` deep-copies via `model_dump` and rebuilds via `model_validate` (`experiment_scrub.py:59,115`) — returns a copy, never overwrites the raw store — see AR-12-08 | closed |
| T-12-09 | Repudiation/Logging | `experiment_scrub` logger usage | mitigate | Single `logger.info` (`experiment_scrub.py:113`) logs `len(counts)` (an integer category count) with `%s` lazy formatting; no raw `local_model_output`/`reviewer_critique` is logged | closed |
| T-12-10 | Tampering (path traversal) | `_load_experiment(record_id)` | mitigate | `path = EXPERIMENTS_DIR / f"exp_{record_id}.json"` then `if path.resolve().parent != EXPERIMENTS_DIR.resolve(): raise click.ClickException(...)` before any read (`cli.py:106-110`) | closed |
| T-12-11 | Tampering / DoS (malformed record) | experiment score/scrub on bad JSON | mitigate | `load_record` wrapped in try/except → clean `ClickException`, no traceback (`cli.py:115-120`); `if not isinstance(rec, ExperimentRecord): raise click.ClickException(...)` (`cli.py:123-126`) | closed |
| T-12-12 | Information Disclosure (raw PII at rest overwrite) | experiment scrub `--out` / preview | mitigate | WR-02 guard on the WRITE path: `out_path = Path(out).resolve()` then `if out_path == store_root or store_root in out_path.parents: raise click.ClickException(...)` BEFORE `out_path.write_text(...)` (`cli.py:1117-1124`); preview renders SCRUBBED text only (`cli.py:1137`, 1153-1156) | closed |
| T-12-13 | Information Disclosure (confidence/score confusion) | experiment list / score render | mitigate | `list` declares distinct `"Score"` (eval_score) and `"Confidence"` (band) columns (`cli.py:1012-1013`), rendered in separate cells (`cli.py:1037-1038`); `score` renders the band table then a separate "Confidence vs. answer quality" panel surfacing `eval_score` distinctly (`cli.py:1063-1081`) | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-12-02 | T-12-02 | Test fixtures embed inline PII strings (emails, paths, an API-key-shaped token) as scrub/preservation proof inputs. They live under `tests/fixtures/` and never flow to any community/publish path — experiments are no-publish (D-08 / ELOG-03). Accepted as private test data. | c0derj0e (plan-time) | 2026-06-04 |
| AR-12-SC | T-12-SC | Phase 12 installs ZERO third-party packages. All four plan SUMMARYs record `tech-stack.added: []`. No supply-chain surface introduced. Accepted as not-applicable. | c0derj0e (plan-time) | 2026-06-04 |
| AR-12-08 | T-12-08 | Raw PII is retained at rest in the private, no-publish experiment store (`exp_<id>.json`). This is the deliberate store-raw / scrub-at-export design (D-08, inherited AR-11-01): `scrub_experiment` returns a scrubbed COPY and never overwrites the raw store; the share-boundary export-write gate is Phase 15. Accepted at rest in the private store. | c0derj0e (plan-time) | 2026-06-04 |
| AR-12-01 | T-12-05 / T-12-12 (residual) | The declared T-12-05 control (route all 5 free-text surfaces through `scrub_text`) IS present and verified, but the SHARED `scrubber.py` `api_keys` regex `sk-[a-zA-Z0-9]{32,}` (`scrubber.py:71`) does not match `sk-live-…` style keys with an internal hyphen, so such a token survives the scrub and would be echoed verbatim by the `experiment scrub` preview panel (`cli.py:1153-1156`). Empirically confirmed: `task_description` email → `[REDACTED_EMAIL]` but `sk-live-AbCdEf1234567890XyZqrStUvWx` survives. Root cause is the shared community regex layer; widening it is explicitly DEFERRED out of Phase 12 scope per D-09 (Phase 12 reuses the shared engine verbatim, must not fork it) and is formally tracked in `.planning/phases/12-eval-scoring-scrub-tuning/deferred-items.md` (suggested fix `sk-[a-zA-Z0-9_-]{20,}` with regression tests, owner = a scrubber-hardening pass). This is a residual information-disclosure weakness accepted ONLY because experiments are no-publish at rest (AR-12-08) and the actual share-boundary export is Phase 15 — it MUST be resolved (regex widened + `sk-live-` redaction regression test) before any experiment-share/export capability ships. Mirrors review findings WR-01 / IN-02 (OPEN code-quality, deferred). | c0derj0e | 2026-06-04 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-04 | 14 | 14 | 0 | gsd-security-auditor (Claude) |

Notes:
- 11 `mitigate` threats verified by concrete file:line grep/read matches (T-12-01, T-12-03, T-12-04, T-12-05, T-12-06, T-12-07, T-12-09, T-12-10, T-12-11, T-12-12, T-12-13).
- 3 `accept` threats (T-12-02, T-12-SC, T-12-08) documented in the Accepted Risks Log above.
- 1 residual (AR-12-01) recorded as an accepted-with-conditions risk: the declared mitigation exists; the partial-effectiveness regex gap is out of Phase-12 scope per D-09, formally tracked in `deferred-items.md`, and gated to be closed before any experiment-export ships. Not a Phase-12 blocker because experiments are no-publish at rest.
- No unregistered threat flags: 12-03 SUMMARY `## Threat Flags` = "None"; the 12-04 sk-live discovery maps to existing T-12-05/T-12-12 (recorded as AR-12-01), not net-new attack surface.
- Prior code review CR-01 (5th scrub surface) and WR-02 (`--out` store-clobber guard) confirmed RESOLVED and present in code (`experiment_scrub.py:82`; `cli.py:1117-1124`).

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-04
