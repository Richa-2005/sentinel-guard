"""
Training XGBoost Model
Splitting the data chornologically into train and test to avoid 
Data leakage
And using TimeSeriesSplit for hyperparameter tuning
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from app.core.profiler import DatasetProfiler
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
        X = features_data[[
            'amount_paise', 
            'card_vel_10m', 
            'device_card_ratio_30m', 
            'device_card_limit_crossed', 
            'is_known_merchant', 
            'is_off_hours_window'
        ]]
        
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
                        
                        # evaluate optimizations using PR-AUC since the target distribution is highly skewed
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

        print("\nXGBoost MODEL OUT-OF-SAMPLE TEST PERFORMANCE")
        print(f"PR-AUC (Precision-Recall AUC): {pr_auc:.4f}")
        print(f"Matthews Correlation Coefficient (MCC): {mcc:.4f}")
        print(f"F2-Score (Focus on Recall): {f2:.4f}\n")
        print("Classification Report:")
        print(classification_report(self.y_test, y_preds, target_names=["Majority (0)", "Minority (1)"]))
        
        model_save_path = "data/xgb_compliance_gate.json"
        xgboost.save_model(model_save_path)
        print(f"Frozen XGBoost tree model saved cleanly to: {model_save_path}")

    def optimize_lightgbm(self, scale_pos_weight):
        """Executes a chronological forward-chaining hyperparameter search for LightGBM."""
        print("\nInitiating LightGBM Time-Series Forward-Chaining Parameter Scan...")
        tscv = TimeSeriesSplit(n_splits=5)
        
        # Search space specifically tuned for Leaf-Wise structures
        param_grid = {
            'num_leaves': [31,63],
            'learning_rate': [0.05, 0.1,0.2],
            'min_child_samples': [5, 10]
        }

        best_score = -1
        best_params = None

        for num_leaves in param_grid['num_leaves']:
            for lr in param_grid['learning_rate']:
                for mcs in param_grid['min_child_samples']:
                    cv_scores = []
                    
                    for train_idx, val_idx in tscv.split(self.X_train):
                        X_tr, X_val = self.X_train.iloc[train_idx], self.X_train.iloc[val_idx]
                        y_tr, y_val = self.y_train.iloc[train_idx], self.y_train.iloc[val_idx]

                        clf = LGBMClassifier(
                            num_leaves=num_leaves,
                            learning_rate=lr,
                            min_child_samples=mcs,
                            scale_pos_weight=scale_pos_weight,
                            random_state=42,
                            n_estimators=100,
                            verbose=-1
                        )
                        clf.fit(X_tr, y_tr)
                        
                        val_probs = clf.predict_proba(X_val)[:, 1]
                        prec, rec, _ = precision_recall_curve(y_val, val_probs)
                        cv_scores.append(auc(rec, prec))
                    
                    mean_score = np.mean(cv_scores)
                    print(f"LGBM Candidate -> num_leaves: {num_leaves}, lr: {lr} , min_child: {mcs} | Mean CV PR-AUC: {mean_score:.4f}")
                    
                    if mean_score > best_score:
                        best_score = mean_score
                        best_params = {'num_leaves': num_leaves, 'learning_rate': lr, 'min_child_samples': mcs }
                        
        print(f"LightGBM Optimization Found! Parameters: {best_params}\n")
        return best_params

    def train_lightgbm(self, scale_pos_weight,best_hyperparam):
        """Trains an optimized LightGBM classifier"""

        lgb = LGBMClassifier(
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            n_estimators=100,
            num_leaves=best_hyperparam['num_leaves'],
            learning_rate=best_hyperparam['learning_rate'],
            min_child_samples=best_hyperparam['min_child_samples'],
            verbose=-1 
        )

        lgb.fit(self.X_train, self.y_train)

        y_probs = lgb.predict_proba(self.X_test)[:, 1]
        y_preds = lgb.predict(self.X_test)

        precision, recall, _ = precision_recall_curve(self.y_test, y_probs)
        pr_auc = auc(recall, precision)
        mcc = matthews_corrcoef(self.y_test, y_preds)
        f2 = fbeta_score(self.y_test, y_preds, beta=2)

        print("\n LIGHTGBM MODEL OUT-OF-SAMPLE TEST PERFORMANCE")
        print(f"PR-AUC (Precision-Recall AUC): {pr_auc:.4f}")
        print(f"Matthews Correlation Coefficient (MCC): {mcc:.4f}")
        print(f"F2-Score (Focus on Recall): {f2:.4f}\n")
        print("Classification Report:")
        print(classification_report(self.y_test, y_preds, target_names=["Majority (0)", "Minority (1)"]))

        lgb_save_path = "data/lgb_compliance_gate.txt"
        lgb.booster_.save_model(lgb_save_path)
        print(f"Frozen LightGBM tree model saved cleanly to: {lgb_save_path}")

                
if __name__ == "__main__":
    trainer = FraudModelTrainer(path_data='data/transactions.csv')
    scale_pos_weight = trainer.prepare_datasets()

    best_hyperparam = trainer.optimize_hyperparameters(scale_pos_weight)

    trainer.train_xgboost(scale_pos_weight,best_hyperparam)

    lightbgm_param = trainer.optimize_lightgbm(scale_pos_weight)

    trainer.train_lightgbm(scale_pos_weight,lightbgm_param)


