"""SQLite connection and initialization utilities for Sentinel Guard."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import settings


DEFAULT_DATABASE_PATH = settings.SENTINEL_DATABASE_PATH

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS transactions_ledger (
        transaction_id TEXT PRIMARY KEY NOT NULL,
        card_id TEXT NOT NULL,
        device_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        amount_paise INTEGER NOT NULL CHECK (amount_paise >= 0),
        ensemble_risk_score REAL NOT NULL
            CHECK (ensemble_risk_score >= 0 AND ensemble_risk_score <= 1),
        is_blocked INTEGER NOT NULL CHECK (is_blocked IN (0, 1)),
        hydrated_metrics TEXT,
        shap_payload TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS merchant_history (
        card_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        PRIMARY KEY (card_id, merchant_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_vault (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        compliance_memo TEXT NOT NULL,
        created_at TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        previous_hash TEXT NOT NULL
            CHECK (length(previous_hash) = 64),
        current_hash TEXT NOT NULL UNIQUE
            CHECK (length(current_hash) = 64),

        UNIQUE (transaction_id, event_type),

        FOREIGN KEY (transaction_id)
            REFERENCES transactions_ledger(transaction_id)
            ON UPDATE RESTRICT
            ON DELETE RESTRICT
    );
    """,
    # Composite index for lightning-fast card velocity window lookups
    "CREATE INDEX IF NOT EXISTS idx_ledger_card_time ON transactions_ledger(card_id, timestamp);",
    
    # Composite index for high-performance fraud ring device tracking loops
    "CREATE INDEX IF NOT EXISTS idx_ledger_device_time ON transactions_ledger(device_id, timestamp);",

    # Make the audit table append-only by blocking updates and deletes.
    """
    CREATE TRIGGER IF NOT EXISTS prevent_audit_vault_update
    BEFORE UPDATE ON audit_vault
    BEGIN
        SELECT RAISE(
            ABORT,
            'audit_vault records are immutable and cannot be updated'
        );
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS prevent_audit_vault_delete
    BEFORE DELETE ON audit_vault
    BEGIN
        SELECT RAISE(
            ABORT,
            'audit_vault records are immutable and cannot be deleted'
        );
    END;
    """,

    """
    CREATE TABLE IF NOT EXISTS audit_jobs (
        transaction_id TEXT PRIMARY KEY NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
        attempts INTEGER NOT NULL DEFAULT 0
            CHECK (attempts >= 0),
        created_at TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        started_at TEXT,
        completed_at TEXT,
        last_error TEXT,
        next_attempt_at TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

        FOREIGN KEY (transaction_id)
            REFERENCES transactions_ledger(transaction_id)
            ON UPDATE RESTRICT
            ON DELETE RESTRICT
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_audit_jobs_ready
    ON audit_jobs(status, next_attempt_at);
    """
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
