import uvicorn
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import AliasChoices, BaseModel, Field
from core.ensemble import FinancialEnsembleGate
from core.explainer import TransactionExplainer
from core.agent import ComplianceAgent
from core.config import SystemRiskConfig
from core.database import SentinelDatabase


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LOG_FILE_PATH = DATA_DIR / "compliance_audit.log"

app = FastAPI(
    title="Sentinel Guard: Agentic FinTech Risk & Compliance Engine",
    version="1.0.0"
)

class TransactionPayload(BaseModel):
    amount_paise :int = Field(...,description="Transaction amount in local currency paise subunits")
    device_id: str = Field(..., description="Hardware identifier fingerprint token")
    card_id: str = Field(..., description="Unique token hash identifying the plastic card entity")
    merchant_id: str = Field(...,description="Merchant category for each transaction")

ensemble_gate = None
explainer_bridge = None
compliance_agent = None
db = None

#Start all the engines at the start of the server
@app.on_event("startup") 
def startup_event():
    global ensemble_gate, explainer_bridge, compliance_agent, db
    lgb_path = DATA_DIR / "lgb_compliance_gate.txt"
    xgb_path = DATA_DIR / "xgb_compliance_gate.json"

    ensemble_gate = FinancialEnsembleGate(xgb_path,lgb_path)
    explainer_bridge = TransactionExplainer(xgb_path,lgb_path)
    compliance_agent = ComplianceAgent()
    db = SentinelDatabase()
    db.initialize()
    print("System layers activated and database initialized.")


def process_agent_audit_worker(raw_data: dict, raw_features: list, hydrated_metrics : dict):
    """
    Runs entirely on a separate background thread pool.
    Computes SHAP explanations, runs local Llama 3 inference, and logs to disk.
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

        with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n{final_signed_memo}\n")
            
        print("[Background Thread] Cryptographically signed compliance logs successfully written to disk storage.")
    except Exception as err:
        print(f"[Background Thread Error] Task execution aborted: {str(err)}")

@app.post("/api/v1/evaluate")
async def evaluate_transaction(payload: TransactionPayload, background_tasks: BackgroundTasks):
    """
    Asynchronously intercept incoming transaction metrics, run ensemble evaluations,
    and trigger automated agentic audit generation if risk limits are crossed.
    """
    try:
        current_time = datetime.now()
        timestamp_now_str = current_time.isoformat()

        # 1. Bypass Pandas completely - extract fields explicitly into a clean sequence
        card_id = payload.card_id
        device_id = payload.device_id
        merchant = payload.merchant_id

        with db.connection() as conn:
            last_10m = (current_time - timedelta(minutes=10)).isoformat()
            last_30m = (current_time - timedelta(minutes=30)).isoformat()
            last_24h = (current_time - timedelta(hours=24)).isoformat()

            row_vel = conn.execute("""
                            SELECT COUNT(*) as cnt FROM transactions_ledger 
                            WHERE card_id= ? AND timestamp >= ?;
                            """,
                            (card_id, last_10m)).fetchone()
            card_vel_10m = row_vel["cnt"]

            row_ratio = conn.execute("""
                            SELECT COUNT(DISTINCT device_id) as dcnt,COUNT(card_id) as cnt
                            FROM transactions_ledger
                            WHERE card_id = ? AND timestamp >= ?;
                            """,
                            (card_id,last_30m)).fetchone()
            
            if row_ratio["cnt"] > 0:
                device_card_ratio_30m = float(row_ratio["dcnt"] / row_ratio["cnt"])
            else:
                device_card_ratio_30m = 1.0

            row_device =  conn.execute("""
                            SELECT COUNT(DISTINCT card_id) as cnt FROM transactions_ledger
                            WHERE device_id = ? AND timestamp >= ?;
                            """,
                            (device_id,last_24h)).fetchone()
            device_card = row_device["cnt"]
            device_card_limit = 1.0 if device_card > 3 else 0.0

            row_merchant = conn.execute("""
                            SELECT COUNT(*) as cnt FROM merchant_history
                            WHERE card_id = ? AND merchant_id = ?;
                            """,
                            (card_id,merchant)).fetchone()

            is_known_merchant = 1.0 if row_merchant["cnt"] >= 1 else 0.0

        raw_features = [
            float(payload.amount_paise),
            card_vel_10m,
            device_card_ratio_30m
        ]
        
        #Time of the swap risk
        current_hour = current_time.hour 
        is_off_hours_window = 1.0 if (1 <= current_hour <= 5) else 0.0
        
        input_matrix = [raw_features]
        
        p_xgb = float(ensemble_gate.xgb.predict_proba(input_matrix)[:, 1][0])
        
        p_lgb = float(ensemble_gate.lgb.predict(input_matrix)[0])
    
        ensemble_prob = (p_xgb + p_lgb) / 2

        is_blocked = ensemble_prob >= SystemRiskConfig.CALIBRATED_THRESHOLD
        
        hydrated_metrics = {
                "card_vel_10m": card_vel_10m,
                "device_card_ratio_30m": round(device_card_ratio_30m, 4),
                "device_card_limit_crossed":device_card_limit,
                "is_known_merchant":is_known_merchant,
                "is_off_hours_window":is_off_hours_window
        }

        # Calculate SHAP explainability values synchronously
        feature_order = ['amount_paise', 'card_vel_10m', 'device_card_ratio_30m']
        input_df = pd.DataFrame([raw_features], columns=feature_order)
        shap_json_str = explainer_bridge.generate_explanation(input_df)
        shap_payload = json.loads(shap_json_str)

        # Inserting the COMPLETE transaction evaluation into SQLite transactions_ledger
        with db.connection() as conn:
            conn.execute(
                """
                INSERT INTO transactions_ledger (
                    card_id, device_id, merchant_id, timestamp, 
                    amount_paise, ensemble_risk_score, is_blocked, 
                    hydrated_metrics, shap_payload
                ) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    card_id, device_id, merchant, timestamp_now_str,
                    payload.amount_paise, ensemble_prob, 1 if is_blocked else 0,
                    json.dumps(hydrated_metrics), json.dumps(shap_payload)
                )
            )
            
            if is_known_merchant == 0.0:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO merchant_history (card_id, merchant_id) 
                    VALUES (?, ?);
                    """,
                    (card_id, merchant)
                )

        response_data = {
            "is_blocked": is_blocked,
            "ensemble_risk_score": round(ensemble_prob, 4),
            "hydrated_metrics": hydrated_metrics,
            "shap_payload": shap_payload,
            "status": "evaluated"
        }

        if is_blocked:
            print("Alert! High risk found, Offloading audit task to background thread pool.")

            # Shunt task to worker pool instantly without waiting for completion
            background_tasks.add_task(
                process_agent_audit_worker, 
                payload.model_dump(), 
                raw_features,
                hydrated_metrics
            )
            response_data["status"] = "Blocked (Audit Pending Background Compilation)"
            
        return response_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Risk Core Exception: {str(e)}")


@app.get("/api/v1/transactions")
def get_transactions():
    """Retrieve full historical logs out of SQLite storage layer for UI component bootstrapping."""
    try:
        with db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions_ledger ORDER BY timestamp DESC LIMIT 200"
            ).fetchall()
            
            result = []
            for r in rows:
                try:
                    hydrated = json.loads(r["hydrated_metrics"]) if r["hydrated_metrics"] else {}
                except Exception:
                    hydrated = {}
                try:
                    shap = json.loads(r["shap_payload"]) if r["shap_payload"] else {}
                except Exception:
                    shap = {}
                
                result.append({
                    "card_id": r["card_id"],
                    "device_id": r["device_id"],
                    "merchant_id": r["merchant_id"],
                    "timestamp": r["timestamp"],
                    "amount_paise": r["amount_paise"] or 0,
                    "ensemble_risk_score": r["ensemble_risk_score"] or 0.0,
                    "is_blocked": bool(r["is_blocked"]),
                    "hydrated_metrics": hydrated,
                    "shap_payload": shap
                })
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve transactions: {str(e)}")


@app.get("/api/v1/merchants")
def get_merchants():
    """Expose the MCC codes registry dynamic dictionary."""
    try:
        from core.agent import kb_manager
        return kb_manager.mcc_registry
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch merchant registry: {str(e)}")


@app.get("/api/v1/audits")
def get_audits():
    """Read compliance_audit.log and split/parse it into separate entries for UI rendering."""
    try:
        if not LOG_FILE_PATH.exists():
            return []
        
        with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
            log_contents = f.read()

        # Split log file into individual entries
        raw_lines = log_contents.splitlines()
        entries = []
        current_entry = []

        for line in raw_lines:
            is_start = False
            if line.startswith("AUDIT ENTRY ["):
                is_start = True
            elif "NEXUS FINTECH COMPLIANCE INCIDENT REPORT" in line:
                is_start = True
            elif line.startswith("LLM Generation Connection Timeout Error:"):
                is_start = True

            if is_start and current_entry:
                entries.append("\n".join(current_entry).strip())
                current_entry = []

            current_entry.append(line)

        if current_entry:
            entries.append("\n".join(current_entry).strip())

        import re
        parsed_entries = []
        for i, entry_text in enumerate(entries):
            if not entry_text.strip():
                continue

            # Extract Card ID
            card_match = re.search(r"Card\s+ID\s*:\s*\*?\*?([a-zA-Z0-9_\-]+)", entry_text, re.IGNORECASE)
            card_id = card_match.group(1).strip() if card_match else "unknown"

            # Extract Timestamp
            time_match = re.search(r"AUDIT ENTRY\s*\[([^\]]+)\]", entry_text, re.IGNORECASE)
            timestamp = time_match.group(1).strip() if time_match else None
            
            # If timestamp is not in the header, look for other markers
            if not timestamp:
                dt_match = re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", entry_text)
                if dt_match:
                    timestamp = dt_match.group(0)[1:-1]
                else:
                    # Look for date/time patterns
                    dt_match2 = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", entry_text)
                    timestamp = dt_match2.group(0) if dt_match2 else "Historical Entry"

            # Extract Cryptographic hashes
            prev_hash_match = re.search(r"PREVIOUS_ENTRY_HASH\s*:\s*([a-fA-F0-9]+)", entry_text, re.IGNORECASE)
            curr_hash_match = re.search(r"CURRENT_RECORD_HASH\s*:\s*([a-fA-F0-9]+)", entry_text, re.IGNORECASE)

            prev_hash = prev_hash_match.group(1).strip() if prev_hash_match else None
            curr_hash = curr_hash_match.group(1).strip() if curr_hash_match else None

            is_error = "Connection Timeout Error" in entry_text or "Generation Failed" in entry_text

            parsed_entries.append({
                "id": i + 1,
                "card_id": card_id,
                "timestamp": timestamp,
                "previous_hash": prev_hash,
                "current_hash": curr_hash,
                "report_text": entry_text,
                "is_error": is_error
            })

        # Return newest first
        return parsed_entries[::-1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch audit logs: {str(e)}")


@app.get("/api/v1/debug-fraud-sample")
def get_fraud_sample():
    """Extracts a real out-of-sample fraud vector directly from our training partition."""
    from core.trainer import FraudModelTrainer
    trainer = FraudModelTrainer("data/transactions.csv")
    _ = trainer.prepare_datasets()
    
    # Isolate real anomalies
    fraud_rows = trainer.X_test[trainer.y_test == 1]
    if not fraud_rows.empty:
        sample = fraud_rows.head(1).to_dict(orient="records")[0]
        return {"msg": "Send this exact combination via curl to trigger your block", "payload": sample}
    return {"error": "No fraud samples located in split partition."}


if __name__ == "__main__":
    uvicorn.run("main:app",host="127.0.0.1", port=8000, reload=True)



    
