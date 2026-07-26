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
        ensemble_risk_score REAL NOT NULL CHECK (ensemble_risk_score >= 0 AND ensemble_risk_score <= 1),
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
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        previous_hash TEXT NOT NULL CHECK (length(previous_hash) = 64),
        current_hash TEXT NOT NULL UNIQUE CHECK (length(current_hash) = 64),
        UNIQUE (transaction_id, event_type),
        FOREIGN KEY (transaction_id) REFERENCES transactions_ledger(transaction_id) ON UPDATE RESTRICT ON DELETE RESTRICT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_jobs (
        transaction_id TEXT PRIMARY KEY NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        started_at TEXT,
        completed_at TEXT,
        last_error TEXT,
        next_attempt_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (transaction_id) REFERENCES transactions_ledger(transaction_id) ON UPDATE RESTRICT ON DELETE RESTRICT
    );
    """,

    
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        full_name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'analyst' CHECK (role IN ('analyst', 'admin')),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    );
    """,

    
    """
    CREATE TABLE IF NOT EXISTS review_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_review', 'awaiting_approval', 'resolved', 'escalated')),
        priority TEXT NOT NULL DEFAULT 'high' CHECK (priority IN ('high', 'critical')),
        assigned_to_user_id INTEGER,
        analyst_recommendation TEXT CHECK (analyst_recommendation IS NULL OR analyst_recommendation IN ('confirmed_fraud', 'false_positive', 'needs_more_information')),
        final_decision TEXT CHECK (final_decision IS NULL OR final_decision IN ('confirmed_fraud', 'false_positive', 'needs_more_information')),
        version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        resolved_at TEXT,
        FOREIGN KEY (transaction_id) REFERENCES transactions_ledger(transaction_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (assigned_to_user_id) REFERENCES users(id) ON UPDATE RESTRICT ON DELETE SET NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS review_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        actor_user_id INTEGER,
        action_type TEXT NOT NULL CHECK (action_type IN ('created', 'claimed', 'assigned', 'decision_submitted', 'reopened', 'overridden', 'recommendation_submitted', 'final_decision_submitted', 'returned_for_evidence')),
        previous_status TEXT CHECK (previous_status IS NULL OR previous_status IN ('open', 'in_review', 'awaiting_approval', 'resolved', 'escalated')),
        resulting_status TEXT NOT NULL CHECK (resulting_status IN ('open', 'in_review', 'awaiting_approval', 'resolved', 'escalated')),
        decision TEXT CHECK (decision IS NULL OR decision IN ('confirmed_fraud', 'false_positive', 'needs_more_information')),
        reason TEXT NOT NULL CHECK (length(trim(reason)) >= 2),
        case_version INTEGER NOT NULL CHECK (case_version > 0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (case_id) REFERENCES review_cases(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
        FOREIGN KEY (actor_user_id) REFERENCES users(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
        UNIQUE (case_id, case_version)
    );
    """,


    "CREATE INDEX IF NOT EXISTS idx_ledger_card_time ON transactions_ledger(card_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_ledger_device_time ON transactions_ledger(device_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_ledger_timestamp ON transactions_ledger(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_audit_jobs_ready ON audit_jobs(status, next_attempt_at);",
    "CREATE INDEX IF NOT EXISTS idx_review_cases_queue ON review_cases(status, priority, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_review_cases_status ON review_cases(status);",
    "CREATE INDEX IF NOT EXISTS idx_review_cases_assignee ON review_cases(assigned_to_user_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_review_actions_case_time ON review_actions(case_id, created_at);",

    
    """
    CREATE TRIGGER IF NOT EXISTS prevent_audit_vault_update BEFORE UPDATE ON audit_vault
    BEGIN SELECT RAISE(ABORT, 'audit_vault records are immutable and cannot be updated'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS prevent_audit_vault_delete BEFORE DELETE ON audit_vault
    BEGIN SELECT RAISE(ABORT, 'audit_vault records are immutable and cannot be deleted'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS prevent_review_actions_update BEFORE UPDATE ON review_actions
    BEGIN SELECT RAISE(ABORT, 'review_actions records are immutable and cannot be updated'); END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS prevent_review_actions_delete BEFORE DELETE ON review_actions
    BEGIN SELECT RAISE(ABORT, 'review_actions records are immutable and cannot be deleted'); END;
    """
)

class SentinelDatabase:
    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    def connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=30.0, check_same_thread=False)
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
        with self.connection() as connection:
            for statement in schema:
                connection.execute(statement)

def initialize_database(
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    schema: Iterable[str] = SCHEMA_STATEMENTS,
) -> SentinelDatabase:
    database = SentinelDatabase(database_path)
    database.initialize(schema)
    return database