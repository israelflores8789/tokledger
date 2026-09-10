# SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
# SPDX-License-Identifier: MIT

"""duckdb_local.py — Local-file DuckDB backend."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb


class LocalDuckDBBackend:
    """Open a local DuckDB database file.

    Attributes:
        database: Resolved path to the local DuckDB database file.
    """

    def __init__(self, database: str | Path) -> None:
        """Initialize the backend with a database file path.

        Args:
            database: Path to the database file; parent directories are
                created for writable connections.
        """
        self.database = Path(database).expanduser()

    @contextmanager
    def connect(
        self,
        *,
        read_only: bool = False,
    ) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open and close a local DuckDB connection.

        Args:
            read_only: Open the file read-only; the file must exist.

        Yields:
            An active DuckDB Python connection.
        """
        if not read_only:
            self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(self.database), read_only=read_only)
        try:
            yield connection
        finally:
            connection.close()
