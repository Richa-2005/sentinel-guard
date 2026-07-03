"""SQLite connection and initialization utilities for Sentinel Guard."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = BACKEND_DIR / "data" / "sentinel_storage.db"

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS transactions_ledger (
        card_id TEXT NOT NULL,
        device_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS merchant_history (
        card_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        PRIMARY KEY (card_id, merchant_id)
    );
    """,
    # Composite index for lightning-fast card velocity window lookups
    "CREATE INDEX IF NOT EXISTS idx_ledger_card_time ON transactions_ledger(card_id, timestamp);",
    
    # Composite index for high-performance fraud ring device tracking loops
    "CREATE INDEX IF NOT EXISTS idx_ledger_device_time ON transactions_ledger(device_id, timestamp);"
)


class SentinelDatabase:
    """Create configured SQLite connections and initialize the schema."""

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    def connect(self) -> sqlite3.Connection:
        """Open a connection configured for concurrent WAL-backed access."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row

        try:
            connection.execute("PRAGMA journal_mode=WAL;")
            connection.execute("PRAGMA synchronous=NORMAL;")
            connection.execute("PRAGMA foreign_keys=ON;")
            connection.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            connection.close()
            raise

        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection and commit or roll back its transaction."""
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, schema: Iterable[str] = SCHEMA_STATEMENTS) -> None:
        """Create the database file and apply all supplied schema statements."""
        with self.connection() as connection:
            for statement in schema:
                connection.execute(statement)


def initialize_database(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    schema: Iterable[str] = SCHEMA_STATEMENTS,
) -> SentinelDatabase:
    """Initialize SQLite storage and return its configured database manager."""
    database = SentinelDatabase(database_path)
    database.initialize(schema)
    return database


if __name__ == "__main__":
    database = initialize_database()
    print(f"SQLite database initialized at {database.database_path}")
