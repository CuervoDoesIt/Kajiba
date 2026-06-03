"""Capture the ESCH-04 golden baseline of record_id + submission_hash.

This standalone, reproducible script snapshots the ``record_id`` and
``submission_hash`` produced by the CURRENT (pre-refactor) ``schema.py`` for
every existing ``*_trajectory.json`` fixture. The result is written to
``tests/fixtures/golden_ids.json`` and committed BEFORE any edit to
``src/kajiba/schema.py`` (the schema refactor lands in plan 10-02).

Why this matters: the baseline is the back-compat tripwire for the entire
phase. If it were generated from the post-refactor schema it would capture the
wrong hashes and the ESCH-04 byte-identical guarantee would become
unfalsifiable. The downstream parametrized test (plan 10-03) reads this file
as ground truth.

``enriched_catalog.json`` is intentionally excluded: it is a publisher catalog
fixture, not a ``KajibaRecord`` (it has no top-level ``trajectory`` key). The
``*_trajectory.json`` glob naturally selects only the five record fixtures, and
a defensive guard skips any loaded dict lacking a ``trajectory`` key.

Run from the repo root with the editable install active::

    python tests/capture_golden_ids.py
"""

import json
from pathlib import Path

from kajiba.schema import validate_record

FIXTURES = Path(__file__).parent / "fixtures"


def main() -> None:
    """Generate tests/fixtures/golden_ids.json from the pre-refactor schema."""
    out: dict[str, dict[str, str]] = {}

    for f in sorted(FIXTURES.glob("*_trajectory.json")):
        data = json.loads(f.read_text(encoding="utf-8"))

        # Belt-and-suspenders: only KajibaRecord fixtures carry a trajectory.
        if "trajectory" not in data:
            print(f"skip   {f.name} (no top-level 'trajectory' key)")
            continue

        rec = validate_record(data)
        entry = {
            "record_id": rec.compute_record_id(),
            "submission_hash": rec.compute_submission_hash(),
        }
        out[f.name] = entry
        print(f"capture {f.name} -> {entry['record_id']} {entry['submission_hash']}")

    golden_path = FIXTURES / "golden_ids.json"
    golden_path.write_text(
        json.dumps(out, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"wrote   {golden_path} ({len(out)} fixtures)")


if __name__ == "__main__":
    main()
