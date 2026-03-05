#!/usr/bin/env python
"""
Evaluate CAS-based anomaly detection on real traffic data from CSV.

CSV format: timestamp, key, size_bytes [, label]
  - Use scripts/convert_cicids.py to convert CICIDS2017 to this format.
  - Or provide your own CSV with these columns.

Usage:
  python scripts/evaluate_real.py data/real_traffic.csv
  python scripts/evaluate_real.py data/real_traffic.csv --json
  python scripts/evaluate_real.py data/real_traffic.csv --no-labels   # skip metrics, report CAS only
  python scripts/evaluate_real.py data/real_traffic.csv --breakdown   # show term1, term3, penalty, raw per endpoint
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "api_cache_framework"))
sys.path.insert(0, SCRIPTS)

from anomaly import check_anomaly
from score import cache_score, cache_score_breakdown
from load_real_data import load_csv, RealEndpoint
from generate_synthetic_data import S0, S1, ALPHA, P, K, Q, LAMBDA_MIN


def evaluate(
    csv_path: str,
    *,
    include_breakdown: bool = False,
    cas_threshold: float = 0.05,
    min_requests: int = 15,
    s0: float = S0,
    s1: float = S1,
    alpha: float = ALPHA,
    p: float = P,
    k: float = K,
    q: float = Q,
    lambda_min: float = LAMBDA_MIN,
    window_seconds: float = 300.0,
    num_windows: int = 12,
) -> dict:
    """
    Load CSV, run CAS detector, compute metrics (when labels present).
    Returns dict with config, overall metrics, by_key stats, and results.
    """
    data = load_csv(
        csv_path,
        window_seconds=window_seconds,
        num_windows=num_windows,
    )

    labeled = [ep for ep in data if ep.label >= 0]
    has_labels = len(labeled) > 0

    tp = fp = tn = fn = 0
    results: list[dict] = []

    for ep in data:
        b = cache_score_breakdown(
            lambda_=ep.lambda_,
            sigma_lambda=ep.sigma_lambda,
            mean_size=ep.mean_size,
            sigma_size=ep.sigma_size,
            s0=s0,
            s1=s1,
            alpha=alpha,
            p=p,
            k=k,
            q=q,
            lambda_min=lambda_min,
        )
        cas = b["final"]
        is_anomaly, reasons = check_anomaly(
            ep.lambda_,
            ep.sigma_lambda,
            ep.mean_size,
            ep.sigma_size,
            cas,
            ep.total_requests,
            cas_threshold=cas_threshold,
            min_requests=min_requests,
        )

        pred = 1 if is_anomaly else 0
        label = ep.label

        if has_labels and label >= 0:
            if label == 1 and pred == 1:
                tp += 1
            elif label == 0 and pred == 1:
                fp += 1
            elif label == 0 and pred == 0:
                tn += 1
            else:
                fn += 1

        row = {
            "key": ep.key,
            "label": "anomaly" if label == 1 else ("normal" if label == 0 else "unknown"),
            "predicted": "anomaly" if pred == 1 else "normal",
            "correct": (label == pred) if label >= 0 else None,
            "cas": round(cas, 4),
            "lambda": round(ep.lambda_, 2),
            "sigma_lambda": round(ep.sigma_lambda, 2),
            "mean_size": round(ep.mean_size, 1),
            "sigma_size": round(ep.sigma_size, 1),
            "total_requests": ep.total_requests,
            "reasons": reasons,
        }
        if include_breakdown:
            row["breakdown"] = {
                "term1": b["term1"],
                "size_benefit": b["size_benefit"],
                "term3": b["term3"],
                "volume_term": b["volume_term"],
                "penalty": b["penalty"],
                "positive": b["positive"],
                "raw": b["raw"],
                "final": b["final"],
            }
        results.append(row)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(labeled) if labeled else 0.0

    return {
        "config": {
            "csv_path": csv_path,
            "cas_threshold": cas_threshold,
            "min_requests": min_requests,
            "s0": s0,
            "s1": s1,
            "alpha": alpha,
            "lambda_min": lambda_min,
            "window_seconds": window_seconds,
            "num_windows": num_windows,
        },
        "data": {
            "total_endpoints": len(data),
            "labeled_endpoints": len(labeled),
        },
        "overall": {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
        } if has_labels else None,
        "results": results,
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Evaluate CAS on real traffic CSV")
    ap.add_argument("csv_path", help="Path to CSV (timestamp, key, size_bytes [, label])")
    ap.add_argument("--json", action="store_true", help="Output JSON")
    ap.add_argument("--no-labels", action="store_true", help="Skip metrics (no label column)")
    ap.add_argument("--breakdown", action="store_true", help="Include formula breakdown (term1, term3, penalty, raw) per endpoint")
    args = ap.parse_args()

    if not os.path.isfile(args.csv_path):
        print(f"Error: file not found: {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    report = evaluate(args.csv_path, include_breakdown=args.breakdown)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    # Human-readable report
    c = report["config"]
    d = report["data"]
    print("=" * 60)
    print("CAS-based Anomaly Detection — Real Data Evaluation")
    print("=" * 60)
    print(f"\nData: {c['csv_path']}")
    print(f"  Endpoints: {d['total_endpoints']}, Labeled: {d['labeled_endpoints']}")
    print(f"Config: cas_threshold={c['cas_threshold']}, min_requests={c['min_requests']}")
    print(f"        window={c['window_seconds']}s, num_windows={c['num_windows']}")

    if report["overall"]:
        o = report["overall"]
        print(f"\nOverall (labeled n={d['labeled_endpoints']})")
        print(f"  TP={o['tp']}  FP={o['fp']}  TN={o['tn']}  FN={o['fn']}")
        print(f"  Precision: {o['precision']:.4f}")
        print(f"  Recall:    {o['recall']:.4f}")
        print(f"  F1:        {o['f1']:.4f}")
        print(f"  Accuracy:  {o['accuracy']:.4f}")
    else:
        print("\nNo labels in CSV — metrics skipped. Showing CAS per endpoint.")

    print("\nTop 15 endpoints by CAS (lowest first — likely anomalies):")
    sorted_results = sorted(report["results"], key=lambda r: r["cas"])[:15]
    for r in sorted_results:
        pred = r["predicted"]
        cas = r["cas"]
        key = r["key"][:50] + "..." if len(r["key"]) > 50 else r["key"]
        print(f"  {cas:.4f}  {pred:7}  {key}")
        if "breakdown" in r:
            b = r["breakdown"]
            print(f"         term1={b['term1']} size_benefit={b['size_benefit']} term3={b['term3']} volume_term={b['volume_term']} penalty={b['penalty']} raw={b['raw']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
