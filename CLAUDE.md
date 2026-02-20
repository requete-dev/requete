# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Requete** is a Python library (decorator-based metadata system) for defining data pipelines as code. It is not an execution engine — the decorators are metadata markers that enable the Requete orchestrator/IDE to build DAGs, validate dependencies, and generate executable pipeline artifacts. Supports multiple execution engines: Spark, DuckDB, and Snowflake.

## Commands

This project uses `uv` as the package manager.

```bash
# Lint
uvx ruff check .

# Format check
uvx ruff format --check .

# Format (apply)
uvx ruff format .

# Type check
uvx basedpyright

# Build package
uv build
```

There is no test runner — this library has no execution logic and tests live in consuming pipelines.

After every code change, verify with:

```bash
uvx ruff check . && uvx ruff format --check . && uvx basedpyright && uv build
```

## Architecture

The entire library is ~530 LOC across three modules in `requete/`:

### `sessions.py` — Execution Engine Configuration
Decorators that mark functions as session creators (SparkSession, DuckDB connection, Snowflake connection). Decorated functions must return the appropriate session object.

### `nodes.py` — Pipeline Node Types
Five decorator types that define the DAG structure:
- **`source`** — Reads external data; single `SparkSession` parameter
- **`backfill_source`** — Historical data ingestion; receives context parameters alongside the session
- **`transform`** — Pure, deterministic function taking one or more DataFrames; dependencies declared via `depends_on`
- **`sink`** — Writes data; no return value
- **`promote`** — Conditional write that only executes after linked promotion tests pass

### `tests.py` — Data Quality Assertions
Four test types:
- **`unit`** — Isolated logic tests with a SparkSession
- **`integration`** — Validates real pipeline output
- **`promotion`** — Data quality gates **required** for `promote` nodes
- **`source`** — Validates source node output

### Dependency Model
Dependencies are declared explicitly via `depends_on=[list_of_tags]`. A downstream function receives each upstream result as a parameter named `{tag}_df`. This explicit declaration is intentional — no implicit discovery, enabling static DAG construction.

### Key Parameters Shared Across Decorators
- `tag` — Unique identifier for the node
- `pipeline` — Which pipeline this node belongs to
- `engine` — Target execution engine
- `env` — Deployment environment (same tag across envs = same logic, different implementations)

### `__init__.py` Exports
The package re-exports from `sessions`, `nodes`, and `tests` as the public API. Keep this as the single import surface.

## Development Notes

- Python ≥ 3.11 required; tested on 3.11, 3.12, 3.13
- The library has **no runtime dependencies** — consumers bring their own PySpark/DuckDB/Snowflake
- `py.typed` marker is present for PEP 561 compliance; maintain full type annotations on all public APIs
- `basedpyright` is configured in `pyproject.toml` with `reportUnusedParameter = false` (decorator parameters are intentionally unused at the Python level)
- Publishing is done via `publish.yaml` with manual workflow dispatch; CI must pass first and the version in `pyproject.toml` must match the dispatch input
