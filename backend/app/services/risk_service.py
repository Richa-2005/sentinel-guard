import asyncio
import json
import pandas as pd
from datetime import datetime, timedelta
from app.config import settings
from core.config import SystemRiskConfig
from core.database import SentinelDatabase
from app.services.engine_service import ml_executor, compute_ml_and_shap
from app.services.websocket_service import ws_manager

db = SentinelDatabase()

def process_agent_audit_worker(
        raw_data: dict, raw_features: list, 
        hydrated_metrics: dict, compliance_agent, 
        explainer_bridge
):
    
    """
    Runs entirely within the separate background tasks pool worker threads.
    Computes SHAP explainability matrices and runs local Llama inference.
    """
    try:
        feature_order = ['amount_paise', 'card_vel_10m', 'device_card_ratio_30m']
        input_df = pd.DataFrame([raw_features], columns=feature_order)
        
        shap_json_str = explainer_bridge.generate_explanation(input_df)
        shap_payload = json.loads(shap_json_str)
        
        print("[Background Thread] Initializing compliance graph audit state app...")
        final_signed_memo = compliance_agent.run_graph_audit(
            transaction_data=raw_data,
            hydrated_metrics=hydrated_metrics,
            shap_payload=shap_payload
        )

        with open(settings.LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n{final_signed_memo}\n")
            
        print("[Background Thread] Signed compliance log successfully written to disk storage.")
    except Exception as err:
        print(f"[Background Thread Error] Task execution aborted: {str(err)}")


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

    raw_features = [float(payload.amount_paise), card_vel_10m, device_card_ratio_30m]
    is_off_hours_window = 1.0 if (1 <= current_time.hour <= 5) else 0.0
    input_matrix = [raw_features]

    # Execute heavy math transformations inside non-blocking threads
    loop = asyncio.get_running_loop()
    ensemble_prob, shap_payload = await loop.run_in_executor(
        ml_executor, compute_ml_and_shap, raw_features, input_matrix, 
        ensemble_gate, explainer_bridge
    )

    is_blocked = ensemble_prob >= SystemRiskConfig.CALIBRATED_THRESHOLD
    
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
                card_id, device_id, merchant_id, timestamp, 
                amount_paise, ensemble_risk_score, is_blocked, 
                hydrated_metrics, shap_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            card_id, device_id, merchant, timestamp_now_str,
            payload.amount_paise, ensemble_prob, 1 if is_blocked else 0,
            json.dumps(hydrated_metrics), json.dumps(shap_payload)
        ))
        
        if is_known_merchant == 0.0:
            conn.execute(
                "INSERT OR IGNORE INTO merchant_history (card_id, merchant_id) VALUES (?, ?);",
                (card_id, merchant)
            )

    response_data = {
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
            "card_id": card_id, "device_id": device_id, "merchant_id": merchant,
            "timestamp": timestamp_now_str, "amount_paise": payload.amount_paise,
            "ensemble_risk_score": response_data["ensemble_risk_score"],
            "is_blocked": is_blocked, "hydrated_metrics": hydrated_metrics
        }
    })

    if is_blocked:
        background_tasks.add_task(
            process_agent_audit_worker, 
            payload.model_dump(), 
            raw_features, 
            hydrated_metrics,
            compliance_agent,
            explainer_bridge
        )
        response_data["status"] = "Blocked (Audit Pending Background Compilation)"
        
    return response_data
