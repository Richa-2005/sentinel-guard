import uvicorn
import pandas as pd
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import AliasChoices, BaseModel, Field
from core.ensemble import FinancialEnsembleGate
from core.explainer import TransactionExplainer
from core.agent import ComplianceAgent

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

app = FastAPI(
    title="Sentinel Guard: Agentic FinTech Risk & Compliance Engine",
    version="1.0.0"
)

class TransactionPayload(BaseModel):
    amount_paise :int = Field(...,description="Transaction amount in local currency paise subunits")
    card_vel_10m : float = Field(..., description="Rolling count of card uses over past 10 minutes")
    device_card_ratio_30m: float = Field(
        ...,
        validation_alias=AliasChoices("device_card_ratio_30m", "device_ard_ratio_30m"),
        description="Device-card switching profile density ratio",
    )

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


@app.post("/api/v1/evaluate")
async def evaluate_transaction(payload: TransactionPayload):
    """
    Asynchronously intercept incoming transaction metrics, run ensemble evaluations,
    and trigger automated agentic audit generation if risk limits are crossed.
    """
    try:
        # 1. Bypass Pandas completely - extract fields explicitly into a clean sequence
        raw_features = [
            float(payload.amount_paise),
            float(payload.card_vel_10m),
            float(payload.device_card_ratio_30m)
        ]
        
        # Wrap into a raw 2D array format matrix layout required by C-engines [[val1, val2, val3]]
        input_matrix = [raw_features]
        
        # 2. Extract XGBoost standard probability natively
        p_xgb = float(ensemble_gate.xgb.predict_proba(input_matrix)[:, 1][0])
        
        # 3. Extract LightGBM native prediction from the identical layout
        p_lgb = float(ensemble_gate.lgb.predict(input_matrix)[0])
        
        # Active debugging trace log
        print(f"📡 GATEWAY TRACE -> Features Sent: {raw_features} | XGB: {p_xgb:.4f} | LGB: {p_lgb:.4f}")

        # Compute combined ensemble score
        ensemble_prob = (p_xgb + p_lgb) / 2

        CALIBRATED_THRESHOLD = 0.01
        is_blocked = ensemble_prob >= CALIBRATED_THRESHOLD
        
        response_data = {
            "is_blocked": is_blocked,
            "ensemble_risk_score": round(ensemble_prob, 4),
            "audit_trail": None
        }

        if is_blocked:
            print("🚨 High Risk Anomaly Detected! Launching Automated Agentic Audit Trail...")
            
            # FIXED: Reconstruct the exact DataFrame format that the SHAP explainer needs
            feature_order = ['amount_paise', 'card_vel_10m', 'device_card_ratio_30m']
            input_df = pd.DataFrame([raw_features], columns=feature_order)
            
            # Pass it safely to the SHAP engine
            shap_json_str = explainer_bridge.generate_explanation(input_df)
            shap_payload = json.loads(shap_json_str)
            
            prompt = compliance_agent.compile_audit_prompt(raw_features, shap_payload)
            audit_report = compliance_agent.generate_audit_trail(prompt)
            response_data["audit_trail"] = audit_report
            
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



    
