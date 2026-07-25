"""Deterministic, idempotent sample data for an explicitly enabled demo runtime."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.audit_service import GENESIS_HASH, _calculate_audit_hash
from app.core.config import SystemRiskConfig


DEMO_PREFIX = "demo-v2-"
DEMO_TRANSACTION_COUNT = 72
DEMO_INTERVAL_HOURS = 0.62


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ensure_demo_environment(session: Session) -> None:
    """Populate a fresh demo database without altering existing project data."""
    exists = session.execute(
        text("SELECT 1 FROM transactions_ledger WHERE transaction_id LIKE 'demo-v2-%' LIMIT 1")
    ).first()
    if exists:
        now = datetime.now(timezone.utc)
        session.execute(
            text(
                "UPDATE transactions_ledger SET timestamp = :timestamp "
                "WHERE transaction_id = :transaction_id"
            ),
            [
                {
                    "transaction_id": f"{DEMO_PREFIX}{index + 1:03d}",
                    "timestamp": _utc(
                        now + timedelta(
                            hours=-(DEMO_TRANSACTION_COUNT - index)
                            * DEMO_INTERVAL_HOURS
                        )
                    ),
                }
                for index in range(DEMO_TRANSACTION_COUNT)
            ],
        )
        session.commit()
        return

    now = datetime.now(timezone.utc)
    merchants = ("5411", "5732", "5812", "5999", "7995")
    blocked_ids: list[str] = []
    rows = []

    for index in range(DEMO_TRANSACTION_COUNT):
        offset = -(DEMO_TRANSACTION_COUNT - index) * DEMO_INTERVAL_HOURS
        timestamp = now + timedelta(hours=offset)
        elevated = index % 6 == 0 or index % 11 == 0
        threshold = SystemRiskConfig.CALIBRATED_THRESHOLD
        score = (
            round(min(0.998, threshold + 0.004 + (index % 5) * 0.008), 6)
            if elevated
            else round(min(threshold - 0.03, 0.018 + (index % 9) * 0.031), 6)
        )
        blocked = score >= threshold
        transaction_id = f"{DEMO_PREFIX}{index + 1:03d}"
        if blocked:
            blocked_ids.append(transaction_id)
        velocity = 4 if blocked else index % 3
        metrics = {
            "card_vel_10m": velocity,
            "device_card_ratio_30m": 0.91 if blocked else round(0.12 + (index % 4) * 0.09, 2),
            "device_card_limit_crossed": 1 if blocked and index % 2 == 0 else 0,
            "is_known_merchant": 0 if blocked else 1,
            "is_off_hours_window": 1 if timestamp.hour < 6 or timestamp.hour > 22 else 0,
        }
        risk_impacts = {
            "amount_paise": 0.08,
            "card_vel_10m": 0.31 if blocked else -0.12,
            "device_card_ratio_30m": 0.24 if blocked else -0.18,
            "device_card_limit_crossed": 0.2 if metrics["device_card_limit_crossed"] else -0.04,
            "is_known_merchant": 0.12 if not metrics["is_known_merchant"] else -0.22,
            "is_off_hours_window": 0.05 if metrics["is_off_hours_window"] else -0.03,
        }
        shap = {
            "xgb_normalized_impacts": risk_impacts,
            "lgb_normalized_impacts": {key: round(value * (0.88 if position % 2 else 1.08), 4) for position, (key, value) in enumerate(risk_impacts.items())},
        }
        rows.append({
            "transaction_id": transaction_id,
            "card_id": f"card_token_{210 + index % 18}",
            "device_id": f"device_{'ring' if blocked else 'trusted'}_{index % 12:02d}",
            "merchant_id": merchants[index % len(merchants)],
            "timestamp": _utc(timestamp),
            "amount_paise": 149900 + index * 1731 if blocked else 1299 + index * 619,
            "ensemble_risk_score": score,
            "is_blocked": int(blocked),
            "hydrated_metrics": json.dumps(metrics),
            "shap_payload": json.dumps(shap),
        })

    session.execute(text("""
        INSERT INTO transactions_ledger (
            transaction_id, card_id, device_id, merchant_id, timestamp,
            amount_paise, ensemble_risk_score, is_blocked,
            hydrated_metrics, shap_payload
        ) VALUES (
            :transaction_id, :card_id, :device_id, :merchant_id, :timestamp,
            :amount_paise, :ensemble_risk_score, :is_blocked,
            :hydrated_metrics, :shap_payload
        )
    """), rows)

    analyst = session.execute(
        text("SELECT id FROM users WHERE email = 'demo.analyst@sentinelguard.dev'")
    ).mappings().one()
    admin = session.execute(
        text("SELECT id FROM users WHERE email = 'demo.admin@sentinelguard.dev'")
    ).mappings().one()
    review_states = (
        ("resolved", "confirmed_fraud", "confirmed_fraud", 4),
        ("resolved", "false_positive", "false_positive", 4),
        ("awaiting_approval", "needs_more_information", None, 3),
        ("in_review", None, None, 2),
        ("open", None, None, 1),
        ("open", None, None, 1),
    )
    recent_blocked_ids = blocked_ids[-6:]
    for position, transaction_id in enumerate(recent_blocked_ids):
        status_value, recommendation, final_decision, version = review_states[position]
        score = next(row["ensemble_risk_score"] for row in rows if row["transaction_id"] == transaction_id)
        critical_boundary = SystemRiskConfig.CALIBRATED_THRESHOLD + ((1.0 - SystemRiskConfig.CALIBRATED_THRESHOLD) * 0.65)
        priority = "critical" if score >= critical_boundary else "high"
        assigned = analyst["id"] if status_value != "open" else None
        created_at = now - timedelta(minutes=75 - position * 8)
        resolved_at = created_at + timedelta(minutes=18 + position * 4) if status_value == "resolved" else None
        case_result = session.execute(text("""
            INSERT INTO review_cases (
                transaction_id, status, priority, assigned_to_user_id,
                analyst_recommendation, final_decision, version,
                created_at, updated_at, resolved_at
            ) VALUES (
                :transaction_id, :status, :priority, :assigned, :recommendation,
                :final_decision,
                :version, :created_at, :updated_at, :resolved_at
            )
        """), {
            "transaction_id": transaction_id,
            "status": status_value,
            "priority": priority,
            "assigned": assigned,
            "recommendation": recommendation,
            "final_decision": final_decision,
            "version": version,
            "created_at": created_at,
            "updated_at": resolved_at or created_at,
            "resolved_at": resolved_at,
        })
        case_id = case_result.lastrowid
        session.execute(text("""
            INSERT INTO review_actions (
                case_id, actor_user_id, action_type, previous_status,
                resulting_status, decision, reason, case_version, created_at
            ) VALUES (
                :case_id, NULL, 'created', NULL, 'open', NULL,
                'Automatically opened for a blocked model decision', 1, :created_at
            )
        """), {"case_id": case_id, "created_at": created_at})
        if version >= 2:
            session.execute(text("""
                INSERT INTO review_actions (
                    case_id, actor_user_id, action_type, previous_status,
                    resulting_status, decision, reason, case_version, created_at
                ) VALUES (
                    :case_id, :actor, 'assigned', 'open', 'in_review', NULL,
                    'Administrator assigned the case to the demo analyst', 2, :created_at
                )
            """), {"case_id": case_id, "actor": admin["id"], "created_at": created_at + timedelta(minutes=3)})
        if version >= 3:
            session.execute(text("""
                INSERT INTO review_actions (
                    case_id, actor_user_id, action_type, previous_status,
                    resulting_status, decision, reason, case_version, created_at
                ) VALUES (
                    :case_id, :actor, 'recommendation_submitted', 'in_review',
                    'awaiting_approval', :decision,
                    'Analyst recommendation based on velocity, device reuse, and merchant context',
                    3, :created_at
                )
            """), {"case_id": case_id, "actor": analyst["id"], "decision": recommendation, "created_at": created_at + timedelta(minutes=22)})
        if version >= 4:
            session.execute(text("""
                INSERT INTO review_actions (
                    case_id, actor_user_id, action_type, previous_status,
                    resulting_status, decision, reason, case_version, created_at
                ) VALUES (
                    :case_id, :actor, 'final_decision_submitted', 'awaiting_approval',
                    'resolved', :decision,
                    'Administrator finalized the case after reviewing the analyst evidence',
                    4, :created_at
                )
            """), {"case_id": case_id, "actor": admin["id"], "decision": final_decision, "created_at": resolved_at})

    previous_hash = GENESIS_HASH
    for position, transaction_id in enumerate(recent_blocked_ids[:5]):
        created_at = _utc(now - timedelta(minutes=55 - position * 7))
        transaction = next(row for row in rows if row["transaction_id"] == transaction_id)
        metrics = json.loads(transaction["hydrated_metrics"])
        memo = f"""# Sentinel Guard compliance incident memorandum

## A. Executive risk verdict

Transaction **{transaction_id}** was blocked after its ensemble risk score reached **{transaction['ensemble_risk_score']:.3f}**, above the deployed decision boundary of **{SystemRiskConfig.CALIBRATED_THRESHOLD:.3f}**. The decision is supported by rapid card reuse, concentrated device identity and an unfamiliar merchant relationship.

## B. Technical specification profile

- Amount: **₹{transaction['amount_paise'] / 100:,.2f}**
- Card identity: `{transaction['card_id']}`
- Device identity: `{transaction['device_id']}`
- Merchant category: `{transaction['merchant_id']}`
- Card velocity in ten minutes: **{metrics['card_vel_10m']}**
- Device-to-card ratio: **{metrics['device_card_ratio_30m']}**
- Known merchant indicator: **{metrics['is_known_merchant']}**

Both tree models placed their strongest positive weight on card velocity and device reuse. The ensemble agreement makes this a high-confidence intervention, while the individual feature contributions remain available to the assigned reviewer.

## C. Compliance cross-reference

The synthetic demonstration control corpus requires traceable automated decisions, retained model evidence and attributable human review for blocked payment activity. This portfolio fixture is illustrative and must not be treated as legal guidance.

## D. Mitigation and actionable defence roadmap

1. Preserve the transaction payload and model contribution evidence.
2. Assign an analyst to validate cardholder, device and merchant context.
3. Restrict related device and card identities until the administrator records a final verdict.
4. Monitor subsequent attempts for coordinated velocity or identity reuse.

This memorandum records the automated intervention. Human recommendation and final administrative disposition remain separate, attributable events in the review history.
"""
        current_hash = _calculate_audit_hash(
            transaction_id=transaction_id,
            event_type="TRANSACTION_BLOCKED",
            compliance_memo=memo,
            created_at=created_at,
            previous_hash=previous_hash,
        )
        session.execute(text("""
            INSERT INTO audit_vault (
                transaction_id, event_type, compliance_memo, created_at,
                previous_hash, current_hash
            ) VALUES (
                :transaction_id, 'TRANSACTION_BLOCKED', :memo, :created_at,
                :previous_hash, :current_hash
            )
        """), {
            "transaction_id": transaction_id,
            "memo": memo,
            "created_at": created_at,
            "previous_hash": previous_hash,
            "current_hash": current_hash,
        })
        session.execute(text("""
            INSERT INTO audit_jobs (
                transaction_id, status, attempts, created_at, started_at,
                completed_at, next_attempt_at
            ) VALUES (
                :transaction_id, 'COMPLETED', 1, :created_at, :created_at,
                :created_at, :created_at
            )
        """), {"transaction_id": transaction_id, "created_at": created_at})
        previous_hash = current_hash

    session.commit()
