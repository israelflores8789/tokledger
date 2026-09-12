# SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
# SPDX-License-Identifier: AGPL-3.0-only

"""conftest.py — Shared fixtures for the usagebassoon test suite.

Golden payloads were captured from tokscale 4.15.1 on 2026-09-10 and
sanitized. See Appendix A of the design doc for the invariants asserted
across this suite.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb
import pytest
from usagebassoon.merge import CollectionBundle
from usagebassoon.parsers.graph import GraphPayload, parse_graph
from usagebassoon.parsers.models import ModelsPayload, parse_models
from usagebassoon.parsers.pricing import PricingRow, parse_pricing
from usagebassoon.parsers.report import SessionRow, parse_report
from usagebassoon.reconcile import ReconciliationResult, reconcile_all

FIXTURES = Path(__file__).parent / "fixtures"

EXPECTED_MODELS_ENTRIES = 88
EXPECTED_REPORT_ROWS = 81
EXPECTED_DAILY_ROWS = 23
EXPECTED_DAYS = 18
EXPECTED_TOTAL_INPUT = 78_318_668
EXPECTED_TOTAL_OUTPUT = 1_415_099
EXPECTED_TOTAL_CACHE_READ = 496_893_790
EXPECTED_TOTAL_CACHE_WRITE = 0
EXPECTED_TOTAL_REASONING = 1_686_926
EXPECTED_TOTAL_MESSAGES = 4_988
EXPECTED_TOTAL_COST = 109.48238866000003
EXPECTED_TOKSCALE_VERSION = "4.15.1"


def _load(name: str) -> Any:
    """Load a golden fixture by stem name.

    Args:
        name: Fixture stem, e.g. "models".

    Returns:
        The decoded JSON payload.
    """
    return json.loads((FIXTURES / f"golden-2026-09-10.{name}.json").read_text())


@pytest.fixture(scope="session")
def models_raw() -> dict[str, Any]:
    """Return the raw models payload as decoded JSON."""
    return _load("models")


@pytest.fixture(scope="session")
def report_raw() -> list[dict[str, Any]]:
    """Return the raw report payload as decoded JSON."""
    return _load("report")


@pytest.fixture(scope="session")
def graph_raw() -> dict[str, Any]:
    """Return the raw graph payload as decoded JSON."""
    return _load("graph")


@pytest.fixture(scope="session")
def pricing_raw() -> dict[str, Any]:
    """Return the raw pricing payload as decoded JSON."""
    return _load("pricing")


@pytest.fixture(scope="session")
def models_payload(models_raw: dict[str, Any]) -> ModelsPayload:
    """Return the validated models payload."""
    return parse_models(models_raw)


@pytest.fixture(scope="session")
def report_rows(report_raw: list[dict[str, Any]]) -> list[SessionRow]:
    """Return the validated report rows."""
    return parse_report(report_raw)


@pytest.fixture(scope="session")
def graph_payload(graph_raw: dict[str, Any]) -> GraphPayload:
    """Return the validated graph payload."""
    return parse_graph(graph_raw)


@pytest.fixture(scope="session")
def pricing_row(pricing_raw: dict[str, Any]) -> PricingRow:
    """Return the validated pricing row."""
    return parse_pricing(pricing_raw)


@pytest.fixture(scope="session")
def recon_result(
    models_payload: ModelsPayload,
    report_rows: list[SessionRow],
    graph_payload: GraphPayload,
) -> ReconciliationResult:
    """Run full reconciliation over the golden fixture set."""
    return reconcile_all(models_payload, report_rows, graph_payload)


@pytest.fixture
def connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield an in-memory DuckDB connection with the full DDL applied."""
    ddl = Path(__file__).parents[1] / "src" / "usagebassoon" / "sql" / "ddl.sql"
    con = duckdb.connect(":memory:")
    con.execute(ddl.read_text())
    yield con
    con.close()


@pytest.fixture
def collection_bundle(
    models_payload: ModelsPayload,
    report_rows: list[SessionRow],
    graph_payload: GraphPayload,
    pricing_row: PricingRow,
    models_raw: dict[str, Any],
    report_raw: list[dict[str, Any]],
    graph_raw: dict[str, Any],
    pricing_raw: dict[str, Any],
    recon_result: ReconciliationResult,
) -> CollectionBundle:
    """Build a complete, validated CollectionBundle from the fixtures."""
    return CollectionBundle(
        run_id=uuid4(),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC) + timedelta(seconds=2),
        host="pytest",
        models=models_payload,
        report_rows=report_rows,
        graph=graph_payload,
        pricing_by_model={"gemini-3.8-flash": pricing_row},
        raw_exports={
            "models": models_raw,
            "report": report_raw,
            "graph": graph_raw,
            "pricing": pricing_raw,
        },
        reconciliation=recon_result,
    )
