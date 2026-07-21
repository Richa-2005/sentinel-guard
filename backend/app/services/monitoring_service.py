"""Operational model monitoring derived from predictions and human outcomes."""

import math
from datetime import datetime, timedelta, timezone

from app.core.config import SystemRiskConfig
from app.core.database import SentinelDatabase


SCORE_BUCKETS: tuple[tuple[float, float], ...] = (
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0000001),
)
MINIMUM_DRIFT_SAMPLE_SIZE = 30
PSI_EPSILON = 1e-6


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    return round(
        ordered[lower] * (1 - weight) + ordered[upper] * weight,
        3,
    )


def _bucket_counts(scores: list[float]) -> list[int]:
    counts = [0] * len(SCORE_BUCKETS)
    for score in scores:
        for index, (lower, upper) in enumerate(SCORE_BUCKETS):
            if lower <= score < upper:
                counts[index] += 1
                break
    return counts


def _calculate_psi(current: list[int], previous: list[int]) -> float:
    current_total = sum(current)
    previous_total = sum(previous)
    value = 0.0
    for current_count, previous_count in zip(current, previous, strict=True):
        current_ratio = max(current_count / current_total, PSI_EPSILON)
        previous_ratio = max(previous_count / previous_total, PSI_EPSILON)
        value += (current_ratio - previous_ratio) * math.log(
            current_ratio / previous_ratio
        )
    return round(value, 6)


def _drift_level(psi: float) -> str:
    if psi < 0.1:
        return "stable"
    if psi < 0.25:
        return "moderate_shift"
    return "significant_shift"


class ModelMonitoringService:
    """Aggregate prediction behavior and human review feedback by time window."""

    def __init__(self, database: SentinelDatabase) -> None:
        self.database = database

    def build_report(
        self,
        *,
        window_hours: int = 24,
        now: datetime | None = None,
    ) -> dict[str, object]:
        if window_hours < 1:
            raise ValueError("window_hours must be positive")

        window_end = now or datetime.now(timezone.utc)
        if window_end.tzinfo is None:
            window_end = window_end.replace(tzinfo=timezone.utc)
        window_end = window_end.astimezone(timezone.utc)
        window_start = window_end - timedelta(hours=window_hours)
        previous_start = window_start - timedelta(hours=window_hours)

        with self.database.connection() as connection:
            current_rows = connection.execute(
                """
                SELECT ensemble_risk_score, is_blocked
                FROM transactions_ledger
                WHERE datetime(timestamp) >= datetime(?)
                  AND datetime(timestamp) < datetime(?)
                ORDER BY timestamp;
                """,
                (_isoformat_utc(window_start), _isoformat_utc(window_end)),
            ).fetchall()
            previous_rows = connection.execute(
                """
                SELECT ensemble_risk_score
                FROM transactions_ledger
                WHERE datetime(timestamp) >= datetime(?)
                  AND datetime(timestamp) < datetime(?)
                ORDER BY timestamp;
                """,
                (_isoformat_utc(previous_start), _isoformat_utc(window_start)),
            ).fetchall()
            review_row = connection.execute(
                """
                SELECT
                    COUNT(rc.id) AS case_count,
                    SUM(CASE WHEN rc.status = 'open' THEN 1 ELSE 0 END) AS open_count,
                    SUM(CASE WHEN rc.status = 'in_review' THEN 1 ELSE 0 END) AS in_review_count,
                    SUM(CASE WHEN rc.status = 'escalated' THEN 1 ELSE 0 END) AS escalated_count,
                    SUM(CASE WHEN rc.status = 'resolved' THEN 1 ELSE 0 END) AS resolved_count,
                    SUM(CASE WHEN rc.current_decision IS NOT NULL THEN 1 ELSE 0 END)
                        AS reviewed_count,
                    SUM(CASE WHEN rc.current_decision = 'confirmed_fraud' THEN 1 ELSE 0 END)
                        AS confirmed_fraud_count,
                    SUM(CASE WHEN rc.current_decision = 'false_positive' THEN 1 ELSE 0 END)
                        AS false_positive_count,
                    SUM(CASE WHEN rc.current_decision = 'needs_more_information' THEN 1 ELSE 0 END)
                        AS needs_more_information_count
                FROM review_cases AS rc
                JOIN transactions_ledger AS tx
                  ON tx.transaction_id = rc.transaction_id
                WHERE datetime(tx.timestamp) >= datetime(?)
                  AND datetime(tx.timestamp) < datetime(?);
                """,
                (_isoformat_utc(window_start), _isoformat_utc(window_end)),
            ).fetchone()
            latency_rows = connection.execute(
                """
                SELECT
                    (julianday(rc.resolved_at) - julianday(rc.created_at)) * 86400.0
                        AS resolution_seconds
                FROM review_cases AS rc
                JOIN transactions_ledger AS tx
                  ON tx.transaction_id = rc.transaction_id
                WHERE datetime(tx.timestamp) >= datetime(?)
                  AND datetime(tx.timestamp) < datetime(?)
                  AND rc.resolved_at IS NOT NULL
                  AND rc.resolved_at >= rc.created_at;
                """,
                (_isoformat_utc(window_start), _isoformat_utc(window_end)),
            ).fetchall()

        current_scores = [float(row["ensemble_risk_score"]) for row in current_rows]
        previous_scores = [float(row["ensemble_risk_score"]) for row in previous_rows]
        blocked_count = sum(int(row["is_blocked"]) for row in current_rows)
        total_predictions = len(current_rows)
        current_bucket_counts = _bucket_counts(current_scores)
        previous_bucket_counts = _bucket_counts(previous_scores)

        score_buckets = []
        for index, ((lower, upper), count) in enumerate(
            zip(SCORE_BUCKETS, current_bucket_counts, strict=True)
        ):
            score_buckets.append(
                {
                    "lower_bound": lower,
                    "upper_bound": 1.0 if index == len(SCORE_BUCKETS) - 1 else upper,
                    "count": count,
                    "rate": _safe_rate(count, total_predictions),
                }
            )

        drift_psi: float | None = None
        drift_level = "insufficient_data"
        if (
            len(current_scores) >= MINIMUM_DRIFT_SAMPLE_SIZE
            and len(previous_scores) >= MINIMUM_DRIFT_SAMPLE_SIZE
        ):
            drift_psi = _calculate_psi(
                current_bucket_counts,
                previous_bucket_counts,
            )
            drift_level = _drift_level(drift_psi)

        case_count = int(review_row["case_count"] or 0)
        reviewed_count = int(review_row["reviewed_count"] or 0)
        confirmed_count = int(review_row["confirmed_fraud_count"] or 0)
        false_positive_count = int(review_row["false_positive_count"] or 0)
        conclusive_count = confirmed_count + false_positive_count
        latencies = [
            max(0.0, float(row["resolution_seconds"]))
            for row in latency_rows
            if row["resolution_seconds"] is not None
        ]

        return {
            "generated_at": _isoformat_utc(datetime.now(timezone.utc)),
            "window": {
                "hours": window_hours,
                "start": _isoformat_utc(window_start),
                "end": _isoformat_utc(window_end),
            },
            "model": {
                "name": "xgboost_lightgbm_ensemble",
                "decision_threshold": SystemRiskConfig.CALIBRATED_THRESHOLD,
                "feature_dimensions": SystemRiskConfig.FEATURE_DIMENSIONS,
            },
            "predictions": {
                "total": total_predictions,
                "blocked": blocked_count,
                "allowed": total_predictions - blocked_count,
                "blocked_rate": _safe_rate(blocked_count, total_predictions),
                "average_risk_score": (
                    round(sum(current_scores) / total_predictions, 6)
                    if total_predictions
                    else None
                ),
                "minimum_risk_score": (
                    round(min(current_scores), 6) if current_scores else None
                ),
                "maximum_risk_score": (
                    round(max(current_scores), 6) if current_scores else None
                ),
                "score_buckets": score_buckets,
            },
            "human_review": {
                "cases_created": case_count,
                "reviewed": reviewed_count,
                "open": int(review_row["open_count"] or 0),
                "in_review": int(review_row["in_review_count"] or 0),
                "escalated": int(review_row["escalated_count"] or 0),
                "resolved": int(review_row["resolved_count"] or 0),
                "confirmed_fraud": confirmed_count,
                "false_positive": false_positive_count,
                "needs_more_information": int(
                    review_row["needs_more_information_count"] or 0
                ),
                "case_coverage_rate": _safe_rate(case_count, blocked_count),
                "decision_completion_rate": _safe_rate(
                    reviewed_count,
                    case_count,
                ),
                "confirmed_fraud_rate": _safe_rate(
                    confirmed_count,
                    conclusive_count,
                ),
                "false_positive_rate": _safe_rate(
                    false_positive_count,
                    conclusive_count,
                ),
                "average_resolution_seconds": (
                    round(sum(latencies) / len(latencies), 3)
                    if latencies
                    else None
                ),
                "p95_resolution_seconds": _percentile(latencies, 0.95),
            },
            "score_drift": {
                "method": "population_stability_index",
                "current_sample_size": len(current_scores),
                "previous_sample_size": len(previous_scores),
                "minimum_sample_size": MINIMUM_DRIFT_SAMPLE_SIZE,
                "psi": drift_psi,
                "level": drift_level,
            },
        }
