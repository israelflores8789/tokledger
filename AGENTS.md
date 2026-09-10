# tokledger — Agent Context

## Purpose

A python service that persists `tokscale` token usage statistics to a persistent data store using `DuckDB` and `MotherDuck` (default). This allows users to aggregate token usage across agentic environments.

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
│   └── test_*.py             # incl. fixture-derived invariants (Appendix A)
├── .github/workflows/        # ci (ruff, mypy, pytest), release to PyPI
└── docs/                     # incl. SECURITY.md (threat model from §5)
```

## Architecture

- **Dependencies**: `duckdb`, `pandas`, `pydantic`, `typer`, `rich`, `plotext`, `polars` (optional).
- **Dev Environment**: `uv`, `hatchling`, `pyrefly`, `ruff`, `pytest`, `just`, `pre-commit`.

## Rules

- USE Google-style docstrings for **all** python modules.
- KEEP comments concise yet clear. Do NOT use numbered headers (e.g. "1." or "(1)" etc).
- NO version string is ever hard-coded in source; `hatch-vcs` manages version numbering from git tags (`v0.1.0` → `0.1.0`).

## SQL Schema