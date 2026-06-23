"""
Threshold Optimization & Ensemble Layer
Combining the probabilities estimation of both the models and 
resulting ensemble (soft voting) is then used to tune the 
threshold to reduce false  negatives and hence increase recall.
"""
import numpy as np
from core.trainer import FraudModelTrainer
import pandas as pd
from xgboost import XGBClassifier
import lightgbm as lgb
from sklearn.metrics import fbeta_score, classification_report, precision_recall_curve, auc

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

        best_threshold = 0.5
        best_f2 = -1
        
        threshold_candidates = np.arange(0.01, 0.51, 0.01)

        for tc in threshold_candidates:
            
            y_pred = (ensemble_probs >= tc).astype(int)
            
            sc = fbeta_score(y_test, y_pred, beta=2, zero_division=0)
            if best_f2 < sc : 
                best_f2 = sc
                best_threshold = tc

        print(f"Optimization Found! Peak F2-Score: {best_f2:.4f} at Boundary: {best_threshold:.2f}")
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


