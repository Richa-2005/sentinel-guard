"""Authenticated audit-chain integrity endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth_dependencies import CurrentUser
from app.core.database import SentinelDatabase
from app.schemas.audit import AuditChainVerification
from app.services.audit_service import AuditVaultService


router = APIRouter(prefix="/api/v1/audits", tags=["Audit Integrity"])


def get_audit_vault_service() -> AuditVaultService:
    """Construct the verifier against the configured runtime database."""
    return AuditVaultService(SentinelDatabase())


AuditService = Annotated[AuditVaultService, Depends(get_audit_vault_service)]


@router.get("/verify", response_model=AuditChainVerification)
def verify_audit_chain(
    _current_user: CurrentUser,
    audit_service: AuditService,
):
    """Recompute every audit hash and validate every chain link."""
    return audit_service.verify_chain()
