"""Structured API responses for operational model monitoring."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MonitoringWindow(BaseModel):
    hours: int = Field(ge=1)
    start: datetime
    end: datetime


class MonitoredModel(BaseModel):
    name: str
    decision_threshold: float = Field(ge=0, le=1)
    feature_dimensions: list[str]


class ScoreBucket(BaseModel):
    lower_bound: float = Field(ge=0, le=1)
    upper_bound: float = Field(ge=0, le=1)
    count: int = Field(ge=0)
    rate: float | None = Field(default=None, ge=0, le=1)


class PredictionMetrics(BaseModel):
    total: int = Field(ge=0)
    blocked: int = Field(ge=0)
    allowed: int = Field(ge=0)
    blocked_rate: float | None = Field(default=None, ge=0, le=1)
    average_risk_score: float | None = Field(default=None, ge=0, le=1)
    minimum_risk_score: float | None = Field(default=None, ge=0, le=1)
    maximum_risk_score: float | None = Field(default=None, ge=0, le=1)
    score_buckets: list[ScoreBucket]


class HumanReviewMetrics(BaseModel):
    cases_created: int = Field(ge=0)
    reviewed: int = Field(ge=0)
    open: int = Field(ge=0)
    in_review: int = Field(ge=0)
    escalated: int = Field(ge=0)
    resolved: int = Field(ge=0)
    confirmed_fraud: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    needs_more_information: int = Field(ge=0)
    case_coverage_rate: float | None = Field(default=None, ge=0, le=1)
    decision_completion_rate: float | None = Field(default=None, ge=0, le=1)
    confirmed_fraud_rate: float | None = Field(default=None, ge=0, le=1)
    false_positive_rate: float | None = Field(default=None, ge=0, le=1)
    average_resolution_seconds: float | None = Field(default=None, ge=0)
    p95_resolution_seconds: float | None = Field(default=None, ge=0)


class ScoreDriftMetrics(BaseModel):
    method: Literal["population_stability_index"]
    current_sample_size: int = Field(ge=0)
    previous_sample_size: int = Field(ge=0)
    minimum_sample_size: int = Field(ge=1)
    psi: float | None = Field(default=None, ge=0)
    level: Literal[
        "insufficient_data",
        "stable",
        "moderate_shift",
        "significant_shift",
    ]


class ModelMonitoringReport(BaseModel):
    generated_at: datetime
    window: MonitoringWindow
    model: MonitoredModel
    predictions: PredictionMetrics
    human_review: HumanReviewMetrics
    score_drift: ScoreDriftMetrics
