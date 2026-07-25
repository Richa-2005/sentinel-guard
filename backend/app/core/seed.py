import json
import hashlib
from datetime import datetime, timezone, timedelta
from app.core.database import SentinelDatabase
from app.config import settings

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
password_hash = PasswordHash((Argon2Hasher(),))

def seed_demo_data():
    if not settings.DEMO_MODE:
        return

    db = SentinelDatabase()
    with db.connection() as conn:
        conn.execute("UPDATE users SET email = 'admin@sentinel.dev' WHERE email = 'admin@sentinel.local'")
        conn.execute("UPDATE users SET email = 'analyst@sentinel.dev' WHERE email = 'analyst@sentinel.local'")

        count = conn.execute("SELECT COUNT(*) as cnt FROM transactions_ledger").fetchone()["cnt"]
        if count > 0:
            return

        print("DEMO_MODE active: Seeding Llama 3.1 deterministic presentation data...")

        admin_pass = password_hash.hash("admin")
        analyst_pass = password_hash.hash("analyst")

        conn.execute("INSERT OR IGNORE INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)", 
                     ("admin@sentinel.dev", "System Admin", admin_pass, "admin"))
        conn.execute("INSERT OR IGNORE INTO users (email, full_name, password_hash, role) VALUES (?, ?, ?, ?)", 
                     ("analyst@sentinel.dev", "Lead Analyst", analyst_pass, "analyst"))

        burst_shap = '{"xgb_normalized_impacts": {"amount_paise": -0.1173, "card_vel_10m": 0.1482, "device_card_ratio_30m": 0.24, "device_card_limit_crossed": 0.2, "is_known_merchant": 0.12, "is_off_hours_window": -0.03}, "lgb_normalized_impacts": {"amount_paise": 0.0723, "card_vel_10m": -0.0201, "device_card_ratio_30m": 0.2592, "device_card_limit_crossed": 0.176, "is_known_merchant": 0.1296, "is_off_hours_window": -0.0264}}'
        burst_metrics = '{"card_vel_10m": 4, "device_card_ratio_30m": 0.91, "device_card_limit_crossed": 1, "is_known_merchant": 0, "is_off_hours_window": 1}'

        transactions = [
            {'transaction_id': 'demo-002', 'card_id': 'card_token_211', 'device_id': 'device_trusted_01', 'merchant_id': '5732', 'timestamp': '2026-07-25T17:01:59.021Z', 'amount_paise': 1918, 'ensemble_risk_score': 0.049, 'is_blocked': 0, 'hydrated_metrics': '{"card_vel_10m": 1, "device_card_ratio_30m": 0.21, "device_card_limit_crossed": 0, "is_known_merchant": 1, "is_off_hours_window": 0}', 'shap_payload': '{"xgb_normalized_impacts": {"amount_paise": 0.08, "card_vel_10m": -0.12, "device_card_ratio_30m": -0.18, "device_card_limit_crossed": -0.04, "is_known_merchant": -0.22, "is_off_hours_window": -0.03}, "lgb_normalized_impacts": {"amount_paise": 0.0864, "card_vel_10m": -0.1056, "device_card_ratio_30m": -0.1944, "device_card_limit_crossed": -0.0352, "is_known_merchant": -0.2376, "is_off_hours_window": -0.0264}}'},
            {'transaction_id': 'demo-011', 'card_id': 'card_token_220', 'device_id': 'device_trusted_10', 'merchant_id': '5411', 'timestamp': '2026-07-25T17:36:47.021Z', 'amount_paise': 7489, 'ensemble_risk_score': 0.049, 'is_blocked': 0, 'hydrated_metrics': '{"card_vel_10m": 1, "device_card_ratio_30m": 0.3, "device_card_limit_crossed": 0, "is_known_merchant": 1, "is_off_hours_window": 0}', 'shap_payload': '{"xgb_normalized_impacts": {"amount_paise": 0.08, "card_vel_10m": -0.12, "device_card_ratio_30m": -0.18, "device_card_limit_crossed": -0.04, "is_known_merchant": -0.22, "is_off_hours_window": -0.03}, "lgb_normalized_impacts": {"amount_paise": 0.0864, "card_vel_10m": -0.1056, "device_card_ratio_30m": -0.1944, "device_card_limit_crossed": -0.0352, "is_known_merchant": -0.2376, "is_off_hours_window": -0.0264}}'},
            {'transaction_id': 'demo-026', 'card_id': 'card_token_217', 'device_id': 'device_trusted_01', 'merchant_id': '5411', 'timestamp': '2026-07-25T17:54:47.021Z', 'amount_paise': 16774, 'ensemble_risk_score': 0.235, 'is_blocked': 0, 'hydrated_metrics': '{"card_vel_10m": 1, "device_card_ratio_30m": 0.21, "device_card_limit_crossed": 0, "is_known_merchant": 1, "is_off_hours_window": 1}', 'shap_payload': '{"xgb_normalized_impacts": {"amount_paise": 0.08, "card_vel_10m": -0.12, "device_card_ratio_30m": -0.18, "device_card_limit_crossed": -0.04, "is_known_merchant": -0.22, "is_off_hours_window": 0.05}, "lgb_normalized_impacts": {"amount_paise": 0.0864, "card_vel_10m": -0.1056, "device_card_ratio_30m": -0.1944, "device_card_limit_crossed": -0.0352, "is_known_merchant": -0.2376, "is_off_hours_window": 0.044}}'},
            
            {
                'transaction_id': 'guided-7c2495a7-ca36-41ec-a51a-a50cc37c73c0', 'card_id': 'guided_risk_card_1', 'device_id': 'guided_device_ring_01', 'merchant_id': 'risk_merchant_1', 'timestamp': '2026-07-25T18:38:06.000Z', 'amount_paise': 12380, 'ensemble_risk_score': 0.9977, 'is_blocked': 1, 'hydrated_metrics': burst_metrics, 'shap_payload': burst_shap,
                'memo': """# Sentinel Guard Compliance Memorandum

- Record: 21
- Transaction: guided-7c2495a7-ca36-41ec-a51a-a50cc37c73c0
- Card: guided_risk_card_1
- Recorded: 25/07/2026, 13:08:12 UTC
- Chain state: Append-only

## A. Executive Risk Verdict
Based on the provided evidence, the transaction in question exhibits a high risk profile. The ensemble risk score of 0.997740626335144 indicates a strong likelihood of fraudulent activity. Furthermore, the transaction was blocked due to elevated risk, suggesting that the system's risk assessment mechanisms have identified potential red flags. The strongest model-supported signals come from the architectural divergence alerts on features 'amount_paise' and 'card_vel_10m', which indicate disagreement between the XGBoost and LightGBM models on the direction of the feature's contribution to the risk score. This discrepancy suggests that the transaction may be attempting to evade detection by exploiting differences in the models' behavior.
## B. Technical Specification Profile
* The transaction ID is "guided-7c2495a7-ca36-41ec-a51a-a50cc37c73c0".
* The card ID is "guided_risk_card_1".
* The device ID is "guided_device_ring_01".
* The merchant ID is "risk_merchant_1".
* The transaction amount is 12380 paise.
* The ensemble risk score is 0.997740626335144.
* The transaction was blocked due to elevated risk.
* The XGBoost model contributed -11.73% to the risk score for the 'amount_paise' feature, while the LightGBM model contributed +7.23%.
* The XGBoost model contributed +14.82% to the risk score for the 'card_vel_10m' feature, while the LightGBM model contributed -2.01%.
* The transaction occurred during an off-hours window (18:38:06 on July 25, 2026).
## C. Regulatory Compliance Cross-Reference
Internal synthetic guidance from Nexus Fintech Solutions' Global Corporate Operational Policy Manual (NX-POL-2026-T&E-04) highlights the following relevant points:

* Section 2.2: Rolling temporal velocity constraints must be enforced to prevent programmatic automated fraud-script leakage and brute-force card testing.
* Section 3.1: Off-hours restricted processing tier applies to transactions executed between 01:00 AM and 05:00 AM local terminal time.
* Section 3.2: Transactions executed during off-hours that display an unknown merchant anchor or elevated transaction amount must be flagged for asynchronous LLM audit trail generation.
* Section 4.1: Any transaction containment pass or systemic gateway rejection triggered by automated velocity tracking systems or multiplex fraud ring identifiers must be immediately fed down into an offline compliance auditing process.
## D. Mitigation and Actionable Defense Roadmap
1. Conduct a thorough review of the transaction's risk profile, including the ensemble risk score and architectural divergence alerts.
2. Verify the transaction's compliance with rolling temporal velocity constraints and off-hours restricted processing tier.
3. Investigate the merchant's reputation and verify their identity to ensure they are not a known risk.
4. Analyze the transaction's velocity profile to determine if it exceeds the structural volume cap.
5. Review the transaction's device and card information to identify any potential red flags.
6. Submit a comprehensive forensic review to the internal Audit Committee of the Board if the potential exposure matches or exceeds 25.00 Lakh.
"""
            },
            {
                'transaction_id': 'guided-e431c88c-ae1c-48e7-974e-fb9944bad56b', 'card_id': 'guided_risk_card_2', 'device_id': 'guided_device_ring_01', 'merchant_id': 'risk_merchant_2', 'timestamp': '2026-07-25T18:38:07.021Z', 'amount_paise': 12380, 'ensemble_risk_score': 0.9977, 'is_blocked': 1, 'hydrated_metrics': burst_metrics, 'shap_payload': burst_shap,
                'memo': """# Sentinel Guard Compliance Memorandum

- Record: 22
- Transaction: guided-e431c88c-ae1c-48e7-974e-fb9944bad56b
- Card: guided_risk_card_2
- Recorded: 25/07/2026, 13:08:18 UTC
- Chain state: Append-only

## A. Executive Risk Verdict
Based on the strongest model-supported signals, the transaction in question exhibits high-risk characteristics. The ensemble risk score of 0.997740626335144 indicates a strong likelihood of fraudulent activity. Furthermore, the architectural divergence alerts on features 'amount_paise' and 'card_vel_10m' suggest that the models disagree on the direction of the risk, with XGBoost indicating a higher risk and LightGBM indicating a lower risk. This discrepancy highlights the need for further investigation and review.
## B. Technical Specification Profile
* The transaction ID is guided-e431c88c-ae1c-48e7-974e-fb9944bad56b.
* The card ID is guided_risk_card_2.
* The device ID is guided_device_ring_01.
* The merchant ID is risk_merchant_2.
* The transaction timestamp is 2026-07-25T18:38:07.021797.
* The transaction amount is 12380 paise.
* The ensemble risk score is 0.997740626335144.
* The transaction is blocked.
* The models disagree on the direction of the risk for features 'amount_paise' and 'card_vel_10m'.
* The relative contributions of XGBoost and LightGBM for feature 'amount_paise' are -11.73% and +7.23%, respectively.
* The relative contributions of XGBoost and LightGBM for feature 'card_vel_10m' are +14.82% and -2.01%, respectively.
## C. Regulatory Compliance Cross-Reference
Internal synthetic guidance from Nexus Fintech Solutions' Global Corporate Operational Policy Manual (NX-POL-2026-T&E-04) highlights the following relevant points:

* Section 2.2: Rolling temporal velocity constraints must be enforced to prevent programmatic automated fraud-script leakage and brute-force card testing.
* Section 3.1: Off-hours restricted processing tier must be applied between 01:00 AM and 05:00 AM local terminal time.
* Section 3.2: Transactions executed during this window that display an unknown merchant anchor or elevated transaction amount must be flagged for asynchronous LLM audit trail generation.
* Section 4.1: Any transaction containment pass or systemic gateway rejection triggered by automated velocity tracking systems or multiplex fraud ring identifiers must be immediately fed down into an offline compliance auditing process.
## D. Mitigation and Actionable Defense Roadmap
1. Review the transaction in question to determine the underlying modus operandi and identify potential system failure points.
2. Conduct a comprehensive forensic review to outline the transaction's velocity profile and identify any structural patches applied.
3. Flag the transaction for asynchronous LLM audit trail generation due to its execution during the off-hours restricted processing tier.
4. Evaluate the transaction's velocity limits to determine if it has crossed the structural volume cap, triggering an inline decline authorization code (Decline Code 59: Suspected Fraud).
5. Submit a comprehensive forensic review directly to the internal Audit Committee of the Board, outlining the underlying transaction modus operandi, system failure points, and immediate structural patches applied, if the potential exposure matches or exceeds 25.00 Lakh.
"""
            },
            {
                'transaction_id': 'guided-ad4a6b83-2b03-4c6d-875d-b35f9c1a039f', 'card_id': 'guided_risk_card_3', 'device_id': 'guided_device_ring_01', 'merchant_id': 'risk_merchant_3', 'timestamp': '2026-07-25T18:38:08.000Z', 'amount_paise': 12380, 'ensemble_risk_score': 0.9977, 'is_blocked': 1, 'hydrated_metrics': burst_metrics, 'shap_payload': burst_shap,
                'memo': """# Sentinel Guard Compliance Memorandum

- Record: 23
- Transaction: guided-ad4a6b83-2b03-4c6d-875d-b35f9c1a039f
- Card: guided_risk_card_3
- Recorded: 25/07/2026, 13:08:25 UTC
- Chain state: Append-only

## A. Executive Risk Verdict
Based on the strongest model-supported signals, the transaction in question exhibits high-risk characteristics. The ensemble risk score of 0.997740626335144 indicates a strong likelihood of fraudulent activity. Furthermore, the models disagree on the direction of the feature 'amount_paise', with XGBoost indicating a negative contribution and LightGBM indicating a positive contribution. This disagreement suggests that the transaction may be attempting to evade detection. Additionally, the transaction was blocked, which further supports the high-risk assessment.
## B. Technical Specification Profile
* The transaction ID is guided-ad4a6b83-2b03-4c6d-875d-b35f9c1a039f.
* The card ID is guided_risk_card_3.
* The device ID is guided_device_ring_01.
* The merchant ID is risk_merchant_3.
* The transaction amount is 12380 paise.
* The ensemble risk score is 0.997740626335144.
* The transaction was blocked.
* The models disagree on the direction of the feature 'amount_paise'.
* The models disagree on the direction of the feature 'card_vel_10m'.
## C. Regulatory Compliance Cross-Reference
* According to Section 2.2 of the internal reference context, a rolling temporal velocity constraint is in place to prevent programmatic automated fraud-script leakage and brute-force card testing. The constraint limits individual card signatures to a maximum threshold of three (3) transaction authorization requests within any rolling ten (10) minute window.
* According to Section 3.2 of the internal reference context, transactions executed during the 01:00 AM - 05:00 AM temporal boundary that simultaneously display an unknown merchant anchor or elevated transaction amount must be flagged for asynchronous LLM audit trail generation.
* According to Section 2.1 of the internal reference context, Visa Core Rule 5.3.7.4 requires card-issuing platforms to enforce strict real-time velocity limits to identify and counter programmatic testing and systematic card sweeps.
* According to Section 4.1 of the internal reference context, any transaction containment pass or systemic gateway rejection triggered by automated velocity tracking systems or multiplex fraud ring identifiers must be immediately fed down into an offline compliance auditing process.
## D. Mitigation and Actionable Defense Roadmap
1. Review the transaction logs to determine if the card signature has exceeded the rolling temporal velocity constraint of three (3) transaction authorization requests within any rolling ten (10) minute window.
2. Verify if the transaction was executed during the 01:00 AM - 05:00 AM temporal boundary and if it simultaneously displays an unknown merchant anchor or elevated transaction amount.
3. Check if the transaction amount exceeds 1.00 Lakh, which would require a comprehensive forensic review to be submitted directly before the internal Audit Committee of the Board.
4. Conduct a thorough analysis of the transaction modus operandi, system failure points, and immediate structural patches applied to prevent similar incidents in the future.
5. Update the system to flag transactions that exhibit structural deviations from normal usage profiles, such as unusual geographic offsets, un-characteristic merchant category codes (MCC), or sudden velocity shifts.
6. Implement additional controls to prevent programmatic automated fraud-script leakage and brute-force card testing, such as IP blocking or rate limiting.
"""
            },
            {
                'transaction_id': 'guided-d68bb3e0-86d6-4c4e-a5e0-431e11595cb9', 'card_id': 'guided_risk_card_4', 'device_id': 'guided_device_ring_01', 'merchant_id': 'risk_merchant_4', 'timestamp': '2026-07-25T18:38:08.421Z', 'amount_paise': 12380, 'ensemble_risk_score': 0.9977, 'is_blocked': 1, 'hydrated_metrics': burst_metrics, 'shap_payload': burst_shap,
                'memo': """# Sentinel Guard Compliance Memorandum

- Record: 23
- Transaction: guided-ad4a6b83-2b03-4c6d-875d-b35f9c1a039f
- Card: guided_risk_card_3
- Recorded: 25/07/2026, 13:08:25 UTC
- Chain state: Append-only

## A. Executive Risk Verdict
Based on the strongest model-supported signals, the transaction in question exhibits high-risk characteristics. The ensemble risk score of 0.997740626335144 indicates a strong likelihood of fraudulent activity. Furthermore, the models disagree on the direction of the feature 'amount_paise', with XGBoost indicating a negative contribution and LightGBM indicating a positive contribution. This disagreement suggests that the transaction may be attempting to evade detection. Additionally, the transaction was blocked, which further supports the high-risk assessment.
## B. Technical Specification Profile
* The transaction ID is guided-ad4a6b83-2b03-4c6d-875d-b35f9c1a039f.
* The card ID is guided_risk_card_3.
* The device ID is guided_device_ring_01.
* The merchant ID is risk_merchant_3.
* The transaction amount is 12380 paise.
* The ensemble risk score is 0.997740626335144.
* The transaction was blocked.
* The models disagree on the direction of the feature 'amount_paise'.
* The models disagree on the direction of the feature 'card_vel_10m'.
## C. Regulatory Compliance Cross-Reference
* According to Section 2.2 of the internal reference context, a rolling temporal velocity constraint is in place to prevent programmatic automated fraud-script leakage and brute-force card testing. The constraint limits individual card signatures to a maximum threshold of three (3) transaction authorization requests within any rolling ten (10) minute window.
* According to Section 3.2 of the internal reference context, transactions executed during the 01:00 AM - 05:00 AM temporal boundary that simultaneously display an unknown merchant anchor or elevated transaction amount must be flagged for asynchronous LLM audit trail generation.
* According to Section 2.1 of the internal reference context, Visa Core Rule 5.3.7.4 requires card-issuing platforms to enforce strict real-time velocity limits to identify and counter programmatic testing and systematic card sweeps.
* According to Section 4.1 of the internal reference context, any transaction containment pass or systemic gateway rejection triggered by automated velocity tracking systems or multiplex fraud ring identifiers must be immediately fed down into an offline compliance auditing process.
## D. Mitigation and Actionable Defense Roadmap
1. Review the transaction logs to determine if the card signature has exceeded the rolling temporal velocity constraint of three (3) transaction authorization requests within any rolling ten (10) minute window.
2. Verify if the transaction was executed during the 01:00 AM - 05:00 AM temporal boundary and if it simultaneously displays an unknown merchant anchor or elevated transaction amount.
3. Check if the transaction amount exceeds 1.00 Lakh, which would require a comprehensive forensic review to be submitted directly before the internal Audit Committee of the Board.
4. Conduct a thorough analysis of the transaction modus operandi, system failure points, and immediate structural patches applied to prevent similar incidents in the future.
5. Update the system to flag transactions that exhibit structural deviations from normal usage profiles, such as unusual geographic offsets, un-characteristic merchant category codes (MCC), or sudden velocity shifts.
6. Implement additional controls to prevent programmatic automated fraud-script leakage and brute-force card testing, such as IP blocking or rate limiting.
"""
            }
        ]

        previous_hash = "0" * 64

        now_time = datetime.now(timezone.utc)
        for index, tx in enumerate(transactions):
            offset_minutes = 45 - index * 5
            tx_time = now_time - timedelta(minutes=offset_minutes)
            tx['timestamp'] = tx_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")

        for tx in transactions:
            conn.execute("""
                INSERT INTO transactions_ledger (
                    transaction_id, card_id, device_id, merchant_id, timestamp, 
                    amount_paise, ensemble_risk_score, is_blocked, hydrated_metrics, shap_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tx['transaction_id'], tx['card_id'], tx['device_id'], tx['merchant_id'], 
                  tx['timestamp'], tx['amount_paise'], tx['ensemble_risk_score'], 
                  tx['is_blocked'], tx['hydrated_metrics'], tx['shap_payload']))

            if tx['is_blocked'] == 1:
                conn.execute("INSERT INTO review_cases (transaction_id, status, priority, version) VALUES (?, 'open', 'critical', 1)", (tx['transaction_id'],))
                
                payload = json.dumps({"transaction_id": tx['transaction_id'], "event_type": "BLOCKED_TRANSACTION_AUDIT", "compliance_memo": tx['memo'], "previous_hash": previous_hash}, sort_keys=True)
                current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                
                conn.execute("INSERT INTO audit_vault (transaction_id, event_type, compliance_memo, previous_hash, current_hash) VALUES (?, 'BLOCKED_TRANSACTION_AUDIT', ?, ?, ?)", 
                             (tx['transaction_id'], tx['memo'], previous_hash, current_hash))
                
                previous_hash = current_hash
                
                conn.execute("INSERT INTO audit_jobs (transaction_id, status, attempts) VALUES (?, 'COMPLETED', 1)", (tx['transaction_id'],))

        print("Successfully seeded Golden Transactions, Analyst Cases, and Llama 3.1 Audit Vaults.")

if __name__ == "__main__":
    seed_demo_data()