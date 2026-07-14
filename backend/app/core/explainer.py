"""
SHAP (SHapely Additive exPlanations) Explainer layer gives the 
exact metrics the models used to give a particular score for 
a transaction. 
"""

import json
import shap
import pandas as pd
from xgboost import XGBClassifier
import lightgbm as lgb
from app.core.trainer import FraudModelTrainer

class TransactionExplainer:
    def __init__(self, xgb_path, lgb_path):
        """
        Initializes the explainer layer by deserializing 
        a pre-trained model.
        """

        self.xgb = XGBClassifier()
        self.xgb.load_model(xgb_path)
        self.xgb_explainer = shap.TreeExplainer(self.xgb)

        self.lgb = lgb.Booster(model_file=lgb_path)
        self.lgb_explainer = shap.TreeExplainer(self.lgb)

        self.explainer = shap.TreeExplainer(self.xgb)
        print("SHAP Explainability Engine successfully mapped to both model weights.")

    
    def generate_explanation(self, transaction_row: pd.DataFrame) -> str:
        """Extracts Shapley values for both models and formats them into a unified audit trail."""
      
        xgb_shap = self.xgb_explainer(transaction_row)
        xgb_contributions = xgb_shap.values[0]

        lgb_shap = self.lgb_explainer(transaction_row)
        lgb_contributions = lgb_shap.values[0]

        feature_names = transaction_row.columns.tolist()

        ens_contributions = (xgb_contributions + lgb_contributions) / 2
        
        unified_payload = {
            "xgb_feature_impacts": dict(zip(feature_names, [round(float(x), 4) for x in xgb_contributions])),
            "lgb_feature_impacts": dict(zip(feature_names, [round(float(x), 4) for x in lgb_contributions])),
            "ensemble_feature_impacts": dict(zip(feature_names, [round(float(x), 4) for x in ens_contributions]))
        }

        return json.dumps(unified_payload, indent=4)

if __name__ == "__main__":
    xgb_path =  "data/xgb_compliance_gate.json" 
    lgb_path = "data/lgb_compliance_gate.txt"
    
    tExp = TransactionExplainer(xgb_path, lgb_path)

    trainer = FraudModelTrainer(path_data='data/transactions.csv')
    scale_pos_weight = trainer.prepare_datasets()

    sample = trainer.X_test[trainer.y_test == 1].head(1)

    if not sample.empty:
        json_output = tExp.generate_explanation(sample)
        print("\nSentinel Guard: Explainability Bridge Vector Locked ---")
        print(json_output)

    else:
        print("No fraud flags found in test slice validation checks.")
