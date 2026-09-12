<!--
SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
SPDX-License-Identifier: AGPL-3.0-only
-->

# UsageBassoon — Agent Context

## Purpose

A Python CLI and library (pipx-installable, import usagebassoon) that persists `tokscale` JSON token usage statistics to a persistent data store into DuckDB or MotherDuck. This allows users to aggregate token usage across agentic environments.

## Repository Structure
```
usagebassoon/
├── pyproject.toml            # hatchling; pipx-installable; Python >= 3.11
├── src/usagebassoon/
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
│   ├── api.py                # usagebassoon.query/connect (pandas default, polars opt-in)
│   └── sql/                  # ddl + views, loaded as package data
├── tests/
│   ├── fixtures/             # sanitized golden captures: models, report, graph, pricing
│   └── test_*.py             # incl. fixture-derived invariants
└── .github/workflows/        # ci (ruff, pyrefly, pytest), release to PyPI
```

## Architecture

- **Dependencies**: `duckdb`, `pandas`, `pydantic`, `typer`, `rich`, `plotext`, `polars` (optional).
- **Dev Environment**: `uv`, `hatchling`, `twine`, `pyrefly`, `ruff`, `pytest`, `just`, `pre-commit`.

## Commands

Run all project tasks via `just` from the repository root. Use `just --list` to inspect available recipes.

- USE `just install-dev` to synchronize all uv dependency groups.
- USE `just test` to run the test suite; pass pytest arguments with `just test <args>`.
- USE `just coverage` to run test suite with terminal coverage reporting.
- USE `just lint` to perform Ruff linting and formatting checks.
- USE `just typecheck` to perform Pyrefly type checks.
- USE `just spell-diff` to run typos spelling checker.
- PREFER `just ci` for combined test, lint, and typecheck recipes.
- USE `just build` to clean `dist/` and build an sdist and wheel with Hatchling.
- USE `just check-dist` to clean, build, and validate artifacts with Twine.
- USE `just clean` to remove build artifacts and local caches.

## Rules

- USE Google-style docstrings for **all** source code.
- KEEP comments concise yet clear. Do NOT use numbered headers (e.g. "1." or "(1)" etc).
- NO version string is ever hard-coded in source; `hatch-vcs` manages version numbering from git tags (`v0.1.0` → `0.1.0`).

### Prohibitions
The following actions are **prohibited** and are reserved exclusively for the user. When encountering a task that involves a prohibited action, you MUST **stop** and **report** to the user the conflict:

- NEVER modify the golden JSON fixtures in `tests/fixtures/`.
- NEVER attempt to publish to PyPI or invoke any publishing command; consequently, NEVER use `just publish` or `just release`.
- NEVER attempt to perform a release to GitHub or invoke any release command.
- NEVER attempt to push git changes to GitHub.
