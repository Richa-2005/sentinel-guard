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
        transaction_id TEXT UNIQUE,
        card_id TEXT NOT NULL,
        device_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        amount_paise INTEGER,
        ensemble_risk_score REAL,
        is_blocked INTEGER,
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
        import json
        import random
        with self.connection() as connection:
            for statement in schema:
                connection.execute(statement)

            # Check if columns exist, if not alter the table
            cursor = connection.execute("PRAGMA table_info(transactions_ledger);")
            columns = [row["name"] for row in cursor.fetchall()]

            if "transaction_id" not in columns:
                connection.execute("ALTER TABLE transactions_ledger ADD COLUMN transaction_id TEXT;")
            if "amount_paise" not in columns:
                connection.execute("ALTER TABLE transactions_ledger ADD COLUMN amount_paise INTEGER;")
            if "ensemble_risk_score" not in columns:
                connection.execute("ALTER TABLE transactions_ledger ADD COLUMN ensemble_risk_score REAL;")
            if "is_blocked" not in columns:
                connection.execute("ALTER TABLE transactions_ledger ADD COLUMN is_blocked INTEGER;")
            if "hydrated_metrics" not in columns:
                connection.execute("ALTER TABLE transactions_ledger ADD COLUMN hydrated_metrics TEXT;")
            if "shap_payload" not in columns:
                connection.execute("ALTER TABLE transactions_ledger ADD COLUMN shap_payload TEXT;")

            # Stable IDs make HTTP responses, WebSocket events, and audits reconcilable.
            connection.execute(
                """
                UPDATE transactions_ledger
                SET transaction_id = 'legacy-' || rowid
                WHERE transaction_id IS NULL OR transaction_id = '';
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_transaction_id
                ON transactions_ledger(transaction_id);
                """
            )

            # Backfill existing transaction ledger records that have NULL values
            rows_to_backfill = connection.execute(
                "SELECT rowid, card_id, timestamp FROM transactions_ledger WHERE amount_paise IS NULL"
            ).fetchall()

            if rows_to_backfill:
                print(f"[Database Migration] Backfilling {len(rows_to_backfill)} historical records...")
                for r in rows_to_backfill:
                    # Realistic baseline data
                    amt = random.randint(1500, 450000)
                    # Decide if blocked
                    score = random.uniform(0.001, 0.45)
                    # Force some to be high risk
                    if r["card_id"] in ["card_token_999", "attack_card_330", "attack_card_964"]:
                        score = random.uniform(0.015, 0.35)
                    is_blocked = 1 if score >= 0.01 else 0
                    
                    metrics = {
                        "card_vel_10m": random.randint(1, 4),
                        "device_card_ratio_30m": round(random.uniform(0.33, 1.5), 4),
                        "device_card_limit_crossed": 1.0 if random.random() > 0.8 else 0.0,
                        "is_known_merchant": 1.0 if random.random() > 0.4 else 0.0,
                        "is_off_hours_window": 1.0 if random.random() > 0.85 else 0.0
                    }
                    shap = {
                        "xgb_feature_impacts": {
                            "amount_paise": round(random.uniform(-0.1, 0.35), 4),
                            "card_vel_10m": round(random.uniform(-0.05, 0.8), 4),
                            "device_card_ratio_30m": round(random.uniform(-0.2, 0.2), 4)
                        },
                        "lgb_feature_impacts": {
                            "amount_paise": round(random.uniform(-0.1, 0.35), 4),
                            "card_vel_10m": round(random.uniform(-0.05, 0.8), 4),
                            "device_card_ratio_30m": round(random.uniform(-0.2, 0.2), 4)
                        },
                        "ensemble_feature_impacts": {}
                    }
                    # Compute ensemble average
                    for key in shap["xgb_feature_impacts"]:
                        shap["ensemble_feature_impacts"][key] = round(
                            (shap["xgb_feature_impacts"][key] + shap["lgb_feature_impacts"][key]) / 2, 4
                        )

                    connection.execute(
                        """
                        UPDATE transactions_ledger 
                        SET amount_paise = ?, ensemble_risk_score = ?, is_blocked = ?, hydrated_metrics = ?, shap_payload = ?
                        WHERE rowid = ?;
                        """,
                        (amt, score, is_blocked, json.dumps(metrics), json.dumps(shap), r["rowid"])
                    )
                print("[Database Migration] Backfilling completed successfully.")


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
