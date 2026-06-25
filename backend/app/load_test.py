import time 
import httpx
import random
import asyncio
import numpy as np

TARGET_URL = "http://127.0.0.1:8000/api/v1/evaluate"
TOTAL_REQUESTS = 100
CONCURRENCY_LIMIT = 10  # Max simultaneous worker pipes


async def fire_transaction_packet(client:httpx.AsyncClient, request_id: int):
    """
    Randomly hits the servers endpoint with either normal transaction
    or a fraud transaction.
    """

    is_blocked = random.random() < 0.30

    if is_blocked : 
        payload = {
            "card_id": f"attack_card_{random.randint(100, 999)}",
            "device_id": f"dev_mac_{random.randint(10, 99)}",
            "amount_paise": 27370
        }
    else :
        payload = {
            "card_id": f"safe_user_{random.randint(1000, 9999)}",
            "device_id": f"dev_phone_{random.randint(1000, 9999)}",
            "amount_paise": random.randint(500, 5000)
        }
    
    start_time = time.perf_counter()

    try:
        response = await client.post(TARGET_URL, json=payload, timeout=10.0)
        latency = (time.perf_counter() - start_time) * 1000
        server_json = response.json()
        block_result = server_json.get("is_blocked",False)

        return latency, response.status_code, block_result
    except Exception as e:
        return (time.perf_counter() - start_time) * 1000, 500, False
    

async def main_orchestrator():
    
    limits = httpx.Limits(max_connections=CONCURRENCY_LIMIT, max_keepalive_connections=5)

    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [fire_transaction_packet(client, i) for i in range(TOTAL_REQUESTS)]
        results = await asyncio.gather(*tasks)
        
    latencies = [r[0] for r in results if r[1] == 200]
    blocked_count = sum(1 for r in results if r[2] is True)
    
    print("\nSENTINEL GUARD CORE BENCHMARK REGISTRY")
    print(f"Total Transactions Processed : {len(results)}")
    print(f"Successful HTTP 200 Returns  : {len(latencies)}")
    print(f"Anomalies Blocked by Engine  : {blocked_count}")
    print(f"Average Gateway Latency Speed : {np.mean(latencies):.2f} ms")
    print(f"P95 Operational Latency Fence : {np.percentile(latencies, 95):.2f} ms")
    print(f"P99 Operational Latency Fence : {np.percentile(latencies, 99):.2f} ms")

if __name__ == "__main__":
    asyncio.run(main_orchestrator())