---
phase: 11
slug: experiment-logging-private-store
status: verified
threats_open: 0
threats_total: 11
threats_closed: 11
asvs_level: 1
created: 2026-06-04
---

# Phase 11 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verification-only pass (no implementation files modified). Implementation files
> are the source of truth; every declared mitigation cites concrete `file:line`
> evidence. Source threat models: `11-01-PLAN.md`, `11-02-PLAN.md`, `11-03-PLAN.md`
> `<threat_model>` blocks. Test suite: 276 passed / 2 pre-existing yaml-soft-dep skips.
> Code review cross-reference: `11-REVIEW.md` (WR-02/03/04 assessed as noted residuals below).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| caller → `log_experiment` | An external eval script or the CLI hands in a validated `ExperimentRecord` + target store dir | Experiment record (may contain raw model output / PII) |
| user CLI → `experiment_log` | User supplies a `--from` JSON path and/or scalar flags; untrusted file content crosses here | Arbitrary JSON file content |
| process → filesystem | One JSON file written under the user-home experiment store | Serialized experiment record |
| outbox file → `publish` | A misplaced/hostile `model_experiment` file could sit in the outbox | Raw record dicts read for community PR |
| disk store → community paths | The private experiment store must never be read by browse/download or globbed by publish | (must not cross) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (evidence file:line) | Status |
|-----------|----------|-----------|-------------|----------------------------------|--------|
| T-11-01 | Information Disclosure | `log_experiment` write target (D-13 structural guard) | mitigate | `experiment_store.py:72-76` `resolved = store_dir.resolve(); if resolved.name != "experiments": raise ValueError`. Test `test_experiment_store.py:123-130` (`test_refuses_outbox_dir`) | closed (residual noted) |
| T-11-02 | Tampering / Integrity | torn write on crash leaves corrupt JSON | mitigate | `experiment_store.py:95-102` `mkstemp` → `os.fdopen` write → `os.replace`; `except BaseException: unlink(missing_ok=True); raise`. Test `test_experiment_store.py:90-100` (`test_atomic_write`) | closed |
| T-11-03 | Tampering (path traversal) | `record_id`-derived filename | mitigate | `schema.py:454-467` `record_id = kajiba_exp_<12hex>` (SHA-256 hex only); filename built `experiment_store.py:83` `exp_{record_id}.json`, never user-supplied | closed |
| T-11-04 | Information Disclosure | raw PII stored at log time (no scrub this phase) | accept | Private/no-publish store; scrub deferred to Phase 12 — see Accepted Risks | closed (accepted) |
| T-11-05 | Tampering | malformed / hostile `--from` JSON | mitigate | `cli.py:870` `json.loads` (no eval); `:884` `load_record`; `:885-886` `ClickException` on non-`ExperimentRecord`; overrides applied to raw dict pre-validation `:873-882` so field validators fire | closed (residual noted) |
| T-11-06 | Information Disclosure | CLI writing an experiment outside the private store | mitigate | `cli.py:932` `log_experiment(rec, EXPERIMENTS_DIR)` is the only write; CLI never opens the file itself; relies on T-11-01 guard. `EXPERIMENTS_DIR` at `cli.py:68` | closed |
| T-11-07 | Denial of Service | interactive prompt hangs automated callers | accept | `--from`/full-scalar paths non-interactive (`cli.py:868-907`); interactive fallback is intentional HITL; tests use scripted `input=` — see Accepted Risks | closed (accepted) |
| T-11-08 | Information Disclosure | experiment record reaching the community publish path | mitigate | Defense in depth: structural `OUTBOX_DIR`-only glob (`cli.py:112`) + active skip `cli.py:1673-1678` (`record_kind == "model_experiment"` → notice + `continue`). Tests `test_experiment_exclusion.py:103,122` | closed |
| T-11-09 | Information Disclosure | experiment routed into submit/staging | mitigate | `cli.py:491-494` defensive `if getattr(record, "record_kind", "coding_session") == "model_experiment": raise click.ClickException` (Assumption A2: structurally unreachable today) | closed |
| T-11-10 | Tampering | experiment dict fed to `KajibaRecord` validator | mitigate | `cli.py:1673` raw-dict `data.get("record_kind")` check + `continue` BEFORE `validate_record(data)` at `:1680` | closed |
| T-11-SC | Tampering (supply chain) | npm/pip/cargo installs | accept | Zero new dependencies (stdlib + pinned pydantic/click/rich) — see Accepted Risks | closed (accepted) |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date | Review Trigger |
|---------|------------|-----------|-------------|------|----------------|
| AR-11-01 | T-11-04 | Raw (un-scrubbed) PII may be written into the experiment store at log time. The store is private and never published (T-11-08), so PII never leaves the machine; experiment-aware scrubbing is deliberately deferred to Phase 12. | user (2026-06-04) | 2026-06-04 | Re-open when Phase 12 (experiment-aware scrub) lands — verify a scrub pass runs before/at log time. |
| AR-11-02 | T-11-07 | The interactive `kajiba experiment log` fallback uses `click.prompt`, blocking an automated caller that supplies neither `--from` nor the full scalar set. Interactive mode is intentional HITL convenience, not an automation surface; non-interactive paths exist and tests script `input=`. | user (2026-06-04) | 2026-06-04 | Re-assess only if a non-interactive automation contract is added for the bare `log` invocation. |
| AR-11-03 | T-11-SC | A compromised dependency could enter via the install chain. Phase 11 adds zero new dependencies (stdlib + already-pinned pydantic/click/rich). | user (2026-06-04) | 2026-06-04 | Re-evaluate in any phase that adds a new third-party dependency. |

---

## Residual Risks (CLOSED-with-note)

Mitigations are present and verified (threat CLOSED), but code review surfaced bounded
weaknesses worth recording. They do not reopen the threat because the declared mitigation
exists and the exploit path is not currently reachable.

- **T-11-01 — leaf-name-only guard (`11-REVIEW.md` WR-04).** The D-13 guard checks
  `resolved.name != "experiments"` (`experiment_store.py:73`) but does not assert the path
  is under `KAJIBA_BASE`/`~/.hermes`. A caller-supplied `/anywhere/experiments` dir passes.
  The declared mitigation — "an experiment can never land in `STAGING_DIR`/`OUTBOX_DIR`" —
  **holds** (those leaves are not named `experiments`) and the only production caller passes
  the real `EXPERIMENTS_DIR` (`cli.py:932`). Residual is a weaker-than-documented guarantee
  against arbitrary misplacement by a programmatic ELOG-02 caller, not a community-namespace
  leak. Recommend asserting descendant-of-`KAJIBA_BASE` (tracked in the CR-01 follow-up todo).

- **T-11-05 — malformed-JSON / missing-discriminator error UX (`11-REVIEW.md` WR-02, WR-03).**
  Hostile/malformed `--from`/`--local-model` content is rejected (no `eval`; Pydantic validates;
  non-experiment records raise `ClickException`), so the tampering threat is mitigated. But a
  non-JSON file (`JSONDecodeError`, `cli.py:866,870`) or an experiment file omitting `record_kind`
  (raw `ValidationError` before the `isinstance` check, `:884-886`) surfaces as an unhandled
  traceback rather than a friendly message. Fail-closed (input still refused) — error-UX defect,
  not a bypass. Recommend wrapping `json.loads`/`load_record` in `try/except` in a future phase.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-04 | 11 | 11 | 0 | gsd-security-auditor (verification-only) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
