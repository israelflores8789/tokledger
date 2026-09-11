# tokledger — Agent Context

## Purpose

A Python CLI and library (pipx-installable, import tokledger) that persists `tokscale` JSON token usage statistics to a persistent data store into DuckDB or MotherDuck. This allows users to aggregate token usage across agentic environments.

## Repository Structure
```
tokledger/
├── pyproject.toml            # hatchling; pipx-installable; Python >= 3.11
├── src/tokledger/
│   ├── cli.py                # typer app
│   ├── collector.py          # tokscale subprocess + retry
│   ├── parsers/              # one module per payload kind
│   │   ├── models.py         # per session×model rows → session_model_stats
│   │   ├── report.py         # session metadata       → sessions (no LLM summary fields)
│   │   ├── graph.py          # daily contributions    → daily_stats/daily_activity/run_metrics
│   │   └── pricing.py        # rates + resolution     → pricing_snapshots + row stamps
│   ├── backends/
│   │   ├── base.py           # StorageBackend protocol
│   │   ├── duckdb_local.py
│   │   └── motherduck.py
│   ├── merge.py              # staging + transactional merge + rebuild + session_label
│   ├── reconcile.py          # cross-payload consistency checks
│   ├── curation.py           # tags + notes
│   ├── sanitize.py           # export-time pseudonymization (--sanitize)
│   ├── report_term.py        # rich tables + plotext charts (+ --save/--sanitize)
│   ├── api.py                # tokledger.query/connect (pandas default, polars opt-in)
│   └── sql/                  # ddl + views, loaded as package data
├── tests/
│   ├── fixtures/             # sanitized golden captures: models, report, graph, pricing
│   └── test_*.py             # incl. fixture-derived invariants
└── .github/workflows/        # ci (ruff, pyrefly, pytest), release to PyPI
```

## Architecture

- **Dependencies**: `duckdb`, `pandas`, `pydantic`, `typer`, `rich`, `plotext`, `polars` (optional).
- **Dev Environment**: `uv`, `hatchling`, `twine`, `pyrefly`, `ruff`, `pytest`, `just`, `pre-commit`.

## SQL Schema


## Rules

- USE Google-style docstrings for **all** python modules.
- KEEP comments concise yet clear. Do NOT use numbered headers (e.g. "1." or "(1)" etc).
- NO version string is ever hard-coded in source; `hatch-vcs` manages version numbering from git tags (`v0.1.0` → `0.1.0`).
- NEVER modify the golden JSON fixtures in `tests/fixtures/`.

## Commands

Run all project tasks via `just` from the repository root. Use `just --list` to inspect available recipes.

<!-- TODO: truncate and simplify -->
### Setup

- `just install-dev` — synchronize all uv dependency groups
- `just install-motherduck` — install the MotherDuck CLI when required

### Validation

- `just test` — run tests; pass pytest arguments with `just test <args>`
- `just coverage` — run tests with terminal coverage reporting
- `just lint` — run Ruff linting and formatting checks
- `just typecheck` — run Pyrefly type checks
- `just spell` — check spelling
- `just spell-diff` — check spelling only in changed files
- `just spell-fix` — apply spelling fixes
- `just ci` — standard validation gate: tests, lint, type checking
- `just check-justfile` — verify Justfile formatting

### Packaging

- `just build` — clean `dist/` and build an sdist and wheel with Hatchling
- `just check-dist` — clean, build, and validate artifacts with Twine
- `just clean` — remove build artifacts and local caches

### Publishing

- `just publish-test` — local/manual release path: clean, build, validate, and upload to TestPyPI
- `just publish` — local/manual release path: clean, build, validate, and upload to PyPI
- `just release-check` — CI artifact path: validate the existing contents of `dist/` with Twine
- `just release-test` — CI artifact path: upload already-built `dist/` artifacts to TestPyPI
- `just release` — CI artifact path: upload already-built `dist/` artifacts to PyPI

Publishing requires `UV_PUBLISH_TOKEN` locally, or PyPI Trusted Publishing in CI. Do not invoke any publishing command unless explicitly asked. In CI, build once, test/validate those exact artifacts, then use `release-check` and `release` rather than rebuilding.
