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

#mapping of cards to the list of timepstamps of their swiping
card_history = {} 

#linking card to device
device_history = {}

ensemble_gate = None
explainer_bridge = None
compliance_agent = None

#Start all the engines at the start of the server
@app.on_event("startup") 
def startup_event():
    global ensemble_gate, explainer_bridge, compliance_agent
    lgb_path = DATA_DIR / "lgb_compliance_gate.txt"
    xgb_path = DATA_DIR / "xgb_compliance_gate.json"

    ensemble_gate = FinancialEnsembleGate(xgb_path,lgb_path)
    explainer_bridge = TransactionExplainer(xgb_path,lgb_path)
    compliance_agent = ComplianceAgent()
    print("System layers activated.")


def process_agent_audit_worker(raw_data: dict, raw_features: list):
    """
    Runs entirely on a separate background thread pool.
    Computes SHAP explanations, runs local Llama 3 inference, and logs to disk.
    """
    try:
        feature_order = ['amount_paise', 'card_vel_10m', 'device_card_ratio_30m']
        input_df = pd.DataFrame([raw_features], columns=feature_order)
        
        shap_json_str = explainer_bridge.generate_explanation(input_df)
        shap_payload = json.loads(shap_json_str)
        
        prompt = compliance_agent.compile_audit_prompt(raw_data, shap_payload)
        audit_report = compliance_agent.generate_audit_trail(prompt)

        # 4. Persistence Phase: Write the audit log entry directly to disk
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"AUDIT ENTRY [{timestamp_str}] \nCard ID: {raw_data.get('card_id')}\n{audit_report}\n\n"
        
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(log_entry)
            
        print("[Background Thread] Compliance logs persisted to storage asset.")
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
        # 1. Bypass Pandas completely - extract fields explicitly into a clean sequence
        card_id = payload.card_id
        device_id = payload.device_id
        
        if card_id not in card_history:
            card_history[card_id] = []
        if card_id not in device_history:
            device_history[card_id] = set()
            
        # Append the current transaction attempt to historical memory
        card_history[card_id].append(current_time)
        device_history[card_id].add(device_id)

        last_10m = current_time - timedelta(minutes=10)
        
        active_cards_time = [t for t in card_history[card_id] if t >= last_10m]
        card_history[card_id] = active_cards_time #saves memory 

        card_vel_10m = len(active_cards_time)

        unique_devices_used = len(device_history[card_id])
        device_card_ratio_30m = float(unique_devices_used / card_vel_10m)

        raw_features = [
            float(payload.amount_paise),
            card_vel_10m,
            device_card_ratio_30m
        ]
        
        input_matrix = [raw_features]
        
        p_xgb = float(ensemble_gate.xgb.predict_proba(input_matrix)[:, 1][0])
        
        p_lgb = float(ensemble_gate.lgb.predict(input_matrix)[0])
    
        ensemble_prob = (p_xgb + p_lgb) / 2

        CALIBRATED_THRESHOLD = 0.01
        is_blocked = ensemble_prob >= CALIBRATED_THRESHOLD
        
        response_data = {
           "is_blocked": is_blocked,
            "ensemble_risk_score": round(ensemble_prob, 4),
            "hydrated_metrics": {
                "card_vel_10m": card_vel_10m,
                "device_card_ratio_30m": round(device_card_ratio_30m, 4)
            },
            "status" : "evaluated"
        }

        if is_blocked:
            print("Alert! High risk found, Offloading audit task to background thread pool.")

            # Shunt task to worker pool instantly without waiting for completion
            background_tasks.add_task(
                process_agent_audit_worker, 
                payload.model_dump(), 
                raw_features
            )
            response_data["status"] = "Blocked (Audit Pending Background Compilation)"
            
        return response_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Risk Core Exception: {str(e)}")


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



    
