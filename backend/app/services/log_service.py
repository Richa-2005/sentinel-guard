"""Parse persisted compliance reports into stable frontend audit records."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from app.config import settings


AUDIT_ID_PATTERN = re.compile(
    r"^AUDIT SYSTEM ID\s*:\s*([a-zA-Z0-9_-]+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
LEGACY_START_PATTERNS = (
    re.compile(r"^AUDIT ENTRY \[", re.IGNORECASE),
    re.compile(r"NEXUS FINTECH COMPLIANCE INCIDENT REPORT", re.IGNORECASE),
    re.compile(r"^LLM Generation Connection Timeout Error:", re.IGNORECASE),
)


def _split_legacy_entries(text: str) -> list[str]:
    """Split records written before transaction correlation IDs were introduced."""
    entries: list[str] = []
    current: list[str] = []

    for line in text.splitlines():
        is_start = any(pattern.search(line) for pattern in LEGACY_START_PATTERNS)
        if is_start and current and any(part.strip() for part in current):
            entries.append("\n".join(current).strip())
            current = []
        current.append(line)

    if current and any(part.strip() for part in current):
        entries.append("\n".join(current).strip())
    return entries


def _split_audit_entries(log_contents: str) -> list[str]:
    """Keep each new AUDIT SYSTEM ID header attached to its complete report."""
    matches = list(AUDIT_ID_PATTERN.finditer(log_contents))
    if not matches:
        return _split_legacy_entries(log_contents)

    entries: list[str] = []
    legacy_prefix = log_contents[: matches[0].start()]
    entries.extend(_split_legacy_entries(legacy_prefix))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(log_contents)
        entry = log_contents[match.start() : end].strip()
        if entry:
            entries.append(entry)
    return entries


def _transaction_metadata(db: Any, transaction_id: str | None) -> dict[str, str]:
    """Enrich an audit from the ledger when the migrated correlation column exists."""
    if not transaction_id:
        return {}

    try:
        with db.connection() as connection:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(transactions_ledger)").fetchall()
            }
            if "transaction_id" not in columns:
                return {}
            row = connection.execute(
                """
                SELECT card_id, timestamp
                FROM transactions_ledger
                WHERE transaction_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (transaction_id,),
            ).fetchone()
            return dict(row) if row else {}
    except Exception:
        # Parsing historical files must remain available during schema migration.
        return {}


def _extract_card_id(entry_text: str) -> str:
    patterns = (
        r'"card_id"\s*:\s*"([a-zA-Z0-9_-]+)"',
        r"Card\s+ID\s*:\s*\*?\*?([a-zA-Z0-9_-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, entry_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "unknown"


def _extract_timestamp(entry_text: str) -> str:
    patterns = (
        r"AUDIT ENTRY\s*\[([^\]]+)\]",
        r"\[(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]",
    )
    for pattern in patterns:
        match = re.search(pattern, entry_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "Historical Entry"


def parse_compliance_vault_logs(db):
    """Return newest-first structured audits with stable transaction correlation."""
    try:
        if not settings.LOG_FILE_PATH.exists():
            return []

        log_contents = settings.LOG_FILE_PATH.read_text(encoding="utf-8")
        parsed_entries = []

        for index, entry_text in enumerate(_split_audit_entries(log_contents), start=1):
            if not entry_text.strip():
                continue

            tx_match = AUDIT_ID_PATTERN.search(entry_text)
            transaction_id = tx_match.group(1).strip() if tx_match else None
            metadata = _transaction_metadata(db, transaction_id)
            previous_hash = re.search(
                r"PREVIOUS_ENTRY_HASH\s*:\s*([a-fA-F0-9]+)", entry_text, re.IGNORECASE
            )
            current_hash = re.search(
                r"CURRENT_RECORD_HASH\s*:\s*([a-fA-F0-9]+)", entry_text, re.IGNORECASE
            )
            is_error = (
                "Connection Timeout Error" in entry_text
                or "Generation Failed" in entry_text
            )

            stable_id = transaction_id or f"legacy-{index}"
            parsed_entries.append(
                {
                    "id": stable_id,
                    "transaction_id": transaction_id,
                    "card_id": metadata.get("card_id") or _extract_card_id(entry_text),
                    "timestamp": metadata.get("timestamp") or _extract_timestamp(entry_text),
                    "previous_hash": previous_hash.group(1).strip() if previous_hash else None,
                    "current_hash": current_hash.group(1).strip() if current_hash else None,
                    "report_text": entry_text,
                    "is_error": is_error,
                    "status": "failed" if is_error else "complete",
                }
            )

        return parsed_entries[::-1]
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch audit logs: {error}",
        ) from error
