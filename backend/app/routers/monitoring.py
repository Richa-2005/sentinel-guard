"""Administrator-only operational model monitoring endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth_dependencies import AdminUser
from app.core.database import SentinelDatabase
from app.schemas.monitoring import ModelMonitoringReport
from app.services.monitoring_service import ModelMonitoringService


router = APIRouter(prefix="/api/v1/monitoring", tags=["Model Monitoring"])


def get_model_monitoring_service() -> ModelMonitoringService:
    """Construct monitoring against the configured runtime database."""
    return ModelMonitoringService(SentinelDatabase())


MonitoringService = Annotated[
    ModelMonitoringService,
    Depends(get_model_monitoring_service),
]


@router.get("/model", response_model=ModelMonitoringReport)
def read_model_monitoring(
    _admin: AdminUser,
    monitoring_service: MonitoringService,
    window_hours: int = Query(default=24, ge=1, le=720),
):
    """Return prediction, review-outcome, latency, and score-shift metrics."""
    return monitoring_service.build_report(window_hours=window_hours)
