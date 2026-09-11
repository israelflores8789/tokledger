# SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
# SPDX-License-Identifier: MIT

"""test_merge.py — Merge-level golden-file tests over the real DDL + fixture set."""

from __future__ import annotations

import dataclasses
from uuid import uuid4

import duckdb
import pytest

from tests.conftest import (
    EXPECTED_DAILY_ROWS,
    EXPECTED_DAYS,
    EXPECTED_MODELS_ENTRIES,
    EXPECTED_REPORT_ROWS,
    EXPECTED_TOKSCALE_VERSION,
)
from tokledger.merge import CollectionBundle, MergeError, merge_collection


def test_merge_populates_all_tables(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert one merge populates every curated and audit table."""
    merge_collection(connection, collection_bundle)
    counts = {
        t: connection.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in (
            "ingest_runs",
            "raw_exports",
            "sessions",
            "session_model_stats",
            "daily_stats",
            "daily_activity",
            "pricing_snapshots",
            "run_metrics",
            "reconciliation_issues",
        )
    }
    assert counts == {
        "ingest_runs": 1,
        "raw_exports": 4,
        "sessions": EXPECTED_REPORT_ROWS,
        "session_model_stats": EXPECTED_MODELS_ENTRIES,
        "daily_stats": EXPECTED_DAILY_ROWS,
        "daily_activity": EXPECTED_DAYS,
        "pricing_snapshots": 1,
        "run_metrics": 1,
        "reconciliation_issues": 10,
    }


def test_merge_is_idempotent(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert a second run upserts curated tables; audit tables grow."""
    merge_collection(connection, collection_bundle)
    merge_collection(connection, dataclasses.replace(collection_bundle, run_id=uuid4()))
    assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == EXPECTED_REPORT_ROWS
    assert (
        connection.execute("SELECT count(*) FROM session_model_stats").fetchone()[0]
        == EXPECTED_MODELS_ENTRIES
    )
    assert connection.execute("SELECT count(*) FROM ingest_runs").fetchone()[0] == 2
    assert connection.execute("SELECT count(*) FROM raw_exports").fetchone()[0] == 8


def test_total_tokens_includes_reasoning(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert the generated column includes reasoning."""
    merge_collection(connection, collection_bundle)
    sample = connection.execute(
        "SELECT input_tokens, output_tokens, cache_read, cache_write,"
        " reasoning, total_tokens FROM session_model_stats"
        " WHERE reasoning > 0 LIMIT 1"
    ).fetchone()
    assert sample[5] == sum(sample[:5])


def test_embedded_pricing_round_trip(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert point-in-time pricing lands with provenance intact."""
    merge_collection(connection, collection_bundle)
    row = connection.execute(
        "SELECT price_input_per_token, price_match_kind, price_source"
        " FROM session_model_stats WHERE model = 'gemini-3.8-flash'"
        " LIMIT 1"
    ).fetchone()
    assert row == (7.5e-07, "exact", "LiteLLM")


def test_session_label_landed(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert session labels are generated and unique."""
    merge_collection(connection, collection_bundle)
    labels = connection.execute("SELECT session_label FROM sessions").fetchall()
    assert all(lbl and "·" in lbl for (lbl,) in labels)
    assert len({lbl for (lbl,) in labels}) == EXPECTED_REPORT_ROWS


def test_tokscale_version_stamped(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert the graph meta version stamps the ingest run."""
    merge_collection(connection, collection_bundle)
    got = connection.execute("SELECT tokscale_ver, status FROM ingest_runs").fetchone()
    assert got == (EXPECTED_TOKSCALE_VERSION, "partial")


def test_user_tables_untouched_by_merge(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert merge never inserts into tags or notes."""
    connection.execute(
        "INSERT INTO tags VALUES ('session', 'codex', 'ses_1', 'investigate', now())"
    )
    connection.execute("INSERT INTO notes VALUES ('codex', 'ses_1', 'spike here', now(), now())")
    merge_collection(connection, collection_bundle)
    assert connection.execute("SELECT count(*) FROM tags").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM notes").fetchone()[0] == 1


def test_merge_rolls_back_on_failure(
    connection: duckdb.DuckDBPyConnection,
    collection_bundle: CollectionBundle,
) -> None:
    """Assert a corrupt bundle leaves zero partial rows."""
    bad = dataclasses.replace(
        collection_bundle,
        raw_exports={"broken": object()},  # not JSON-serializable
    )
    with pytest.raises(MergeError):
        merge_collection(connection, bad)
    assert connection.execute("SELECT count(*) FROM ingest_runs").fetchone()[0] == 0
    assert connection.execute("SELECT count(*) FROM raw_exports").fetchone()[0] == 0
