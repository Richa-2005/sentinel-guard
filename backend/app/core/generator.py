"""
Generating / Synthesising the artificial data to train the model on. 
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
        
        #merchant_category generation 
        merchants = []
        for i in range(1,501):
            merch = "merch_"
            if i <10 : 
                merch += f"00{i}"
            elif i<100 :
                merch += f"0{i}"
            else:
                merch += f"{i}"
            merchants.append(merch)
        
        # Reuse a stable pool of normal cards so each card builds meaningful
        # transaction and merchant history across the generated ledger.
        normal_cards = [f"tok_{card_number:06d}" for card_number in range(1, 3001)]
        card_tokens = np.random.choice(
            normal_cards,
            size=normal_rows,
            replace=True,
        ).tolist()

        normal_device_numbers = np.random.choice(
            np.arange(1111, 10000),
            size=len(normal_cards),
            replace=False,
        )
        normal_hardware_map = {
            card: f"dev_{device_number}"
            for card, device_number in zip(normal_cards, normal_device_numbers)
        }
        device_ids_normal = [normal_hardware_map[card] for card in card_tokens]
        
        card_profiles = {}

        merchant_id_normal = []
        for card in card_tokens:
            if card not in card_profiles:
                favorite_merchants = np.random.choice(
                    merchants,
                    size=3,
                    replace=False,
                ).tolist()
                card_profiles[card] = favorite_merchants

            if np.random.random() < 0.05:
                spontaneous_merchant = np.random.choice(merchants)
                while spontaneous_merchant in card_profiles[card]:
                    spontaneous_merchant = np.random.choice(merchants)
                merchant_id_normal.append(spontaneous_merchant)
            else:
                merchant_id_normal.append(np.random.choice(card_profiles[card]))

        #Synthesis of normal transactions 
        normal_data = {
            "transaction_id": [str(uuid.uuid4())[:18] for _ in range(normal_rows)],
            "card_token": card_tokens,
            "device_id": device_ids_normal,

            # Modeled via log-normal to simulate realistic retail pricing distributions
            "amount_paise": (np.random.lognormal(mean=np.log(50000), sigma=1.0, size=normal_rows)).astype(int),
            "merchant_category": merchant_id_normal,
            "is_fraud": np.zeros(normal_rows, dtype=int)
        }

        df_normal = pd.DataFrame(normal_data)

        base_time = datetime.now().replace(microsecond=0)
        normal_hour_weights = np.ones(24, dtype=float)
        normal_hour_weights[8:23] = 8.0
        normal_hour_weights /= normal_hour_weights.sum()

        normal_hours = np.random.choice(
            np.arange(24),
            size=normal_rows,
            p=normal_hour_weights,
        )
        normal_minutes = np.random.randint(0, 60, size=normal_rows)
        normal_seconds = np.random.randint(0, 60, size=normal_rows)
        normal_days_ago = np.random.randint(0, 7, size=normal_rows)

        normal_timestamps = []
        for hour, minute, second, days_ago in zip(
            normal_hours,
            normal_minutes,
            normal_seconds,
            normal_days_ago,
        ):
            timestamp = base_time.replace(
                hour=int(hour),
                minute=int(minute),
                second=int(second),
                microsecond=0,
            ) - timedelta(days=int(days_ago))

            if timestamp > base_time:
                timestamp -= timedelta(days=1)

            normal_timestamps.append(timestamp)

        df_normal["timestamp"] = normal_timestamps

        # Roughly 2% of normal rows belong to legitimate shopping sprees:
        # five rapid purchases on one card at one trusted merchant.
        spree_group_size = 5
        spree_group_count = int(normal_rows * 0.02) // spree_group_size
        normal_card_row_indices = df_normal.groupby("card_token").indices
        spree_eligible_cards = [
            card
            for card, positions in normal_card_row_indices.items()
            if len(positions) >= spree_group_size
        ]
        spree_cards = np.random.choice(
            spree_eligible_cards,
            size=min(spree_group_count, len(spree_eligible_cards)),
            replace=False,
        )

        for card in spree_cards:
            spree_indices = np.random.choice(
                normal_card_row_indices[card],
                size=spree_group_size,
                replace=False,
            )
            trusted_merchant = np.random.choice(card_profiles[card])
            daytime_indices = [
                index
                for index in normal_card_row_indices[card]
                if 8 <= df_normal.at[index, "timestamp"].hour <= 22
            ]
            anchor_index = np.random.choice(daytime_indices or spree_indices.tolist())
            spree_start = df_normal.at[anchor_index, "timestamp"].replace(
                minute=min(df_normal.at[anchor_index, "timestamp"].minute, 55),
                second=np.random.randint(0, 60),
            )

            for offset, row_index in enumerate(spree_indices):
                df_normal.at[row_index, "timestamp"] = spree_start + timedelta(minutes=offset)
                df_normal.at[row_index, "merchant_category"] = trusted_merchant

        #Synthesis of fraud data (Card-Testing Botnets)
        fraud_devices = [
            f"dev_fraud_{device_number:04d}"
            for device_number in range(1, max(1, fraud_rows // 5) + 1)
        ]

        # Build fraud in bursts across off-hours and daylight. Bursts alternate
        # between one-device/many-card rings and one-card/many-merchant tests.
        # Cycling bursts across seven days distributes fraud chronologically.
        card_tokens_fraud = []
        device_id_fraud = []
        merchant_id_fraud = []
        fraud_timestamps = []
        unique_card_tokens = np.unique(card_tokens)
        ind = 0
        burst_number = 0

        while ind < fraud_rows:
            remaining_rows = fraud_rows - ind

            if remaining_rows <= 10:
                group_rows = remaining_rows
            else:
                group_rows = np.random.randint(5, 11)
                if 0 < remaining_rows - group_rows < 5:
                    group_rows = remaining_rows - 5

            if len(unique_card_tokens) < group_rows:
                raise ValueError(
                    "Not enough unique normal card tokens to create a fraud burst."
                )

            compromised_device = np.random.choice(fraud_devices)
            is_velocity_attack = burst_number % 2 == 1

            if is_velocity_attack:
                stolen_card = np.random.choice(unique_card_tokens)
                burst_cards = np.repeat(stolen_card, group_rows)
                valid_merchants = [
                    merchant
                    for merchant in merchants
                    if merchant not in card_profiles[stolen_card]
                ]
                burst_merchants = np.random.choice(
                    valid_merchants,
                    size=group_rows,
                    replace=False,
                )
            else:
                burst_cards = np.random.choice(
                    unique_card_tokens,
                    size=group_rows,
                    replace=False,
                )
                burst_merchants = [
                    np.random.choice([
                        merchant
                        for merchant in merchants
                        if merchant not in card_profiles[card]
                    ])
                    for card in burst_cards
                ]

            fraud_hour = np.random.choice([1, 2, 3, 4, 14, 15, 16])
            fraud_minute = np.random.randint(0, 60)
            fraud_second = np.random.randint(0, 60)
            days_ago = burst_number % 7

            burst_start = base_time.replace(
                hour=int(fraud_hour),
                minute=int(fraud_minute),
                second=int(fraud_second),
                microsecond=0,
            ) - timedelta(days=days_ago, seconds=group_rows)

            if burst_start > base_time:
                burst_start -= timedelta(days=1)

            card_tokens_fraud.extend(burst_cards.tolist())
            device_id_fraud.extend([compromised_device] * group_rows)
            merchant_id_fraud.extend(list(burst_merchants))
            fraud_timestamps.extend(
                burst_start + timedelta(seconds=offset)
                for offset in range(group_rows)
            )

            ind += group_rows
            burst_number += 1
        
        fraud_amounts = np.random.randint(4700, 47800, size=fraud_rows)
        normal_like_amount_mask = np.random.random(fraud_rows) < 0.30
        fraud_amounts[normal_like_amount_mask] = np.clip(
            np.random.lognormal(
                mean=np.log(50000),
                sigma=1.0,
                size=normal_like_amount_mask.sum(),
            ).astype(int),
            1000,
            500000,
        )

        fraud_data = {
            "transaction_id" : [str(uuid.uuid4())[:18] for _ in range(fraud_rows)],
            "card_token" : card_tokens_fraud,
            "device_id": device_id_fraud,

            # Botnets running card testing execute micro-charges to verify accounts
            "amount_paise" : fraud_amounts,
            "merchant_category": merchant_id_fraud,
            "is_fraud": np.ones(fraud_rows, dtype=int)
        }

        df_fraud = pd.DataFrame(fraud_data)
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
