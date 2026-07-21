"""Structured responses for audit-chain integrity verification."""

from datetime import datetime

from pydantic import BaseModel, Field


class AuditChainIssue(BaseModel):
    """One integrity failure discovered at an audit record."""

    record_id: int
    code: str
    message: str


class AuditChainVerification(BaseModel):
    """Complete verification result for the current audit-vault snapshot."""

    is_valid: bool
    records_checked: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    issues: list[AuditChainIssue]
    first_invalid_record_id: int | None
    genesis_hash: str = Field(min_length=64, max_length=64)
    head_hash: str = Field(min_length=64, max_length=64)
    checked_at: datetime
