"""
Data Audit / Cost Sensitive Learning : class skewness , class weights for the models to know 
the amount of imbalance present to calculate the precision-recall 
trade off. To penalize a wrong fraud detection x times more.
"""
import pandas as pd
import numpy as np

try:
    from .pipeline import FinancialFeaturePipeline
except ImportError:
    from pipeline import FinancialFeaturePipeline

class DatasetProfiler:
    def __init__(self, path_data: str):
        self.path_data = path_data
        self.data = None
        self.pipeline = FinancialFeaturePipeline(path_data)
    
    def execute_audit(self):
        """Loads features and runs statistical calculations on target splits."""

        # 1. Load the sorted data via your pipeline
        self.pipeline.load_and_sort_ledger()
        # 2. Compute sliding behavioral attributes
        self.data = self.pipeline.compute_window_features()

        total_rows = len(self.data)
        norm_rows = len(self.data[self.data["is_fraud"]==0])
        fraud_rows = total_rows - norm_rows
        fraud_percentage = (fraud_rows / total_rows)*100
        scale_pos_weight = norm_rows / fraud_rows

        print("\n Sentinel Guard: Operational Ledger Audit ")
        print(f"Total Transactions Processed : {total_rows:,}")
        print(f"Normal Customer Operations   : {norm_rows:,}")
        print(f"Adversarial Interventions    : {fraud_rows:,}")
        print(f"Calculated Class Skewness    : {fraud_percentage:.4f}%")
        print(f"Programmatic scale_pos_weight: {scale_pos_weight:.4f}")


        return fraud_percentage, scale_pos_weight
        

if __name__ == "__main__":

    profiler = DatasetProfiler(path_data = 'data/transactions.csv')
    fraud_percentage, scale_pos_weight = profiler.execute_audit()
    

