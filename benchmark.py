import asyncio
import aiohttp
import statistics
import time
from collections import Counter

BASE_URL = "http://127.0.0.1:8001"
TOKEN = "BE58FB0A-2D91-48C2-93ED-600FB16E021A"

DURATION = 60
CONCURRENT_WORKERS = 250
TIMEOUT = 1

NUM_NAMESPACES = 10
NUM_DOCUMENTS = 10

latencies = []
status_codes = Counter()
operation_counts = Counter()

total_requests = 0
total_errors = 0

start_time = None


def percentile(values, pct):
    if not values:
        return 0

    values = sorted(values)

    k = (len(values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(values) - 1)

    if f == c:
        return values[f]

    return values[f] + (values[c] - values[f]) * (k - f)


async def perform_request(session, method, url, payload=None):
    global total_requests, total_errors

    t0 = time.perf_counter()

    try:
        async with session.request(
            method,
            url,
            json=payload,
        ) as response:

            await response.read()

            latency = (time.perf_counter() - t0) * 1000

            latencies.append(latency)
            status_codes[response.status] += 1
            total_requests += 1

            if response.status >= 400:
                total_errors += 1

    except Exception:
        latency = (time.perf_counter() - t0) * 1000

        latencies.append(latency)
        total_requests += 1
        total_errors += 1
        status_codes["EXCEPTION"] += 1


async def worker(session, worker_id):
    global start_time

    ns = f"ns{worker_id % NUM_NAMESPACES}"
    doc = f"doc{(worker_id // NUM_NAMESPACES) % NUM_DOCUMENTS}"

    while True:

        if time.time() - start_time >= DURATION:
            return

        for i in range(20):
            key = f"key{i}"

            url = f"{BASE_URL}/item/{ns}/{doc}/{key}"

            await perform_request(
                session,
                "POST",
                url,
                {"value": f"value-{i}"}
            )
            operation_counts["POST"] += 1

        for i in range(20):
            key = f"key{i}"

            url = f"{BASE_URL}/item/{ns}/{doc}/{key}"

            await perform_request(
                session,
                "GET",
                url
            )
            operation_counts["GET"] += 1

        for i in range(20):
            key = f"key{i}"

            url = f"{BASE_URL}/item/{ns}/{doc}/{key}"

            await perform_request(
                session,
                "DELETE",
                url
            )
            operation_counts["DELETE"] += 1


async def main():
    global start_time

    connector = aiohttp.TCPConnector(
        limit=0,
        ttl_dns_cache=300
    )

    timeout = aiohttp.ClientTimeout(total=TIMEOUT)

    headers = {
        "Authorization": f"Bearer {TOKEN}"
    }

    async with aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers=headers
    ) as session:

        start_time = time.time()

        tasks = [
            asyncio.create_task(worker(session, i))
            for i in range(CONCURRENT_WORKERS)
        ]

        await asyncio.gather(*tasks)

    runtime = time.time() - start_time

    print()
    print("=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)

    print(f"Duration:              {runtime:.2f}s")
    print(f"Concurrent Workers:    {CONCURRENT_WORKERS}")
    print(f"Namespaces:            {NUM_NAMESPACES}")
    print(f"Documents/Namespace:   {NUM_DOCUMENTS}")
    print(f"Total Documents:       {NUM_NAMESPACES * NUM_DOCUMENTS}")
    print(f"Total Requests:        {total_requests}")
    print(f"Requests/sec:          {total_requests / runtime:.2f}")
    print(f"Error Rate:            {(total_errors / max(total_requests, 1)) * 100:.2f}%")

    print()

    print("Operations:")
    for op, count in operation_counts.items():
        print(f"  {op:<10} {count}")

    print()

    if latencies:
        print("Latency (ms)")
        print(f"  Min:      {min(latencies):.2f}")
        print(f"  Avg:      {statistics.mean(latencies):.2f}")
        print(f"  Median:   {statistics.median(latencies):.2f}")
        print(f"  P90:      {percentile(latencies, 90):.2f}")
        print(f"  P95:      {percentile(latencies, 95):.2f}")
        print(f"  P99:      {percentile(latencies, 99):.2f}")
        print(f"  Max:      {max(latencies):.2f}")

    print()

    print("Status Codes:")
    for code, count in sorted(status_codes.items(), key=lambda x: str(x[0])):
        print(f"  {code}: {count}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
