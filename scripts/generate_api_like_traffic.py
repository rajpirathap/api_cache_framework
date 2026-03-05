#!/usr/bin/env python
"""
Generate a realistic API-like traffic CSV for CAS evaluation.

Mimics patterns from real API/CDN logs:
  - Normal: stable endpoints with moderate/high traffic and consistent payload sizes
  - frequent_small: health checks, probes, abuse (high rate + tiny responses)
  - bursty: scan or bot traffic (unstable request rate)
  - erratic_size: variable response sizes (probing different endpoints)

Output format: timestamp, key, size_bytes, label
  Compatible with scripts/load_real_data.py and evaluate_real.py

Usage:
  python scripts/generate_api_like_traffic.py -o data/api_like_traffic.csv
  python scripts/generate_api_like_traffic.py -o data/api_like_traffic.csv --rows 5000
"""
import argparse
import csv
import random
import sys
from pathlib import Path

# Reproducible
random.seed(42)

# Base timestamp (Unix epoch)
BASE_TS = 1700000000.0
WINDOW_SEC = 300.0
NUM_WINDOWS = 12


def generate_normal_endpoint(key: str, requests_per_window: float, mean_size: int, sigma_size: float) -> list[tuple[float, int, str]]:
    """Stable traffic: uniform spread, consistent sizes."""
    rows = []
    for w in range(NUM_WINDOWS):
        n = max(0, int(requests_per_window + random.gauss(0, 1)))
        for _ in range(n):
            ts = BASE_TS + w * WINDOW_SEC + random.uniform(0, WINDOW_SEC)
            size = max(100, int(mean_size + random.gauss(0, sigma_size)))
            rows.append((ts, size, "normal"))
    return rows


def generate_frequent_small_endpoint(key: str, requests_per_window: float) -> list[tuple[float, int, str]]:
    """High rate + tiny responses (DoS/probe pattern)."""
    rows = []
    for w in range(NUM_WINDOWS):
        n = max(5, int(requests_per_window + random.gauss(0, 2)))
        for _ in range(n):
            ts = BASE_TS + w * WINDOW_SEC + random.uniform(0, WINDOW_SEC)
            size = random.randint(50, 400)
            rows.append((ts, size, "anomaly"))
    return rows


def generate_bursty_endpoint(key: str, mean_per_window: float, burst_factor: float, mean_size: int) -> list[tuple[float, int, str]]:
    """Bursty: most requests in few windows."""
    rows = []
    for w in range(NUM_WINDOWS):
        # Random burst: some windows get many, others few
        mult = 1.0 + (random.random() - 0.5) * burst_factor
        n = max(0, int(mean_per_window * mult))
        for _ in range(n):
            ts = BASE_TS + w * WINDOW_SEC + random.uniform(0, WINDOW_SEC)
            size = max(500, int(mean_size + random.gauss(0, 200)))
            rows.append((ts, size, "anomaly"))
    return rows


def generate_erratic_size_endpoint(key: str, requests_per_window: float, mean_size: int, sigma_size: float) -> list[tuple[float, int, str]]:
    """Highly variable response sizes (probing/scanning)."""
    rows = []
    for w in range(NUM_WINDOWS):
        n = max(3, int(requests_per_window + random.gauss(0, 1)))
        for _ in range(n):
            ts = BASE_TS + w * WINDOW_SEC + random.uniform(0, WINDOW_SEC)
            # High variance: mix of tiny and large
            size = int(mean_size + random.gauss(0, sigma_size))
            size = max(50, min(size, 100000))
            rows.append((ts, size, "anomaly"))
    return rows


def generate_all(num_rows_target: int = 3000) -> list[tuple[float, int, str, str]]:
    """Generate (timestamp, size_bytes, label, key) rows."""
    all_rows: list[tuple[float, int, str, str]] = []

    # Normal endpoints (API paths, IP:port, etc.)
    normal_configs = [
        ("/api/products", 8, 45 * 1024, 500),
        ("/api/users", 6, 30 * 1024, 300),
        ("/api/orders", 5, 20 * 1024, 400),
        ("192.168.1.10:443", 10, 50 * 1024, 800),
        ("/api/items", 12, 40 * 1024, 600),
    ]
    for key, rpw, mean_s, sigma_s in normal_configs:
        for ts, size, lbl in generate_normal_endpoint(key, rpw, mean_s, sigma_s):
            all_rows.append((ts, size, lbl, key))

    # frequent_small
    for key in ["/health", "/ping", "10.0.0.99:80", "/metrics", "/status"]:
        for ts, size, lbl in generate_frequent_small_endpoint(key, 15):
            all_rows.append((ts, size, lbl, key))

    # bursty
    for key in ["/api/scan", "172.16.0.1:443", "/api/probe"]:
        for ts, size, lbl in generate_bursty_endpoint(key, 6, 4.0, 2000):
            all_rows.append((ts, size, lbl, key))

    # erratic_size
    for key in ["/api/random", "/api/varied", "192.168.2.5:80"]:
        for ts, size, lbl in generate_erratic_size_endpoint(key, 7, 500, 3000):
            all_rows.append((ts, size, lbl, key))

    # Shuffle by timestamp
    random.shuffle(all_rows)

    # Trim or pad to target
    if len(all_rows) > num_rows_target:
        all_rows = random.sample(all_rows, num_rows_target)
        all_rows.sort(key=lambda x: x[0])

    return all_rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate API-like traffic CSV for CAS evaluation")
    ap.add_argument("-o", "--output", default="data/api_like_traffic.csv", help="Output CSV path")
    ap.add_argument("--rows", type=int, default=3000, help="Approximate number of rows (may trim)")
    args = ap.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = generate_all(args.rows)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "key", "size_bytes", "label"])
        for ts, size, lbl, key in rows:
            w.writerow([f"{ts:.2f}", key, size, lbl])

    print(f"Wrote {len(rows)} rows to {out_path}")
    keys = set(r[3] for r in rows)
    print(f"  {len(keys)} unique keys (endpoints)")
    normal_count = sum(1 for r in rows if r[2] == "normal")
    print(f"  {normal_count} normal, {len(rows) - normal_count} anomaly rows")


if __name__ == "__main__":
    main()
