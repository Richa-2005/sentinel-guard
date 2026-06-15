"""
Generating / Synthesisng the artificial data to train the model on. 
The actual financial records , requests contain private keys and identification hence 
cannot be used to train. companines like Stripe, PayPal etc. also synthesise data
which replicates the real world data immensely. 
"""

import os
import uuid
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

class FinancialDataSynthesizer:
    def __init__(self, total_records: int = 50000, fraud_ratio: float = 0.002):
        '''
        Engineered framework to simulate a financial transaction database.
        
        Args:
            total_records: Base row ceiling for the synthetic ledger table
            fraud_ratio: Target configuration representing standard minority class imbalance
        '''
        self.total_records = total_records
        self.fraud_ratio = fraud_ratio
        np.random.seed(42) # Lock randomness for exact cross-machine reproducibility
    
    def generate_ledger(self) -> pd.DataFrame:
        """
        Synthesizes high-fidelity normal and fraudulent transactional records.
        Human data is really skewed since there are few high purchases like cars 
        While Otherwise purchases are small (coffee) or repeating like electricity bills. 
        """
        print(f"Building transaction matrices for {self.total_records} rows...")

        fraud_rows = int(self.total_records * self.fraud_ratio)
        normal_rows = self.total_records - fraud_rows

        #Synthesis of normal transactions 
        normal_data = {
            "transaction_id": [str(uuid.uuid4())[:18] for _ in range(normal_rows)],
            "card_token": [f"tok_{np.random.randint(100000, 999999)}" for _ in range(normal_rows)],
            "device_id": [f"dev_{np.random.randint(1111, 9999)}" for _ in range(normal_rows)],

            # Modeled via log-normal to simulate realistic retail pricing distributions
            "amount_rupees": (np.random.lognormal(mean=np.log(500), sigma=1.0, size=normal_rows)).round(2),
            "merchant_category": np.random.choice(["retail", "food", "entertainment", "utility"], size=normal_rows, p=[0.4, 0.3, 0.2, 0.1]),
            "is_fraud": np.zeros(normal_rows, dtype=int)
        }

        df_normal = pd.DataFrame(normal_data)

        # Generate linear chronological timestamps spanning the last 48 hours
        base_time = datetime.utcnow()
        df_normal["timestamp"] = [base_time - timedelta(seconds=int(x)) for x in np.random.uniform(0, 172800, size=normal_rows)]

        #Synthesis of fraud data (Card-Testing Botnets)
        fraud_cards = [f"tok_{np.random.randint(1111, 9999)}" for _ in range(max(1, fraud_rows // 5))]
        fraud_devices = [f"dev_{np.random.randint(1111, 9999)}" for _ in range(max(1, fraud_rows // 5))]

        fraud_data = {
            "transation_id" : [str(uuid.uuid4())[:18] for _ in range(fraud_rows)],
            "card_token" : np.random.choice(fraud_cards, size=fraud_rows),
            "device_id" : np.random.choice(fraud_devices, size=fraud_rows),

            # Botnets running card testing execute micro-charges to verify accounts
            "amounts_rupees" : np.random.randint(47, 478, size=fraud_rows),
            "merchant_category": np.random.choice(["retail", "utility"], size=fraud_rows, p=[0.7, 0.3]),
            "is_fraud": np.ones(fraud_rows, dtype=int)
        }

        df_fraud = pd.DataFrame(fraud_data)

        #The fraud transactions arrive in a very fast pace in a very short period of time
        fraud_timestamps = []
        for i in range(fraud_rows):
            cluster_offset = (i // 5) * 3600  # Stagger bot attacks across distinct hours
            burst_noise = np.random.randint(1, 4)  # Force execution within 1-3 seconds of each other
            fraud_timestamps.append(base_time - timedelta(seconds=cluster_offset + burst_noise))
        df_fraud["timestamp"] = fraud_timestamps

        # Concatenate and sort the unified dataframe to match real-time ledger arrival
        unified_ledger = pd.concat([df_normal, df_fraud], ignore_index=True)
        unified_ledger = unified_ledger.sort_values(by="timestamp").reset_index(drop=True)

        return unified_ledger
    
    def save_to_disk(self, df: pd.DataFrame, location : str = "data"):
        """Persists the processed dataframe to the untracked data layer safely."""
        os.makedirs(location, exist_ok=True)
        file_path = os.path.join(location, "transactions.csv")
        df.to_csv(file_path, index=False)
        print(f"Immutable transaction ledger written successfully to: {file_path}")
        print(f"Data Matrix Dimensions: {df.shape}")
    
if __name__ == "__main__":
    synthesizer = FinancialDataSynthesizer(total_records=50000, fraud_ratio=0.002)
    ledger_df = synthesizer.generate_ledger()
    synthesizer.save_to_disk(ledger_df)


