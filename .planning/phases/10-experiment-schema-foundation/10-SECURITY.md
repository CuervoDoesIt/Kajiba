---
phase: 10
slug: experiment-schema-foundation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-03
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Each declared threat mitigation is verified against the implemented code (not against documentation or intent).

**Audited:** 2026-06-03 · **ASVS Level:** 1 · **Phase base commit:** e1bae76
**Disposition:** SECURED — 4/4 `mitigate` threats CLOSED; 5 `accept` threats logged

The phase is schema-only (Pydantic models + a manual dispatch factory + the golden-baseline tooling and tests). No network endpoint, auth path, or publish/browse/download path was introduced.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| repo fixtures → capture script | Trusted in-repo JSON read by a local script; no network, no external input, no secrets | Public, PII-free test trajectories |
| raw JSON dict → schema models | Untrusted-shaped `json.loads` dict crosses into Pydantic validation via `validate_record` / `load_record`; Pydantic is the validation gate | Local record JSON the user already owns |
| privacy boundary: experiment vs community records | `ExperimentRecord` carries richer model/hardware metadata, is private/no-publish (ELOG-03, later phases); this phase declares schema only and adds no publish path | Local-only experiment metadata |
| test code → schema models | Test-only code constructing/validating in-memory models from in-repo fixtures | Public, PII-free test data |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-10-01 | Tampering | `golden_ids.json` baseline integrity | mitigate | Reproducible committed script `tests/capture_golden_ids.py` (glob L37, `trajectory`-key guard L41-43, hash compute L45-49) derives the baseline; committed (`85b3866`) BEFORE any schema edit (`fa0d4bf`/`05d08ec`/`89152eb`). Re-running against the current schema reproduces `golden_ids.json` byte-identically (verified live). `tests/test_schema_backcompat.py:36-42` reads it as ground truth and passes for all 5 fixtures. | closed |
| T-10-03 | Tampering | controlled-vocabulary bypass (`record_kind`, `experiment_type`, `recommended_action`) | mitigate | Scalar `Literal` types `RecordKindType` (schema.py L112), `ExperimentTypeType` (L115), `RecommendedActionType` (L118) make Pydantic auto-reject out-of-vocab scalars. Rejection asserted in `tests/test_schema_experiment.py:64-83` (`pydantic.ValidationError` raised); tests pass. | closed |
| T-10-06 | Information Disclosure | ExperimentRecord richer model/hardware metadata must stay private | mitigate | Phase is schema-only — grep for publish/browse/download/upload/huggingface/http finds only docstring text (schema.py L436, L474), no code path. Private namespace distinguishable via `record_kind` discriminator (`model_experiment` L440 vs `coding_session` L278) and id prefix `kajiba_exp_` (L466) vs `kajiba_` (L376). SUMMARY Threat Flags confirm "None". | closed |
| T-10-07 | Tampering | regression detection (the tests ARE the integrity control) | mitigate | Both integrity-control modules pass (20 tests): golden-hash tripwire `test_schema_backcompat.py::test_record_id_and_submission_hash_stable` (parametrized over all 5 keys) + vocab-bypass detectors in `test_schema_experiment.py`. Run on every commit/wave merge per VALIDATION.md sampling. | closed |
| T-10-02 | Information Disclosure | public fixture content | accept | See Accepted Risks Log. | closed |
| T-10-04 | Denial of Service | malformed/oversized record JSON during `load_record`/`validate_record` | accept | See Accepted Risks Log. | closed |
| T-10-05 | Spoofing / Repudiation | hash forgery/collision on `submission_hash` (local dedup) | accept | See Accepted Risks Log. | closed |
| T-10-08 | Information Disclosure | test fixtures / golden baseline | accept | See Accepted Risks Log. | closed |
| T-10-SC | Tampering | npm/pip/cargo installs | accept | See Accepted Risks Log. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Verification Method Notes

- **T-10-01 re-derivation:** the committed `golden_ids.json` was reproduced byte-for-byte by replaying the capture-script logic against the **current (post-refactor)** schema — the strongest possible confirmation of ESCH-04 (post-refactor schema yields the exact pre-refactor hashes). The committed file was never overwritten.
- **T-10-03 / T-10-07:** rejection confirmed by *running* the suite, not by reading `Literal` definitions alone — `pydantic.ValidationError` is actually raised.
- **T-10-06:** publish-absence confirmed by grep matching only docstring text, not code.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-02 | T-10-02 | Fixtures are public, PII-free test data already in the repo; the capture script only hashes already-committed content. No new fixtures with secrets introduced this phase. | gsd-security-auditor | 2026-06-03 |
| AR-10-04 | T-10-04 | Local-first, network-free pipeline operating on files the user already owns; no remote attacker. Pydantic bounds typed fields. ASVS L1 — no untrusted network input. No network code added. | gsd-security-auditor | 2026-06-03 |
| AR-10-05 | T-10-05 | `submission_hash` is a local de-dup key, not an auth/integrity token; experiment records never publish (D-06). SHA-256 collision infeasible; a forged dup only affects local dedup. | gsd-security-auditor | 2026-06-03 |
| AR-10-08 | T-10-08 | `golden_ids.json` and fixtures are public, PII-free test data. | gsd-security-auditor | 2026-06-03 |
| AR-10-SC | T-10-SC | No commit since base `e1bae76` touched `pyproject.toml` (verified via `git log e1bae76..HEAD`). Dependency list unchanged: `pydantic>=2.0`, `click>=8.0`, `rich>=13.0`; optional extras pre-existing. Dependencies did NOT grow. | gsd-security-auditor | 2026-06-03 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-03 | 9 | 9 | 0 | gsd-security-auditor |

### Unregistered Flags

None. SUMMARY.md `## Threat Flags` declares "None" and the audit found no new attack surface (no network endpoint, auth path, or publish path) introduced during implementation.

### Implementation Files

Implementation files were treated as READ-ONLY and not modified during this audit.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-03
