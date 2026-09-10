# SPDX-FileCopyrightText: 2026 Israel Flores-Arbolay
# SPDX-License-Identifier: MIT

"""base.py — Backend connection contracts shared by DuckDB and MotherDuck."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol

import duckdb


class DatabaseBackend(Protocol):
    """A backend capable of opening a DuckDB-compatible connection."""

    def connect(
        self,
        *,
        read_only: bool = False,
    ) -> AbstractContextManager[duckdb.DuckDBPyConnection]:
        """Open a database connection managed by a context manager.

        Args:
            read_only: Open the underlying database without write access.

        Returns:
            A context manager yielding an active DuckDB connection.
        """
        ...
