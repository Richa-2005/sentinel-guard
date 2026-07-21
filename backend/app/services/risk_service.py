import asyncio
import json
import uuid
from datetime import datetime, timedelta
from app.services.audit_service import AuditVaultService
from app.core.config import SystemRiskConfig
from app.core.database import SentinelDatabase
from app.services.engine_service import ml_executor, compute_ml_and_shap
from app.services.websocket_service import ws_manager
from app.services.review_service import ensure_review_case_for_blocked_transaction

db = SentinelDatabase()
audit_service = AuditVaultService(db)

async def _broadcast_safely(event: dict) -> None:
    """Broadcast without changing persisted audit state on socket failure."""
    try:
        await ws_manager.broadcast_event(event)
    except Exception as error:
        print(f"[WebSocket Warning] Broadcast failed: {error}")

def _compile_and_store_audit(
    transaction_id: str,
    compliance_agent,
    audit_service: AuditVaultService,
) -> dict[str, object]:
    """Load, generate, hash, and persist one compliance audit."""
    raw_data, hydrated_metrics, shap_payload = (
        audit_service.load_job_context(transaction_id)
    )

    final_memo = compliance_agent.run_graph_audit(
        transaction_data=raw_data,
        hydrated_metrics=hydrated_metrics,
        shap_payload=shap_payload,
    )

    return audit_service.append_audit(
        transaction_id=transaction_id,
        event_type="BLOCKED_TRANSACTION_AUDIT",
        compliance_memo=final_memo,
    )

async def process_agent_audit_worker(
    transaction_id: str,
    compliance_agent,
    audit_service: AuditVaultService,
) -> None:
    try:
        claimed = await asyncio.to_thread(
            audit_service.claim_job,
            transaction_id,
        )
    except Exception as error:
        print(
            f"[Audit Worker] Could not claim {transaction_id}: {error}"
        )
        return

    if not claimed:
        return

    try:
        audit_record = await asyncio.to_thread(
            _compile_and_store_audit,
            transaction_id,
            compliance_agent,
            audit_service,
        )
    except Exception as error:
        try:
            failure = await asyncio.to_thread(
                audit_service.record_job_failure,
                transaction_id,
                error,
            )
        except Exception as persistence_error:
            print(
                f"[Audit Worker] Could not record failure for "
                f"{transaction_id}: {persistence_error}"
            )
            return

        if failure["status"] == "PENDING":
            print(
                f"[Audit Worker] Audit {transaction_id} will retry at "
                f"{failure['next_attempt_at']}."
            )

            await _broadcast_safely({
                "type": "AUDIT_RETRY_SCHEDULED",
                "data": {
                    "transaction_id": transaction_id,
                    "status": "retry_scheduled",
                    "attempts": failure["attempts"],
                    "next_attempt_at": failure["next_attempt_at"],
                    "error": str(error),
                },
            })
        else:
            print(
                f"[Audit Worker] Audit {transaction_id} permanently failed "
                f"after {failure['attempts']} attempts."
            )

            await _broadcast_safely({
                "type": "AUDIT_FAILED",
                "data": {
                    "transaction_id": transaction_id,
                    "status": "failed",
                    "attempts": failure["attempts"],
                    "error": str(error),
                },
            })

        return

    print(
        f"[Audit Worker] Audit {audit_record['id']} for transaction "
        f"{transaction_id} stored in audit_vault."
    )

    await _broadcast_safely({
        "type": "AUDIT_COMPLETE",
        "data": {
            "id": audit_record["id"],
            "transaction_id": transaction_id,
            "status": "complete",
            "created_at": audit_record["created_at"],
            "current_hash": audit_record["current_hash"],
        },
    })

async def evaluate_and_persist_transaction(
        payload, background_tasks, 
        ensemble_gate, explainer_bridge, 
        compliance_agent
):
    """
    Handles complete feature aggregation, event loop compute insulation,
    database indexing transactions, and stateful live ticker broadcasts.
    """
    current_time = datetime.now()
    timestamp_now_str = current_time.isoformat()
    tx_id = payload.transaction_id if payload.transaction_id else str(uuid.uuid4())

    card_id = payload.card_id
    device_id = payload.device_id
    merchant = payload.merchant_id

    # Gather historical ledger metrics safely from persistent cache records
    with db.connection() as conn:
        last_10m = (current_time - timedelta(minutes=10)).isoformat()
        last_30m = (current_time - timedelta(minutes=30)).isoformat()
        last_24h = (current_time - timedelta(hours=24)).isoformat()

        row_vel = conn.execute(
            "SELECT COUNT(*) as cnt FROM transactions_ledger WHERE card_id = ? AND timestamp >= ?;",
            (card_id, last_10m)
        ).fetchone()
        card_vel_10m = row_vel["cnt"]

        
        row_ratio = conn.execute("""
            SELECT COUNT(DISTINCT card_id) as card_count
            FROM transactions_ledger
            WHERE device_id = ? AND timestamp >= ?;
        """, (device_id, last_30m)).fetchone()
        device_card_ratio_30m = float(row_ratio["card_count"] if row_ratio else 1.0)

        row_device = conn.execute(
            "SELECT COUNT(DISTINCT card_id) as cnt FROM transactions_ledger WHERE device_id = ? AND timestamp >= ?;",
            (device_id, last_24h)
        ).fetchone()
        device_card = row_device["cnt"]
        device_card_limit = 1.0 if device_card > 3 else 0.0

        row_merchant = conn.execute(
            "SELECT COUNT(*) as cnt FROM merchant_history WHERE card_id = ? AND merchant_id = ?;",
            (card_id, merchant)
        ).fetchone()
        is_known_merchant = 1.0 if row_merchant["cnt"] >= 1 else 0.0

    is_off_hours_window = 1.0 if (1 <= current_time.hour <= 5) else 0.0
    raw_features = [
        float(payload.amount_paise),
        card_vel_10m,
        device_card_ratio_30m,
        device_card_limit,
        is_known_merchant,
        is_off_hours_window,
    ]
    input_matrix = [raw_features]

    # Execute heavy math transformations inside non-blocking threads
    loop = asyncio.get_running_loop()
    ensemble_prob, shap_payload = await loop.run_in_executor(
        ml_executor, compute_ml_and_shap, raw_features, input_matrix, 
        ensemble_gate, explainer_bridge
    )

    is_blocked = ensemble_prob >= SystemRiskConfig.CALIBRATED_THRESHOLD
    review_case_id = None
    
    hydrated_metrics = {
        "card_vel_10m": card_vel_10m,
        "device_card_ratio_30m": round(device_card_ratio_30m, 4),
        "device_card_limit_crossed": device_card_limit,
        "is_known_merchant": is_known_merchant,
        "is_off_hours_window": is_off_hours_window
    }

    # Write records directly into persistent transactions ledger frame blocks
    with db.connection() as conn:
        conn.execute("""
            INSERT INTO transactions_ledger (
                transaction_id, card_id, device_id, merchant_id, timestamp,
                amount_paise, ensemble_risk_score, is_blocked,
                hydrated_metrics, shap_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            tx_id, card_id, device_id, merchant, timestamp_now_str,
            payload.amount_paise, ensemble_prob, 1 if is_blocked else 0,
            json.dumps(hydrated_metrics), json.dumps(shap_payload)
        ))
        
        if is_known_merchant == 0.0:
            conn.execute(
                "INSERT OR IGNORE INTO merchant_history (card_id, merchant_id) VALUES (?, ?);",
                (card_id, merchant)
            )

        if is_blocked:
            conn.execute(
                """
                INSERT INTO audit_jobs (
                    transaction_id,
                    status
                ) VALUES (?, 'PENDING');
                """,
                (tx_id,),
            )

            review_case_id = ensure_review_case_for_blocked_transaction(
                conn,
                transaction_id=tx_id,
                risk_score=ensemble_prob,
            )

    response_data = {
        "transaction_id": tx_id,
        "is_blocked": is_blocked,
        "ensemble_risk_score": round(ensemble_prob, 4),
        "hydrated_metrics": hydrated_metrics,
        "shap_payload": shap_payload,
        "status": "evaluated"
    }

    # BROADCAST SYSTEM TRANSACTION TICKER: Push updates down WebSocket channel instantaneously
    await ws_manager.broadcast_event({
        "type": "TRANSACTION_STREAM",
        "data": {
            "transaction_id": tx_id,
            "card_id": card_id, "device_id": device_id, "merchant_id": merchant,
            "timestamp": timestamp_now_str, "amount_paise": payload.amount_paise,
            "ensemble_risk_score": response_data["ensemble_risk_score"],
            "is_blocked": is_blocked, "hydrated_metrics": hydrated_metrics
        }
    })

    if is_blocked:
        background_tasks.add_task(
            process_agent_audit_worker,
            tx_id,
            compliance_agent,
            audit_service,
        )
        response_data["status"] = "Blocked (Audit Pending Background Compilation)"
        response_data["review_case_id"] = review_case_id
        
    return response_data

async def audit_job_dispatcher(
    compliance_agent,
    audit_service: AuditVaultService,
    poll_interval_seconds: float = 5.0,
) -> None:
    """Continuously process ready audit jobs and scheduled retries."""
    while True:
        try:
            transaction_ids = await asyncio.to_thread(
                audit_service.find_ready_jobs
            )

            if transaction_ids:
                await asyncio.gather(
                    *(
                        process_agent_audit_worker(
                            transaction_id,
                            compliance_agent,
                            audit_service,
                        )
                        for transaction_id in transaction_ids
                    )
                )

        except asyncio.CancelledError:
            raise
        except Exception as error:
            print(f"[Audit Dispatcher] Polling failed: {error}")

        await asyncio.sleep(poll_interval_seconds)
