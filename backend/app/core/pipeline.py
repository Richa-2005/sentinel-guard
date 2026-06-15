"""
Pipeline to find the features over a sliding window over a period 
of time. Two features : 
1. The number of times a particular card was used over last 10 
minutes to check if botnet fired many transactions at the same time

2. Map the device firing the transactions over last 30 minutes 
to check if same device is being used for many card transactions
 hence is possibly a hacker.
"""

import pandas as pd

class FinancialFeaturePipeline:
    def __init__(self,path_data : str):
        self.path_data = path_data
        self.data = None
    
    def load_and_sort_ledger(self):
        """Loads transaction history and sets up a clean datetime tracking index."""
        
        self.data = pd.read_csv(self.path_data)
        self.data["timestamp"] = pd.to_datetime(self.data["timestamp"])

        self.data = self.data.sort_values(by='timestamp')
        #Making timestamp as index
        self.data = self.data.set_index("timestamp")
        print("Sorted the ledger and made timestamp as the index")
        return self.data
    
    def compute_window_features(self):
        """Computes rolling contextual attributes handling historical time states."""
        if self.data is None:
            raise ValueError("Data pipeline frame has not been initialized.")
        
        print("Computing behavioral velocity features...")

        # Ensure index sorting for positional alignment
        self.data = self.data.sort_index()

        # Feature 1 : Card Use Velocity over last 10 min
        self.data["card_vel_10m"] = (
            self.data.groupby("card_token")
            .rolling('10min', closed="left")['transaction_id']
            .count()
            .reset_index(level=0, drop=True)
            .sort_index()
            .values
        )

        # Feature 2: Device-Card use over last 30 min
        
        temp_numeric_cards = self.data["card_token"].astype("category").cat.codes

        self.data["device_card_ratio_30m"] = (
            self.data.assign(card_code=temp_numeric_cards)
            .groupby("device_id")
            .rolling("30min", closed="left")["card_code"]
            .apply(lambda x: len(set(x)), raw=True)  
            .reset_index(level=0, drop=True)
            .sort_index()
            .values
        )

        # Fill any lookback windows containing NaN with 0
        self.data = self.data.fillna(0)

        return self.data



if __name__ == "__main__" : 
    pipeline = FinancialFeaturePipeline(path_data = 'data/transactions.csv')
    
    sorted_data = pipeline.load_and_sort_ledger()
    processed_data = pipeline.compute_window_features()

    print("\n Feature Matrix Extraction Verification:")
    print(processed_data[['card_token', 'device_id', 'card_vel_10m', 'device_card_ratio_30m', 'is_fraud']].tail(15))




