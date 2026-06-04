# Testing Patterns

**Analysis Date:** 2026-03-30

## Test Framework

**Runner:**
- pytest >= 7.0
- Config: `pyproject.toml` section `[tool.pytest.ini_options]`
- Test paths: `tests/`
- Default addopts: `-v` (verbose output)

**Assertion Library:**
- Built-in `assert` statements (pytest rewriting)
- `pytest.raises` for exception testing

**Coverage:**
- pytest-cov >= 4.0
- Config: `pyproject.toml` section `[tool.coverage.run]`
- Source: `["kajiba"]`
- Omit: `["tests/*"]`

**Run Commands:**
```bash
pytest tests/ -v                                  # Run all tests (default via addopts)
pytest tests/ -v --cov=kajiba --cov-report=term-missing  # Run with coverage (Makefile target)
make test                                          # Alias for above
pytest tests/test_schema.py -v                     # Run single module
pytest tests/test_schema.py::TestValidRecords -v   # Run single class
pytest tests/test_schema.py::TestValidRecords::test_gold_tier_record -v  # Run single test
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (not co-located with source)
- Fixtures in `tests/fixtures/` subdirectory

**Naming:**
- Test files: `test_<source_module>.py` -- one test file per source module
- Test classes: `Test<DescriptiveName>` grouping related tests
- Test methods: `test_<what_is_being_tested>(self) -> None`

**Structure:**
```
tests/
├── __init__.py              # Empty (makes tests a package)
├── fixtures/
│   ├── adversarial_trajectory.json
│   ├── gold_trajectory.json
│   ├── minimal_trajectory.json
│   ├── pii_trajectory.json
│   └── silver_trajectory.json
├── test_cli.py              # CLI smoke tests (84 lines)
├── test_collector.py        # Collector lifecycle tests (212 lines)
├── test_schema.py           # Schema validation tests (260 lines)
├── test_scorer.py           # Quality scoring tests (292 lines)
└── test_scrubber.py         # PII scrubber tests (314 lines)
```

**Mapping (test file -> source module):**
| Test File | Source Module | Focus |
|-----------|-------------|-------|
| `tests/test_schema.py` | `src/kajiba/schema.py` | Validation, export methods, record IDs, controlled vocabularies |
| `tests/test_scrubber.py` | `src/kajiba/scrubber.py` + `src/kajiba/scrubber_llm.py` | PII pattern detection, record scrubbing, false positives, LLM stub |
| `tests/test_scorer.py` | `src/kajiba/scorer.py` | Quality tiers, sub-scores, edge cases |
| `tests/test_collector.py` | `src/kajiba/collector.py` | Session lifecycle, hardware detection, fault tolerance |
| `tests/test_cli.py` | `src/kajiba/cli.py` | CLI command smoke tests |

**Not tested:**
- `src/kajiba/hermes_integration.py` -- no dedicated test file

## Test Structure

**Suite Organization:**
Tests use classes to group related test methods by theme. Each class has a docstring.

```python
# Pattern from tests/test_schema.py
class TestValidRecords:
    """Test that valid records parse without error."""

    def test_gold_tier_record(self) -> None:
        """A fully-populated gold-tier record validates successfully."""
        data = _load_fixture("gold_trajectory.json")
        record = validate_record(data)
        assert record.schema_version == SCHEMA_VERSION
        assert record.trajectory.turn_count == 10

    def test_minimal_record(self) -> None:
        """A minimal record (trajectory only, no optional sections) validates."""
        data = _load_fixture("minimal_trajectory.json")
        record = validate_record(data)
        assert record.model is None
```

**Class grouping patterns observed across test files:**
- `TestValidRecords` / `TestValidationFailures` -- positive and negative validation
- `TestFilePathScrubbing` / `TestApiKeyScrubbing` / `TestEmailScrubbing` etc. -- one class per PII category
- `TestFalsePositives` -- things that should NOT be caught
- `TestRecordScrubbing` -- full-record integration tests
- `TestQualityTiers` / `TestCoherenceScore` / `TestToolValidityScore` etc. -- one class per sub-score
- `TestEdgeCases` -- boundary conditions
- `TestCollectorLifecycle` / `TestCollectorFaultTolerance` -- behavior categories
- `TestCLIBasics` / `TestPreviewCommand` / `TestHistoryCommand` etc. -- one class per CLI command

**Method signature pattern:**
- All test methods have return type annotation `-> None`
- All test methods have a one-line docstring
- Instance methods on classes (use `self`) -- no standalone test functions except helpers

**Setup/teardown:**
- No `setUp`/`tearDown` methods or `@pytest.fixture` with `autouse=True`
- Each test is independent and self-contained
- Fixture data loaded per-test via `_load_fixture()` helper

## Fixtures and Test Data

**JSON Fixture Files:**

Each fixture represents a different quality tier or test scenario as a full `KajibaRecord` JSON:

| Fixture | Purpose | Key Characteristics |
|---------|---------|-------------------|
| `tests/fixtures/gold_trajectory.json` | Gold-tier record | 10 turns, 4 tool calls (all success), rating 5, full model/hardware/outcome/submission metadata, outcome tags: perfect |
| `tests/fixtures/silver_trajectory.json` | Silver-tier record | 4 turns, 2 tool calls (1 success, 1 failure), rating 3, model + outcome + submission but no hardware, outcome tags: task_completed + minor_hallucination |
| `tests/fixtures/minimal_trajectory.json` | Bare minimum valid record | 2 turns, 0 tool calls, no model/hardware/outcome/pain_points/submission sections |
| `tests/fixtures/pii_trajectory.json` | PII-laden record for scrubber testing | Contains file paths, emails, API keys, IP addresses, phone numbers, SSH keys, PEM certs, connection strings, JWT tokens across conversations, tool outputs, pain points, and user comments |
| `tests/fixtures/adversarial_trajectory.json` | Deliberately bad record | Non-alternating turns (human-human-gpt-gpt), empty values, tool call on human turn, mismatched tool counts, rating 5 with task_failed + hallucination tags |

**Fixture Loading Pattern:**

Every test module that uses fixtures defines the same helper:

```python
FIXTURES = Path(__file__).parent / "fixtures"

def _load_fixture(name: str) -> dict:
    """Load a test fixture JSON file."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
```

This helper is duplicated in `tests/test_schema.py`, `tests/test_scrubber.py`, and `tests/test_scorer.py`. It returns a raw `dict` so tests can mutate it before validation.

**Fixture Mutation Pattern:**

Tests that verify validation failures start from a valid fixture and mutate specific fields:

```python
# Pattern from tests/test_schema.py
def test_bad_rating_too_high(self) -> None:
    """Rating > 5 must fail."""
    data = _load_fixture("minimal_trajectory.json")
    data["outcome"] = {"user_rating": 6, "outcome_tags": []}
    with pytest.raises(ValidationError):
        validate_record(data)
```

**Record Factory Pattern:**

`tests/test_scorer.py` defines a `_make_record()` helper to build records programmatically with sensible defaults:

```python
def _make_record(**kwargs) -> KajibaRecord:
    """Build a KajibaRecord from keyword arguments with sensible defaults."""
    conversations = kwargs.pop("conversations", [
        ConversationTurn(**{"from": "human"}, value="Hello"),
        ConversationTurn(**{"from": "gpt"}, value="Hi there! How can I help you today?"),
    ])
    turn_count = kwargs.pop("turn_count", len(conversations))
    total_tc = kwargs.pop("total_tool_calls", 0)
    success_tc = kwargs.pop("successful_tool_calls", 0)
    fail_tc = kwargs.pop("failed_tool_calls", 0)

    trajectory = Trajectory(
        conversations=conversations,
        turn_count=turn_count,
        total_tool_calls=total_tc,
        successful_tool_calls=success_tc,
        failed_tool_calls=fail_tc,
    )
    return KajibaRecord(trajectory=trajectory, **kwargs)
```

**pytest Fixtures (function-scoped):**

Only one pytest fixture is defined, in `tests/test_cli.py`:

```python
@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
```

Used by all CLI test classes to get a Click `CliRunner` instance.

## Mocking

**Framework:** No mocking framework is used. No `unittest.mock`, `pytest-mock`, or `monkeypatch` usage detected.

**What is NOT mocked:**
- Hardware detection (`_detect_hardware()`) runs against the real system in `tests/test_collector.py`
- File system operations in CLI tests use real (potentially empty) staging/outbox directories
- No network calls exist in the codebase, so no network mocking needed

**Implications:**
- Tests are fast because the codebase has no external service dependencies
- Hardware detection tests verify "does not crash" rather than specific values since results vary by machine
- CLI tests are smoke tests that verify exit codes and basic output, not full behavior with staged data

## Test Types

**Unit Tests:**
- Schema validation: `tests/test_schema.py` -- validates Pydantic models accept/reject data correctly
- Scrubber text patterns: `tests/test_scrubber.py` -- individual regex categories against known inputs
- Sub-scores: `tests/test_scorer.py` -- each scoring function tested in isolation with known inputs
- These are pure functions with no side effects, no I/O

**Integration Tests:**
- Collector lifecycle: `tests/test_collector.py::TestCollectorLifecycle::test_full_session_lifecycle` -- simulates a full session start-to-export with turns, tool calls, rating, pain points; verifies the assembled record structure
- Record scrubbing: `tests/test_scrubber.py::TestRecordScrubbing` -- loads PII fixture, runs full scrub pipeline, verifies nested fields are all scrubbed
- Quality tiers: `tests/test_scorer.py::TestQualityTiers` -- loads fixtures, runs full composite scorer, verifies tier assignments

**Smoke Tests:**
- CLI: `tests/test_cli.py` -- invokes CLI commands via Click CliRunner and verifies exit code 0 and basic output content. Does not test with actual staged data.

**E2E Tests:**
- Not present. No end-to-end test that writes a file to staging, runs CLI commands, and verifies outbox output.

## Common Patterns

**Validation Error Testing:**
```python
# From tests/test_schema.py
def test_bad_rating_too_high(self) -> None:
    """Rating > 5 must fail."""
    data = _load_fixture("minimal_trajectory.json")
    data["outcome"] = {"user_rating": 6, "outcome_tags": []}
    with pytest.raises(ValidationError):
        validate_record(data)
```

**NotImplementedError Testing:**
```python
# From tests/test_scrubber.py
def test_raises_not_implemented(self) -> None:
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        scrub_semantic("some text", model_fn=lambda x: x)
```

**Assertion Patterns:**
- Direct value comparison: `assert record.schema_version == SCHEMA_VERSION`
- Membership check: `assert "perfect" in record.outcome.outcome_tags`
- None check: `assert record.model is None`
- Not-None check: `assert record.model is not None`
- Range check: `assert 0.0 <= result.composite_score <= 1.0`
- Threshold comparison: `assert score >= 0.9`, `assert score < 1.0`
- Substring absence: `assert "username" not in result.scrubbed_text`
- Set equality: `assert set(result.sub_scores.keys()) == {"coherence", "tool_validity", ...}`
- String prefix: `assert record_id.startswith("kajiba_")`

**Fault Tolerance Testing:**
```python
# From tests/test_collector.py
def test_turn_complete_with_bad_data(self) -> None:
    """on_turn_complete should not crash on bad data."""
    collector = KajibaCollector()
    collector.on_session_start("s5", {"model_name": "test"})
    # Missing required 'role' key -- should log error, not crash
    collector.on_turn_complete({"content": "missing role"})
    # The collector should still be functional after the error
    collector.on_turn_complete({"role": "human", "content": "Valid turn"})
    collector.on_turn_complete({"role": "gpt", "content": "Valid response"})
    collector.on_session_end("s5")
    record = collector.export_record()
    # Should have 2 valid turns (the bad one was skipped)
    assert record.trajectory.turn_count == 2
```

**CLI Testing Pattern:**
```python
# From tests/test_cli.py
@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()

class TestCLIBasics:
    def test_help(self, runner: CliRunner) -> None:
        """--help should show all commands."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "preview" in result.output
```

**Parametric Iteration (manual, not @pytest.mark.parametrize):**
```python
# From tests/test_scorer.py
def test_composite_score_range(self) -> None:
    """Composite score should always be between 0 and 1."""
    for fixture_name in [
        "gold_trajectory.json",
        "silver_trajectory.json",
        "minimal_trajectory.json",
        "adversarial_trajectory.json",
    ]:
        data = _load_fixture(fixture_name)
        record = validate_record(data)
        result = compute_quality_score(record)
        assert 0.0 <= result.composite_score <= 1.0
```

```python
# From tests/test_schema.py
def test_all_outcome_tags_valid_in_model(self) -> None:
    """Every tag in OUTCOME_TAGS should be accepted by the model."""
    data = _load_fixture("minimal_trajectory.json")
    for tag in OUTCOME_TAGS:
        test_data = {**data, "outcome": {"user_rating": 3, "outcome_tags": [tag]}}
        record = validate_record(test_data)
        assert tag in record.outcome.outcome_tags
```

Note: `@pytest.mark.parametrize` is not used anywhere. Tests that iterate over multiple inputs do so with explicit `for` loops inside a single test method.

## Coverage

**Requirements:** No enforced minimum coverage threshold. No `fail_under` setting in `pyproject.toml`.

**View Coverage:**
```bash
make test                                          # Runs with --cov=kajiba --cov-report=term-missing
pytest tests/ -v --cov=kajiba --cov-report=html    # Generate HTML report to htmlcov/
```

**Known Coverage Gaps:**
- `src/kajiba/hermes_integration.py` -- no test file exists; the `register_hooks()` function and HermesAgent protocol are untested
- `src/kajiba/scrubber_llm.py` -- only the `NotImplementedError` raise is tested; no actual LLM scrubbing logic (stub module)
- `src/kajiba/cli.py` -- only smoke tests (empty staging/outbox scenarios); no tests with actual staged records, export file verification, or submit confirmation flow
- Hardware detection in `src/kajiba/collector.py` -- tested for "does not crash" only; no mocking of `nvidia-smi` or `psutil`

## Adding New Tests

**For a new source module `src/kajiba/foo.py`:**
1. Create `tests/test_foo.py`
2. Add fixture loading if needed:
   ```python
   FIXTURES = Path(__file__).parent / "fixtures"
   def _load_fixture(name: str) -> dict:
       return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
   ```
3. Group tests into classes by theme: `TestFooBasic`, `TestFooEdgeCases`, `TestFooErrors`
4. Each test method: `def test_descriptive_name(self) -> None:`
5. Each test method: one-line docstring describing the assertion

**For a new fixture:**
1. Create `tests/fixtures/<descriptive_name>.json`
2. Must be a valid (or deliberately invalid) `KajibaRecord` JSON structure
3. Name should indicate the fixture's purpose: `gold_`, `minimal_`, `pii_`, `adversarial_`, `silver_`

---

*Testing analysis: 2026-03-30*
