"""
Training XGBoost Model
Splitting the data chornologically into train and test to avoid 
Data leakage
And using TimeSeriesSplit for hyperparameter tuning
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from profiler import DatasetProfiler
from sklearn.model_selection import TimeSeriesSplit

from sklearn.metrics import (classification_report, 
                             precision_recall_curve, 
                             auc, matthews_corrcoef, 
                             fbeta_score)

class FraudModelTrainer:
    def __init__(self,path_data:str):
        self.profiler  = DatasetProfiler(path_data)
        self.X_train, self.y_train = None, None
        self.X_test, self.y_test = None, None
        self.data = None
    
    def prepare_datasets(self):
        fraud_percentage, scale_pos_weight = self.profiler.execute_audit()
        features_data = self.profiler.data

        y = features_data["is_fraud"]
        X = features_data[['amount_paise', 'card_vel_10m', 'device_card_ratio_30m']]
        
        r = (int)(len(features_data) * 0.8)
        self.X_train = X[:r]
        self.X_test = X[r:]
        self.y_train = y[:r]
        self.y_test = y[r:]

        return scale_pos_weight
    
    def optimize_hyperparameters(self, scale_pos_weight):
        """Executes a chronological forward-chaining hyperparameter tuning grid."""
        
        print("\nInitiating Time-Series Forward-Chaining Parameter Scan...")

        #chronological rolling windows to prevent lookahead data leakage
        tscv = TimeSeriesSplit(n_splits=5)
        
       
        param_grid = {
            'max_depth': [3, 5],
            'learning_rate': [0.01, 0.1],
            'subsample': [0.8]
        }

        best_score = -1
        best_params = None

       
        for max_depth in param_grid['max_depth']:
            for lr in param_grid['learning_rate']:
                for subsample in param_grid['subsample']:
                    
                    cv_scores = []
                    
                    # Temporal split loop
                    for train_idx, val_idx in tscv.split(self.X_train):
                        X_tr, X_val = self.X_train.iloc[train_idx], self.X_train.iloc[val_idx]
                        y_tr, y_val = self.y_train.iloc[train_idx], self.y_train.iloc[val_idx]

                        clf = XGBClassifier(
                            max_depth=max_depth,
                            learning_rate=lr,
                            subsample=subsample,
                            scale_pos_weight=scale_pos_weight,
                            random_state=42,
                            eval_metric='logloss'
                        )
                        clf.fit(X_tr, y_tr, verbose=False)
                        
                        # We evaluate optimizations using PR-AUC since the target distribution is highly skewed
                        val_probs = clf.predict_proba(X_val)[:, 1]
                        prec, rec, _ = precision_recall_curve(y_val, val_probs)
                        cv_scores.append(auc(rec, prec))
                    
                    mean_score = np.mean(cv_scores)
                    print(f"Candidate Params -> max_depth: {max_depth}, lr: {lr} | Mean CV PR-AUC: {mean_score:.4f}")
                    
                    if mean_score > best_score:
                        best_score = mean_score
                        best_params = {
                            'max_depth': max_depth,
                            'learning_rate': lr,
                            'subsample': subsample
                        }
                        
        print(f"Optimization Found! Best Grid Choice Parameters: {best_params} (PR-AUC: {best_score:.4f})\n")
        return best_params

    def train_xgboost(self, scale_pos_weight,best_hyperparam):
        xgboost = XGBClassifier(
            max_depth=best_hyperparam['max_depth'],
            learning_rate=best_hyperparam['learning_rate'],
            subsample=best_hyperparam['subsample'],
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            eval_metric='logloss'
        )
        
        xgboost.fit(self.X_train,
                    self.y_train,
                    verbose=False)
        
        y_probs = xgboost.predict_proba(self.X_test)[:, 1]
        y_preds = xgboost.predict(self.X_test)
       
        precision, recall, _ = precision_recall_curve(self.y_test, y_probs)
        pr_auc = auc(recall, precision)
        mcc = matthews_corrcoef(self.y_test, y_preds)
        f2 = fbeta_score(self.y_test, y_preds, beta=2)

        print("\nOPTIMIZED MODEL OUT-OF-SAMPLE TEST PERFORMANCE")
        print(f"PR-AUC (Precision-Recall AUC): {pr_auc:.4f}")
        print(f"Matthews Correlation Coefficient (MCC): {mcc:.4f}")
        print(f"F2-Score (Focus on Recall): {f2:.4f}\n")
        print("Classification Report:")
        print(classification_report(self.y_test, y_preds, target_names=["Majority (0)", "Minority (1)"]))
                
if __name__ == "__main__":
    trainer = FraudModelTrainer(path_data='data/transactions.csv')
    scale_pos_weight = trainer.prepare_datasets()

    best_hyperparam = trainer.optimize_hyperparameters(scale_pos_weight)

    trainer.train_xgboost(scale_pos_weight,best_hyperparam)
    
    
    
    