# Contributing to Kajiba

Thank you for your interest in contributing to Kajiba!

## Getting started

1. Fork the repository
2. Clone your fork and install in development mode:
   ```bash
   pip install -e ".[all]"
   ```
3. Run the test suite to confirm everything works:
   ```bash
   pytest tests/ -v
   ```

## Pull request guidelines

- Keep PRs focused — one feature or fix per PR.
- Include tests for new functionality.
- All tests must pass before merge.
- Use type hints on all public functions and classes.
- Follow Google-style docstrings.
- Use `pathlib.Path` instead of `os.path`.

## Controlled vocabulary extensions

The outcome tags and pain point categories are controlled vocabularies defined in the schema. To propose a new tag or category:

1. Open an issue with the `schema` label describing:
   - The proposed tag/category name
   - What it means and when it should be used
   - Why the existing vocabulary doesn't cover this case
   - At least 2 example scenarios where this tag would be appropriate
2. The community discusses the proposal
3. If accepted, the tag is added in a patch version bump (no breaking change)

Do not submit PRs that add vocabulary terms without going through the issue process first.

## Code standards

- Python 3.11+ required
- Pydantic v2 (use `model_validator`, `field_validator`, not v1 decorators)
- Type hints everywhere (no `Any` types except where genuinely unavoidable)
- Use `logging` module, not `print()`
- Constants in `UPPER_SNAKE_CASE` at module level

## Reporting issues

Please include:
- Python version
- OS and version
- Steps to reproduce
- Expected vs actual behavior
