import json
import re
from app.config import settings
from fastapi import HTTPException

def parse_compliance_vault_logs(db):
    """
    Parses on-disk logs and SQLite snapshots into structured data lists for React tabs bootstrapping.
    """
    try:
        if not settings.LOG_FILE_PATH.exists():
            return []
        
        with open(settings.LOG_FILE_PATH, "r", encoding="utf-8") as f:
            log_contents = f.read()

        raw_lines = log_contents.splitlines()
        entries = []
        current_entry = []

        for line in raw_lines:
            is_start = line.startswith("AUDIT ENTRY [") or \
                       "NEXUS FINTECH COMPLIANCE INCIDENT REPORT" in line or \
                       line.startswith("LLM Generation Connection Timeout Error:")
                       
            if is_start and current_entry:
                entries.append("\n".join(current_entry).strip())
                current_entry = []
            current_entry.append(line)

        if current_entry:
            entries.append("\n".join(current_entry).strip())

        parsed_entries = []
        for i, entry_text in enumerate(entries):
            if not entry_text.strip():
                continue

            card_match = re.search(r"Card\s+ID\s*:\s*\*?\*?([a-zA-Z0-9_\-]+)", entry_text, re.IGNORECASE)
            card_id = card_match.group(1).strip() if card_match else "unknown"

            time_match = re.search(r"AUDIT ENTRY\s*\[([^\]]+)\]", entry_text, re.IGNORECASE)
            timestamp = time_match.group(1).strip() if time_match else None
            
            if not timestamp:
                dt_match = re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", entry_text)
                timestamp = dt_match.group(0)[1:-1] if dt_match else "Historical Entry"

            prev_hash_match = re.search(r"PREVIOUS_ENTRY_HASH\s*:\s*([a-fA-F0-9]+)", entry_text, re.IGNORECASE)
            curr_hash_match = re.search(r"CURRENT_RECORD_HASH\s*:\s*([a-fA-F0-9]+)", entry_text, re.IGNORECASE)

            parsed_entries.append({
                "id": i + 1,
                "card_id": card_id,
                "timestamp": timestamp,
                "previous_hash": prev_hash_match.group(1).strip() if prev_hash_match else None,
                "current_hash": curr_hash_match.group(1).strip() if curr_hash_match else None,
                "report_text": entry_text,
                "is_error": "Connection Timeout Error" in entry_text or "Generation Failed" in entry_text
            })

        return parsed_entries[::-1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit logs: {str(e)}")