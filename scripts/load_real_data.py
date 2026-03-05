"""
Load real traffic data from CSV and compute per-endpoint stats for CAS evaluation.

Expected CSV format (header required):
  - timestamp: Unix epoch (float) or ISO format
  - key: endpoint identifier (e.g. dest_ip:port, URL path)
  - size_bytes: response/flow size in bytes
  - label (optional): 0/1 or normal/anomaly — if present, used for evaluation

Alternative: timestamp, key, size_bytes (no labels; evaluation reports CAS only).
"""
import csv
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_scripts_dir)
if os.path.join(_root, "api_cache_framework") not in sys.path:
    sys.path.insert(0, os.path.join(_root, "api_cache_framework"))
from score import compute_lambda_sigma


@dataclass
class RealEndpoint:
    """Single endpoint with computed stats from real data."""
    key: str
    label: int  # 0 = normal, 1 = anomaly (or -1 if unknown)
    lambda_: float
    sigma_lambda: float
    mean_size: float
    sigma_size: float
    total_requests: int


def _parse_timestamp(s: str) -> float:
    """Parse timestamp to Unix epoch float."""
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        pass
    try:
        from datetime import datetime
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
            try:
                return datetime.strptime(s[:26], fmt).timestamp()
            except ValueError:
                continue
    except Exception:
        pass
    return 0.0


def _parse_label(s: str) -> int:
    """Parse label to 0 (normal) or 1 (anomaly)."""
    if s is None or s == "":
        return -1
    s = str(s).strip().lower()
    if s in ("0", "normal", "benign", "false", "no"):
        return 0
    if s in ("1", "anomaly", "attack", "malicious", "true", "yes"):
        return 1
    try:
        v = int(float(s))
        return 1 if v != 0 else 0
    except ValueError:
        return -1


def load_csv(
    path: str,
    timestamp_col: str = "timestamp",
    key_col: str = "key",
    size_col: str = "size_bytes",
    label_col: str | None = "label",
    *,
    window_seconds: float = 300.0,
    num_windows: int = 12,
) -> list[RealEndpoint]:
    """
    Load CSV and compute per-key (λ, σ_λ, mean_size, σ_s).
    Returns list of RealEndpoint. label=-1 if no label column.
    """
    # (ts, size, label) per row; label=-1 if no label col
    rows_by_key: dict[str, list[tuple[float, int, int]]] = defaultdict(list)

    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        norm = {h.strip().lower(): h for h in reader.fieldnames}
        ts_key = norm.get(timestamp_col.lower(), timestamp_col)
        key_key = norm.get(key_col.lower(), key_col)
        size_key = norm.get(size_col.lower(), size_col)
        has_label = label_col and norm.get((label_col or "").lower())
        lb_key = norm.get((label_col or "").lower()) if has_label else None

        for row in reader:
            try:
                ts = _parse_timestamp(row.get(ts_key, "0"))
                key = str(row.get(key_key, "")).strip()
                size = int(float(row.get(size_key, 0)))
                lbl = _parse_label(row.get(lb_key, "")) if lb_key else -1
            except (ValueError, TypeError):
                continue
            if not key:
                continue
            rows_by_key[key].append((ts, size, lbl))

    if not rows_by_key:
        return []

    all_ts = [t for triples in rows_by_key.values() for t, _, _ in triples]
    t_max = max(all_ts)
    window_start = t_max - num_windows * window_seconds
    endpoints: list[RealEndpoint] = []

    for key, triples in rows_by_key.items():
        in_window = [(t, s, lbl) for t, s, lbl in triples if t >= window_start]
        if not in_window:
            continue

        counts: list[float] = []
        for i in range(num_windows):
            w_start = window_start + i * window_seconds
            w_end = w_start + window_seconds
            cnt = sum(1 for t, _, _ in in_window if w_start <= t < w_end)
            counts.append(float(cnt))

        sizes = [s for _, s, _ in in_window]
        lambda_, sigma_lambda = compute_lambda_sigma(counts)

        n = len(sizes)
        mean_size = sum(sizes) / n
        variance = sum((x - mean_size) ** 2 for x in sizes) / n
        sigma_size = math.sqrt(variance)

        # If any flow is attack, key is anomaly; else if any normal, key is normal
        any_attack = any(lbl == 1 for _, _, lbl in in_window)
        any_normal = any(lbl == 0 for _, _, lbl in in_window)
        if any_attack:
            label = 1
        elif any_normal:
            label = 0
        else:
            label = -1

        endpoints.append(RealEndpoint(
            key=key,
            label=label,
            lambda_=lambda_,
            sigma_lambda=sigma_lambda,
            mean_size=mean_size,
            sigma_size=sigma_size,
            total_requests=len(in_window),
        ))

    return endpoints


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python load_real_data.py <csv_path>")
        sys.exit(1)
    eps = load_csv(sys.argv[1])
    print(f"Loaded {len(eps)} endpoints")
    for e in eps[:5]:
        print(f"  {e.key}: lambda={e.lambda_:.2f}, mean_size={e.mean_size:.0f}, label={e.label}")
