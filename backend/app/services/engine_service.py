import asyncio
import pandas as pd
import json
from concurrent.futures import ThreadPoolExecutor

# Instantiate a dedicated core thread pool for compute-heavy ML matrices
ml_executor = ThreadPoolExecutor(max_workers=4)

def compute_ml_and_shap(raw_features, input_matrix, ensemble_gate, explainer_bridge):
    """
    Synchronous compute block wrapping tree evaluations and mathematical SHAP weights.
    Runs completely outside the main FastAPI event loop thread.
    """
    # 1. Execute dual tree scoring branch predictions
    p_xgb = float(ensemble_gate.xgb.predict_proba(input_matrix)[:, 1][0])
    p_lgb = float(ensemble_gate.lgb.predict(input_matrix)[0])
    ensemble_prob = (p_xgb + p_lgb) / 2
    
    # 2. Execute intense mathematical SHAP vectors
    feature_order = ['amount_paise', 'card_vel_10m', 'device_card_ratio_30m']
    input_df = pd.DataFrame([raw_features], columns=feature_order)
    shap_json_str = explainer_bridge.generate_explanation(input_df)
    shap_payload = json.loads(shap_json_str)
    
    return ensemble_prob, shap_payload