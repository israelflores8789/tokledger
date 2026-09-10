# SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
# SPDX-License-Identifier: MIT

"""motherduck.py — MotherDuck backend using DuckDB's MotherDuck connection URI."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import quote

import duckdb


class MotherDuckBackend:
    """Open a MotherDuck database through DuckDB's `md:` URI.

    Attributes:
        database: MotherDuck database name, without the `md:` prefix.
    """

    def __init__(self, database: str, *, token: str | None = None) -> None:
        """Initialize the backend with a database name and optional token.

        Args:
            database: MotherDuck database name (no `md:` prefix).
            token: Service-account or user token. If omitted, the backend
                reads `MOTHERDUCK_TOKEN` when opening a connection.

        Raises:
            ValueError: If the database name is empty or already prefixed.
        """
        if not database or database.startswith("md:"):
            raise ValueError("database must be a non-empty MotherDuck database name")
        self.database = database
        self._token = token

    @contextmanager
    def connect(
        self,
        *,
        read_only: bool = False,
    ) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open and close a MotherDuck connection.

        Args:
            read_only: Requested read-only mode; MotherDuck enforces
                permissions server-side, so this is advisory.

        Yields:
            An active DuckDB Python connection.

        Raises:
            RuntimeError: If no MotherDuck token is available.
        """
        token = self._token or os.environ.get("MOTHERDUCK_TOKEN")
        if not token:
            raise RuntimeError("MOTHERDUCK_TOKEN is required for MotherDuck connections")
        uri = f"md:{self.database}?motherduck_token={quote(token, safe='')}"
        connection = duckdb.connect(uri, read_only=read_only)
        try:
            yield connection
        finally:
            connection.close()
