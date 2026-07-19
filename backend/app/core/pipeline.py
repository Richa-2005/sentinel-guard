"""
Pipeline to find the features over a sliding window over a period 
of time. Two features : 
1. The number of times a particular card was used over last 10 
minutes to check if botnet fired many transactions at the same time

2. Map the device firing the transactions over last 30 minutes 
to check if same device is being used for many card transactions
 hence is possibly a hacker.
"""

import numpy as np
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
        
        #Is off hours column
        hours = self.data.index.hour

        self.data["is_off_hours_window"] = (
            (hours >= 1) & (hours <= 5)
        ).astype(float)

        # Card Use Velocity over last 10 min
        card_velocity = np.zeros(len(self.data), dtype=float)
        for positions in self.data.groupby("card_token", sort=False).indices.values():
            positions = np.asarray(positions)
            card_events = pd.Series(
                np.ones(len(positions), dtype=float),
                index=self.data.index.take(positions),
            )
            card_velocity[positions] = (
                card_events
                .rolling("10min", closed="left")
                .count()
                .fillna(0)
                .to_numpy()
            )

        self.data["card_vel_10m"] = card_velocity

        #Device-Card use over last 30 min
        temp_numeric_cards = self.data["card_token"].astype("category").cat.codes

        def compute_device_unique_cards(window: str) -> np.ndarray:
            """Count prior unique cards per device while preserving row alignment."""
            result = np.zeros(len(self.data), dtype=float)
            card_codes = temp_numeric_cards.to_numpy()

            for positions in self.data.groupby("device_id", sort=False).indices.values():
                positions = np.asarray(positions)
                device_cards = pd.Series(
                    card_codes[positions],
                    index=self.data.index.take(positions),
                )
                result[positions] = (
                    device_cards
                    .rolling(window, closed="left")
                    .apply(lambda values: len(set(values)), raw=True)
                    .fillna(0)
                    .to_numpy()
                )

            return result

        self.data["device_card_ratio_30m"] = compute_device_unique_cards("30min")

        # Device Card Limit Crossed

        device_card_24h_count = compute_device_unique_cards("24h")

        self.data["device_card_limit_crossed"] = (
            device_card_24h_count > 3
        ).astype(float)

        #known merchant
        merchant_history = {}
        known_merchant = []

        for row in self.data.itertuples():
            card = row.card_token
            merchant = row.merchant_category

            if card not in merchant_history:
                merchant_history[card] = set()

            if merchant in merchant_history[card]:
                known_merchant.append(1.0)
            else:
                known_merchant.append(0.0)
                merchant_history[card].add(merchant)

        self.data["is_known_merchant"] = known_merchant

        # Fill any lookback windows containing NaN with 0
        self.data = self.data.fillna(0)

        return self.data



if __name__ == "__main__" : 
    pipeline = FinancialFeaturePipeline(path_data = 'data/transactions.csv')
    
    sorted_data = pipeline.load_and_sort_ledger()
    processed_data = pipeline.compute_window_features()

    print("\n Feature Matrix Extraction Verification:")
    print(processed_data[['card_token', 'device_id', 'card_vel_10m', 'device_card_ratio_30m','is_off_hours_window','device_card_limit_crossed','is_known_merchant', 'is_fraud']].tail(15))


