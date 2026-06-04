# Kajiba (鍛冶場)

**Community data pipeline for open-source local model improvement**

> *Kajiba — the Japanese word for a forge or smithy. Where raw material is shaped into something stronger.*

**Status: Early MVP (Phase 1)**

## What is this?

Kajiba is an open-source pipeline that collects, standardizes, scrubs, curates, and distributes real-world usage data from local model deployments running through the [Hermes Agent](https://github.com/NousResearch/hermes-agent) harness. Users running local models generate structured data about what works and what doesn't, and that data flows into a shared repository that the community uses to fine-tune and train the next generation of local models.

Kajiba builds the **collection, standardization, privacy, curation, and distribution** layers that sit between individual users and the community training pipeline.

## Installation

```bash
# Basic install
pip install -e .

# With all extras (upload, dev tools)
pip install -e ".[all]"
```

Requires Python 3.11+.

## Quick usage

During a Hermes Agent session:

```
# Rate the current session (1-5 scale + tags from controlled vocabulary)
/rate 4 task_completed minor_hallucination

# Report a pain point
/report tool_call_failure Model tried to use docker_compose tool

# Preview what will be submitted
/kajiba preview

# Submit the session data (after preview + confirmation)
/kajiba submit
```

Using the CLI directly:

```bash
# Preview the most recent session
kajiba preview

# Export to a local file
kajiba export ./my-session.jsonl

# View submission history
kajiba history

# Aggregate statistics
kajiba stats
```

## Documentation

See the full project specification: [docs/kajiba-project-spec.md](docs/kajiba-project-spec.md)

## License

Apache 2.0 — see [LICENSE](LICENSE)
