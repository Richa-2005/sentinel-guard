import requests
import time
import random

BASE_URL = "http://127.0.0.1:8000/api/v1/evaluate"
RUN_ID = f"{int(time.time() * 1000)}_{random.randint(1000, 9999)}"


def run_scoped(identifier):
    """Keep repeated live-test runs independent without deleting SQLite history."""
    return f"{identifier}_{RUN_ID}"

def send_transaction(card_id, device_id, merchant_id, amount, scenario_name):
    payload = {
        "amount_paise": amount,
        "device_id": device_id,
        "card_id": card_id,
        "merchant_id": merchant_id,
        "transaction_id": f"TEST-{random.randint(1000,9999)}"
    }
    
    response = requests.post(BASE_URL, json=payload)
    data = response.json()
    
    print(f"\n[{scenario_name}] Transaction sent.")
    print(f" |- Card: {card_id} | Device: {device_id} | Merchant: {merchant_id}")
    print(f" |- Risk Score: {data.get('ensemble_risk_score')}")
    print(f" |- Blocked:    {data.get('is_blocked')}")
    print(f" └- Metrics:    {data.get('hydrated_metrics')}")

# TEST SCENARIO 1: The "Golden User"

print(">>> EXECUTING SCENARIO 1: Trusted Merchant Building...")
# Send two transactions to build merchant trust history in SQLite
golden_card = run_scoped("card_good_01")
golden_device = run_scoped("dev_good_01")
trusted_merchant = run_scoped("merch_trusted_99")
send_transaction(golden_card, golden_device, trusted_merchant, 15000, "Trust Building 1")
send_transaction(golden_card, golden_device, trusted_merchant, 25000, "Trust Building 2")
# The third transaction should securely pass with 'is_known_merchant': 1.0
send_transaction(golden_card, golden_device, trusted_merchant, 45000, "Golden Checkout")


# TEST SCENARIO 2: The "Carding Botnet" (Velocity Spike)

print("\n>>> EXECUTING SCENARIO 2: High-Speed Botnet Attack...")
botnet_card = run_scoped("card_stolen_01")
botnet_device = run_scoped("dev_botnet_99")
# Fire 5 rapid transactions on the SAME card to spike card_vel_10m
for i in range(5):
    send_transaction(botnet_card, botnet_device, run_scoped(f"merch_rand_{i}"), 35000, f"Botnet Strike {i+1}")
    time.sleep(0.1) # Micro-delay


# TEST SCENARIO 3: The "Distributed Fraud Ring" (Device Limits)

print("\n>>> EXECUTING SCENARIO 3: Distributed Device Hoarding...")
hacker_device = run_scoped("dev_hacker_007")
# Use ONE device to test 5 COMPLETELY DIFFERENT cards
cards_to_test = [run_scoped(card) for card in [
    "card_victim_A", "card_victim_B", "card_victim_C", "card_victim_D", "card_victim_E"
]]
target_merchant = run_scoped("merch_target_01")

for idx, victim_card in enumerate(cards_to_test):
    send_transaction(victim_card, hacker_device, target_merchant, 49000, f"Ring Attack {idx+1}")
    time.sleep(0.1)
