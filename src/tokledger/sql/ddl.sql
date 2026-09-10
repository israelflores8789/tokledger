-- SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
-- SPDX-License-Identifier: MIT

-- Append-only audit trail of every collection run.
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id          UUID PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    host            TEXT,
    tokscale_ver    TEXT,
    status          TEXT,
    rows_in         INTEGER,
    rows_merged     INTEGER
);

-- Verbatim payloads. Source of truth for rebuilds. NOTE: raw payloads are
-- stored unsanitized; the database is private-by-authentication (see §5).
CREATE TABLE IF NOT EXISTS raw_exports (
    run_id          UUID REFERENCES ingest_runs(run_id),
    kind            TEXT,
    ingested_at     TIMESTAMPTZ NOT NULL,
    payload         JSON NOT NULL,
    PRIMARY KEY (run_id, kind)
);

-- Session dimension (from `tokscale report --json --no-summarize`).
-- Only stable, structurally-derived fields are kept; tokscale-generated
-- summary fields are intentionally excluded. session_label is a generated,
-- deterministic display name for human recognition.
CREATE TABLE IF NOT EXISTS sessions (
    client          TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    workspace       TEXT,
    workspace_label TEXT,
    created_at      TIMESTAMPTZ,
    last_active     TIMESTAMPTZ,
    duration_minutes INTEGER,
    message_count   BIGINT,
    cost_usd        DOUBLE,
    models_used     TEXT[],
    session_label   TEXT,
    first_seen_at   TIMESTAMPTZ NOT NULL,
    last_seen_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (client, session_id)
);

-- Fact table (from `tokscale models --json --group-by client,session,model`).
-- One row per (client, session, model); cumulative snapshot values with
-- point-in-time pricing embedded so each row is self-contained.
CREATE TABLE IF NOT EXISTS session_model_stats (
    client          TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    model           TEXT NOT NULL,
    provider        TEXT,
    input_tokens    BIGINT,
    output_tokens   BIGINT,
    cache_read      BIGINT,
    cache_write     BIGINT,
    reasoning       BIGINT,
    -- tokscale counts reasoning ON TOP of the other four buckets
    -- (fixture-verified: graph totalTokens == in+out+cr+cw+reasoning):
    total_tokens    BIGINT GENERATED ALWAYS AS
        (input_tokens + output_tokens + cache_read + cache_write + reasoning),
    message_count   BIGINT,
    cost_usd        DOUBLE,
    ms_per_1k_tokens    DOUBLE,
    perf_duration_ms    BIGINT,
    perf_token_coverage DOUBLE,
    price_input_per_token       DOUBLE,
    price_output_per_token      DOUBLE,
    price_cache_read_per_token  DOUBLE,
    price_cache_write_per_token DOUBLE,
    price_matched_key   TEXT,
    price_match_kind    TEXT,
    price_alias_applied BOOLEAN,
    price_source        TEXT,
    price_captured_at   TIMESTAMPTZ,
    first_seen_at   TIMESTAMPTZ NOT NULL,
    last_seen_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (client, session_id, model)
);

-- Daily fact (from `tokscale graph` contributions[]): one row per
-- (day, client, model) — graph emits full token-type breakdown at this grain.
CREATE TABLE IF NOT EXISTS daily_stats (
    day             DATE NOT NULL,
    client          TEXT NOT NULL,
    model           TEXT NOT NULL,
    provider        TEXT,
    input_tokens    BIGINT,
    output_tokens   BIGINT,
    cache_read      BIGINT,
    cache_write     BIGINT,
    reasoning       BIGINT,
    message_count   BIGINT,
    cost_usd        DOUBLE,
    PRIMARY KEY (day, client, model)
);

-- Day-level activity (from contributions[]): intensity + active time.
CREATE TABLE IF NOT EXISTS daily_activity (
    day             DATE PRIMARY KEY,
    intensity       INTEGER,
    active_time_ms  BIGINT
);

-- Rate history per model (tokscale-resolved only).
CREATE TABLE IF NOT EXISTS pricing_snapshots (
    captured_at     TIMESTAMPTZ NOT NULL,
    model           TEXT NOT NULL,
    source          TEXT NOT NULL,
    matched_key     TEXT,
    match_kind      TEXT,
    price_input_per_token       DOUBLE,
    price_output_per_token      DOUBLE,
    price_cache_read_per_token  DOUBLE,
    price_cache_write_per_token DOUBLE,
    PRIMARY KEY (captured_at, model)
);

-- Run-level aggregate telemetry (from graph summary + timeMetrics).
CREATE TABLE IF NOT EXISTS run_metrics (
    run_id              UUID PRIMARY KEY REFERENCES ingest_runs(run_id),
    captured_at         TIMESTAMPTZ NOT NULL,
    total_tokens        BIGINT,
    total_cost          DOUBLE,
    active_days         INTEGER,
    total_active_time_ms BIGINT,
    longest_continuous_ms  BIGINT,
    max_concurrent_sessions INTEGER,
    graph_session_count INTEGER
);

-- User curation: tags at two scopes. scope='client' with empty session_id
-- applies to every session of that client; a session-scoped tag names one
-- session. Tags are plaintext by definition (user-chosen labels).
CREATE TABLE IF NOT EXISTS tags (
    scope           TEXT NOT NULL CHECK (scope IN ('client', 'session')),
    client          TEXT NOT NULL,
    session_id      TEXT NOT NULL DEFAULT '',
    tag             TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (scope, client, session_id, tag)
);

-- User curation: free-text diagnostic notes per session.
CREATE TABLE IF NOT EXISTS notes (
    client          TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    note            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (client, session_id)
);

-- Non-fatal cross-payload reconciliation observations per run.
CREATE TABLE IF NOT EXISTS reconciliation_issues (
    run_id          UUID REFERENCES ingest_runs(run_id),
    check_name      TEXT,
    issue_key       TEXT,
    message         TEXT
);
