# SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
# SPDX-License-Identifier: MIT

"""test_backends.py — Backend tests: local DuckDB round-trips; MotherDuck validation only.

MotherDuck connectivity is intentionally not tested here — it requires a
token and a live service. Behaviour under missing/invalid config is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tokledger.backends.base import DatabaseBackend
from tokledger.backends.duckdb_local import LocalDuckDBBackend
from tokledger.backends.motherduck import MotherDuckBackend


def test_local_backend_creates_parents(tmp_path: Path) -> None:
    """Assert parent directories are created on write."""
    target = tmp_path / "deep" / "nested" / "stats.duckdb"
    backend = LocalDuckDBBackend(target)
    with backend.connect() as con:
        con.execute("CREATE TABLE probe (i INTEGER)")
        con.execute("INSERT INTO probe VALUES (42)")
    assert target.exists()


def test_local_backend_read_only_round_trip(tmp_path: Path) -> None:
    """Assert data written then re-opened read-only reads back."""
    target = tmp_path / "stats.duckdb"
    backend = LocalDuckDBBackend(target)
    with backend.connect() as con:
        con.execute("CREATE TABLE probe (i INTEGER)")
        con.execute("INSERT INTO probe VALUES (42)")
    with backend.connect(read_only=True) as con:
        assert con.execute("SELECT i FROM probe").fetchone() == (42,)


def test_local_backend_expands_user() -> None:
    """Assert tilde expansion on the database path."""
    backend = LocalDuckDBBackend("~/tokledger-test.duckdb")
    assert "~" not in str(backend.database)


def test_motherduck_rejects_prefixed_name() -> None:
    """Assert md:-prefixed database names are rejected."""
    with pytest.raises(ValueError, match="database name"):
        MotherDuckBackend("md:tokledger")


def test_motherduck_rejects_empty_name() -> None:
    """Assert empty database names are rejected."""
    with pytest.raises(ValueError, match="database name"):
        MotherDuckBackend("")


def test_motherduck_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert a missing token raises before any connection attempt."""
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="MOTHERDUCK_TOKEN"):
        with MotherDuckBackend("tokledger").connect():
            pass


def test_backends_satisfy_protocol(tmp_path: Path) -> None:
    """Assert both concrete backends structurally fit DatabaseBackend."""

    def accept(backend: DatabaseBackend) -> None:
        """Accept any structurally conforming backend."""
        assert callable(backend.connect)

    accept(LocalDuckDBBackend(tmp_path / "protocol-check.duckdb"))
    accept(MotherDuckBackend("tokledger", token="placeholder"))
