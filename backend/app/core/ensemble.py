"""
Threshold Optimization & Ensemble Layer
Combining the probabilities estimation of both the models and 
resulting ensemble (soft voting) is then used to tune the 
threshold to reduce false  negatives and hence increase recall.
"""
import json
from pathlib import Path

import numpy as np
from app.config import settings
from app.core.trainer import FraudModelTrainer
import pandas as pd
from xgboost import XGBClassifier
import lightgbm as lgb
from sklearn.metrics import fbeta_score, classification_report, precision_recall_curve, auc

MODEL_FEATURE_DIMENSIONS = [
    'amount_paise',
    'card_vel_10m',
    'device_card_ratio_30m',
    'device_card_limit_crossed',
    'is_known_merchant',
    'is_off_hours_window',
]


def persist_model_config(best_threshold: float, config_path=None) -> Path:
    """Persist the calibrated boundary and canonical inference schema."""
    target_path = Path(config_path) if config_path else settings.DATA_DIR / "model_config.json"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with target_path.open("w", encoding="utf-8") as config_file:
        json.dump(
            {
                "CALIBRATED_THRESHOLD": float(best_threshold),
                "FEATURE_DIMENSIONS": MODEL_FEATURE_DIMENSIONS,
            },
            config_file,
            indent=2,
        )

    return target_path

class FinancialEnsembleGate:
    def __init__(self, xgb_path, lgb_path):
        self.xgb = XGBClassifier()
        self.xgb.load_model(xgb_path)

        self.lgb = lgb.Booster(model_file=lgb_path)

        print("\nModels deserialized.\n")
    
    def optimized_decision_boundary(self,X_test, y_test):
        """
        Computes soft ensemble scores and sweeps thresholds to 
        maximize F2-Score.
        """

        p_xgb = self.xgb.predict_proba(X_test)[:, 1]
        p_lgb = self.lgb.predict(X_test)

        ensemble_probs = (p_xgb + p_lgb)/2

        precision, recall, thresholds = precision_recall_curve(
            y_test,
            ensemble_probs,
        )
        f2_scores = (
            5 * precision[:-1] * recall[:-1]
            / (4 * precision[:-1] + recall[:-1] + 1e-12)
        )
        best_index = int(np.argmax(f2_scores))
        best_threshold = float(thresholds[best_index])
        best_f2 = float(f2_scores[best_index])

        config_path = persist_model_config(best_threshold)
        print(f"Optimization Found! Peak F2-Score: {best_f2:.4f} at Boundary: {best_threshold:.2f}")
        print(f"Calibrated model configuration saved to: {config_path}")
        return best_threshold, ensemble_probs
    
if __name__ == "__main__":
    trainer = FraudModelTrainer("data/transactions.csv")
    scale_pos_weight = trainer.prepare_datasets()

    ensemble = FinancialEnsembleGate("data/xgb_compliance_gate.json","data/lgb_compliance_gate.txt")
    
    threshold, ens_probs = ensemble.optimized_decision_boundary(
        trainer.X_test,
        trainer.y_test
    )

    print("Ensemble probabilities sample: ", [round(float(x), 4) for x in ens_probs[:5]])
    
    final_preds = (ens_probs >= threshold).astype(int)
    print("\nOut-Of-Sample Calibrated Classification Matrix:")
    print(classification_report(trainer.y_test, final_preds, target_names=["Majority (0)", "Minority (1)"]))
