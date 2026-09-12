# SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
# SPDX-License-Identifier: AGPL-3.0-only

"""merge.py — Transactional persistence of normalized tokscale payloads into DuckDB.

Conforms to the final design doc: slim sessions (no LLM summary columns),
deterministic session labels, embedded point-in-time pricing, and user
tables (tags, notes) are never touched by merge.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import duckdb
from usagebassoon.parsers.graph import GraphPayload
from usagebassoon.parsers.models import ModelsPayload, ModelStatsRow
from usagebassoon.parsers.pricing import PricingRow
from usagebassoon.parsers.report import SessionRow, make_session_label
from usagebassoon.reconcile import ReconciliationResult


@dataclass(frozen=True, slots=True)
class CollectionBundle:
    """All normalized data produced by one successful collector invocation.

    Attributes:
        run_id: Identifier for this collection run.
        started_at: When the collector began invoking tokscale.
        finished_at: When parsing finished; used as the merge timestamp.
        host: Hostname or container id, if known.
        models: Validated models payload (metrics authority).
        report_rows: Validated report rows (metadata authority).
        graph: Validated graph payload (daily dimension + telemetry).
        pricing_by_model: Resolved rate cards keyed by model id.
        raw_exports: Verbatim decoded payloads keyed by kind.
        reconciliation: Cross-payload consistency results.
    """

    run_id: UUID
    started_at: datetime
    finished_at: datetime
    host: str | None
    models: ModelsPayload
    report_rows: list[SessionRow]
    graph: GraphPayload
    pricing_by_model: dict[str, PricingRow]
    raw_exports: dict[str, Any]
    reconciliation: ReconciliationResult


class MergeError(RuntimeError):
    """Raised when a collection bundle cannot be persisted atomically."""


def _json(value: Any) -> str:
    """Serialize raw payloads compactly for a DuckDB JSON column.

    Args:
        value: Any JSON-serializable decoded payload.

    Returns:
        A compact UTF-8-safe JSON string.
    """
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _insert_raw_exports(
    connection: duckdb.DuckDBPyConnection,
    run_id: UUID,
    captured_at: datetime,
    raw_exports: dict[str, Any],
) -> None:
    """Insert the immutable raw JSON record for every command payload.

    Args:
        connection: An active DuckDB-compatible connection.
        run_id: Identifier for the owning collection run.
        captured_at: Timestamp recorded for each raw payload row.
        raw_exports: Decoded payloads keyed by payload kind.
    """
    connection.executemany(
        "INSERT INTO raw_exports (run_id, kind, ingested_at, payload) "
        "VALUES (?, ?, ?, CAST(? AS JSON))",
        [(run_id, kind, captured_at, _json(p)) for kind, p in raw_exports.items()],
    )


def _merge_sessions(
    connection: duckdb.DuckDBPyConnection,
    rows: Iterable[SessionRow],
    captured_at: datetime,
) -> None:
    """Upsert the current metadata snapshot for every observed session.

    Args:
        connection: An active DuckDB-compatible connection.
        rows: Validated session metadata rows from the report payload.
        captured_at: Timestamp stamped onto first/last seen columns.
    """
    values = [
        (
            row.client,
            row.session_id,
            row.workspace,
            row.workspace_label,
            row.created_at,
            row.last_active,
            row.duration_minutes,
            row.message_count,
            row.cost_usd,
            list(row.models_used),
            make_session_label(row),
            captured_at,
            captured_at,
        )
        for row in rows
    ]
    if not values:
        return
    connection.executemany(
        """
        INSERT INTO sessions AS target (
            client, session_id, workspace, workspace_label, created_at, last_active,
            duration_minutes, message_count, cost_usd, models_used, session_label,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (client, session_id) DO UPDATE SET
            workspace = excluded.workspace,
            workspace_label = excluded.workspace_label,
            created_at = excluded.created_at,
            last_active = excluded.last_active,
            duration_minutes = excluded.duration_minutes,
            message_count = excluded.message_count,
            cost_usd = excluded.cost_usd,
            models_used = excluded.models_used,
            session_label = excluded.session_label,
            last_seen_at = excluded.last_seen_at
        """,
        values,
    )


def _pricing_values(
    model: str,
    pricing_by_model: dict[str, PricingRow],
) -> tuple[Any, ...]:
    """Return nullable row-level pricing fields aligned with the insert.

    Args:
        model: The model id to resolve pricing for.
        pricing_by_model: Rate cards captured during this run.

    Returns:
        An eight-tuple of pricing column values, all None if uncaptured.
    """
    price = pricing_by_model.get(model)
    if price is None:
        return (None,) * 8
    return (
        price.pricing.input_cost_per_token,
        price.pricing.output_cost_per_token,
        price.pricing.cache_read_input_token_cost,
        price.pricing.cache_write_input_token_cost,
        price.matched_key,
        price.resolution.kind,
        price.resolution.alias_applied,
        price.source,
    )


def _merge_session_model_stats(
    connection: duckdb.DuckDBPyConnection,
    rows: Iterable[ModelStatsRow],
    pricing_by_model: dict[str, PricingRow],
    captured_at: datetime,
) -> None:
    """Upsert cumulative session-model metrics with contemporaneous pricing.

    Args:
        connection: An active DuckDB-compatible connection.
        rows: Validated per-(client, session, model) cumulative entries.
        pricing_by_model: Rate cards captured during this run.
        captured_at: Timestamp stamped onto seen/pricing columns.
    """
    values = [
        (
            row.client,
            row.session_id,
            row.model,
            row.provider,
            row.input_tokens,
            row.output_tokens,
            row.cache_read,
            row.cache_write,
            row.reasoning,
            row.message_count,
            row.cost_usd,
            row.ms_per_1k_tokens,
            row.perf_duration_ms,
            row.perf_token_coverage,
            *_pricing_values(row.model, pricing_by_model),
            captured_at,
            captured_at,
            captured_at,
        )
        for row in rows
    ]
    if not values:
        return
    connection.executemany(
        """
        INSERT INTO session_model_stats AS target (
            client, session_id, model, provider,
            input_tokens, output_tokens, cache_read, cache_write, reasoning,
            message_count, cost_usd,
            ms_per_1k_tokens, perf_duration_ms, perf_token_coverage,
            price_input_per_token, price_output_per_token,
            price_cache_read_per_token, price_cache_write_per_token,
            price_matched_key, price_match_kind, price_alias_applied, price_source,
            price_captured_at, first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (client, session_id, model) DO UPDATE SET
            provider = excluded.provider,
            input_tokens = excluded.input_tokens,
            output_tokens = excluded.output_tokens,
            cache_read = excluded.cache_read,
            cache_write = excluded.cache_write,
            reasoning = excluded.reasoning,
            message_count = excluded.message_count,
            cost_usd = excluded.cost_usd,
            ms_per_1k_tokens = excluded.ms_per_1k_tokens,
            perf_duration_ms = excluded.perf_duration_ms,
            perf_token_coverage = excluded.perf_token_coverage,
            price_input_per_token = excluded.price_input_per_token,
            price_output_per_token = excluded.price_output_per_token,
            price_cache_read_per_token = excluded.price_cache_read_per_token,
            price_cache_write_per_token = excluded.price_cache_write_per_token,
            price_matched_key = excluded.price_matched_key,
            price_match_kind = excluded.price_match_kind,
            price_alias_applied = excluded.price_alias_applied,
            price_source = excluded.price_source,
            price_captured_at = excluded.price_captured_at,
            last_seen_at = excluded.last_seen_at
        """,
        values,
    )


def _merge_daily(
    connection: duckdb.DuckDBPyConnection,
    graph: GraphPayload,
) -> None:
    """Upsert additive graph facts by their natural keys.

    Args:
        connection: An active DuckDB-compatible connection.
        graph: Validated graph payload with contributions and telemetry.
    """
    stats = [
        (
            c.date,
            client.client,
            client.model_id,
            client.provider_id,
            client.tokens.input,
            client.tokens.output,
            client.tokens.cache_read,
            client.tokens.cache_write,
            client.tokens.reasoning,
            client.messages,
            client.cost,
        )
        for c in graph.contributions
        for client in c.clients
    ]
    if stats:
        connection.executemany(
            """
            INSERT INTO daily_stats AS target (
                day, client, model, provider, input_tokens, output_tokens,
                cache_read, cache_write, reasoning, message_count, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (day, client, model) DO UPDATE SET
                provider = excluded.provider,
                input_tokens = excluded.input_tokens,
                output_tokens = excluded.output_tokens,
                cache_read = excluded.cache_read,
                cache_write = excluded.cache_write,
                reasoning = excluded.reasoning,
                message_count = excluded.message_count,
                cost_usd = excluded.cost_usd
            """,
            stats,
        )
    activity = [(c.date, c.intensity, c.active_time_ms) for c in graph.contributions]
    if activity:
        connection.executemany(
            """
            INSERT INTO daily_activity AS target (day, intensity, active_time_ms)
            VALUES (?, ?, ?)
            ON CONFLICT (day) DO UPDATE SET
                intensity = excluded.intensity,
                active_time_ms = excluded.active_time_ms
            """,
            activity,
        )


def _insert_pricing_snapshots(
    connection: duckdb.DuckDBPyConnection,
    pricing_by_model: dict[str, PricingRow],
    captured_at: datetime,
) -> None:
    """Append rate cards observed during this collection run.

    Args:
        connection: An active DuckDB-compatible connection.
        pricing_by_model: Rate cards captured during this run.
        captured_at: Timestamp recorded for each snapshot row.
    """
    values = [
        (
            captured_at,
            p.model_id,
            p.source,
            p.matched_key,
            p.resolution.kind,
            p.pricing.input_cost_per_token,
            p.pricing.output_cost_per_token,
            p.pricing.cache_read_input_token_cost,
            p.pricing.cache_write_input_token_cost,
        )
        for p in pricing_by_model.values()
    ]
    if values:
        connection.executemany(
            """
            INSERT INTO pricing_snapshots (
                captured_at, model, source, matched_key, match_kind,
                price_input_per_token, price_output_per_token,
                price_cache_read_per_token, price_cache_write_per_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            values,
        )


def _insert_run_metrics(
    connection: duckdb.DuckDBPyConnection,
    run_id: UUID,
    graph: GraphPayload,
) -> None:
    """Persist graph-level telemetry for the collection run.

    Args:
        connection: An active DuckDB-compatible connection.
        run_id: Identifier for the owning collection run.
        graph: Validated graph payload; provides summary + timeMetrics.
    """
    tm, summary = graph.time_metrics, graph.summary
    connection.execute(
        """
        INSERT INTO run_metrics (
            run_id, captured_at, total_tokens, total_cost, active_days,
            total_active_time_ms, longest_continuous_ms,
            max_concurrent_sessions, graph_session_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            graph.meta.generated_at,
            summary.total_tokens,
            summary.total_cost,
            summary.active_days,
            tm.total_active_time_ms,
            tm.longest_continuous_ms,
            tm.max_concurrent_sessions,
            tm.session_count,
        ],
    )


def _record_issues(
    connection: duckdb.DuckDBPyConnection,
    run_id: UUID,
    reconciliation: ReconciliationResult,
) -> None:
    """Persist non-fatal reconciliation warnings for the run.

    Args:
        connection: An active DuckDB-compatible connection.
        run_id: Identifier for the owning collection run.
        reconciliation: Results of the cross-payload consistency checks.
    """
    if not reconciliation.issues:
        return
    connection.executemany(
        "INSERT INTO reconciliation_issues (run_id, check_name, issue_key, message) "
        "VALUES (?, ?, ?, ?)",
        [(run_id, i.check, i.key, i.message) for i in reconciliation.issues],
    )


def merge_collection(
    connection: duckdb.DuckDBPyConnection,
    bundle: CollectionBundle,
) -> None:
    """Atomically persist one fully parsed collection bundle.

    Owns a single SQL transaction; leaves no partial rows on failure. The
    caller must have initialized the DDL.

    Args:
        connection: A local DuckDB or MotherDuck connection.
        bundle: Parsed payloads, raw JSON, rates, and reconciliation output.

    Raises:
        MergeError: If the bundle could not be written atomically.
    """
    connection.execute("BEGIN TRANSACTION")
    try:
        connection.execute(
            "INSERT INTO ingest_runs (run_id, started_at, finished_at, host, "
            "tokscale_ver, status, rows_in, rows_merged) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                bundle.run_id,
                bundle.started_at,
                bundle.finished_at,
                bundle.host,
                bundle.graph.meta.version,
                "ok" if bundle.reconciliation.ok else "partial",
                len(bundle.models.entries)
                + len(bundle.report_rows)
                + sum(len(c.clients) for c in bundle.graph.contributions),
                len(bundle.models.entries),
            ],
        )
        _insert_raw_exports(connection, bundle.run_id, bundle.finished_at, bundle.raw_exports)
        _merge_sessions(connection, bundle.report_rows, bundle.finished_at)
        _merge_session_model_stats(
            connection, bundle.models.entries, bundle.pricing_by_model, bundle.finished_at
        )
        _merge_daily(connection, bundle.graph)
        _insert_pricing_snapshots(connection, bundle.pricing_by_model, bundle.finished_at)
        _insert_run_metrics(connection, bundle.run_id, bundle.graph)
        _record_issues(connection, bundle.run_id, bundle.reconciliation)
        connection.execute("COMMIT")
    except Exception as error:
        try:
            connection.execute("ROLLBACK")
        except duckdb.Error:
            pass
        raise MergeError(f"failed to merge collection {bundle.run_id}") from error
