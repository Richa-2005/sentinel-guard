import uvicorn
import json
from app.config import settings
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect, HTTPException
from app.models.model import TransactionPayload

# Core Systems Infrastructure
from app.core.ensemble import FinancialEnsembleGate
from app.core.explainer import TransactionExplainer
from app.core.agent import ComplianceAgent

# Modular Custom Business Logic Services
from app.services.websocket_service import ws_manager
from app.services.risk_service import (
    audit_job_dispatcher,
    audit_service,
    db,
    evaluate_and_persist_transaction,
)

from app.services.log_service import fetch_audit_jobs, fetch_compliance_audits

import asyncio
from contextlib import suppress

app = FastAPI(
    title="Sentinel Guard: Agentic FinTech Risk & Compliance Engine",
    version="1.0.0"
)

# Global Framework State Anchors
ensemble_gate = None
explainer_bridge = None
compliance_agent = None
audit_dispatcher_task = None


@app.on_event("startup")
async def startup_event():
    global ensemble_gate
    global explainer_bridge
    global compliance_agent
    global audit_dispatcher_task

    xgb_path = settings.DATA_DIR / "xgb_compliance_gate.json"
    lgb_path = settings.DATA_DIR / "lgb_compliance_gate.txt"

    ensemble_gate = FinancialEnsembleGate(xgb_path, lgb_path)
    explainer_bridge = TransactionExplainer(xgb_path, lgb_path)
    compliance_agent = ComplianceAgent()

    db.initialize()

    recovered_jobs = await asyncio.to_thread(
        audit_service.recover_interrupted_jobs
    )

    if recovered_jobs:
        print(
            f"[Audit Recovery] Requeued {recovered_jobs} "
            "interrupted audit jobs."
        )

    audit_dispatcher_task = asyncio.create_task(
        audit_job_dispatcher(
            compliance_agent,
            audit_service,
        )
    )

    print("Clean Gateway Architecture activated successfully.")


@app.on_event("shutdown")
async def shutdown_event():
    global audit_dispatcher_task

    if audit_dispatcher_task is None:
        return

    audit_dispatcher_task.cancel()

    with suppress(asyncio.CancelledError):
        await audit_dispatcher_task

    audit_dispatcher_task = None

@app.websocket("/ws/live-feed")
async def websocket_endpoint(websocket: WebSocket):
    """Persistent bidirectional channel broadcasting data tickers directly to React components."""
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.post("/api/v1/evaluate")
async def evaluate_transaction(payload: TransactionPayload, background_tasks: BackgroundTasks):
    """Intercept inbound transactions and map tasks through isolated compute pools."""
    return await evaluate_and_persist_transaction(
        payload, background_tasks, ensemble_gate, explainer_bridge, compliance_agent
    )


@app.get("/api/v1/transactions")
def get_transactions():
    """Historical transaction ledger bootstrapping hook."""
    try:
        with db.connection() as conn:
            rows = conn.execute("SELECT * FROM transactions_ledger ORDER BY timestamp DESC LIMIT 200").fetchall()
            result = []
            for r in rows:
                result.append({
                    "transaction_id": r["transaction_id"],
                    "card_id": r["card_id"], "device_id": r["device_id"], "merchant_id": r["merchant_id"],
                    "timestamp": r["timestamp"], "amount_paise": r["amount_paise"] or 0,
                    "ensemble_risk_score": r["ensemble_risk_score"] or 0.0, "is_blocked": bool(r["is_blocked"]),
                    "hydrated_metrics": json.loads(r["hydrated_metrics"]) if r["hydrated_metrics"] else {},
                    "shap_payload": json.loads(r["shap_payload"]) if r["shap_payload"] else {}
                })
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/merchants")
def get_merchants():
    """Exposes the MCC dynamically fetched dynamic mapping indices."""
    try:
        from app.core.agent import kb_manager
        return kb_manager.mcc_registry
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/audits")
def get_audits():
    """Return persisted compliance audits."""
    return fetch_compliance_audits(db)


@app.get("/api/v1/audit-jobs")
def get_audit_jobs():
    """Return durable audit generation and retry statuses."""
    return fetch_audit_jobs(db)


@app.get("/api/v1/debug-fraud-sample")
def get_fraud_sample():
    try:
        from app.core.trainer import FraudModelTrainer
        trainer = FraudModelTrainer("data/transactions.csv")
        _ = trainer.prepare_datasets()
        fraud_rows = trainer.X_test[trainer.y_test == 1]
        if not fraud_rows.empty:
            return {"msg": "Send matrix sample payload via curl", "payload": fraud_rows.head(1).to_dict(orient="records")[0]}
        return {"error": "No partition vectors found."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
