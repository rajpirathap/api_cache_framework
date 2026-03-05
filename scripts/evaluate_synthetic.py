#!/usr/bin/env python
"""
Evaluate CAS-based anomaly detection on synthetic labeled data.

Runs check_anomaly() on each synthetic endpoint and computes precision, recall, F1.
No Django required — imports anomaly and score modules directly.

Usage:
  python scripts/evaluate_synthetic.py
  python scripts/evaluate_synthetic.py --json   # JSON output for reporting
"""
import json
import os
import sys

# Add paths so we can import api_cache_framework submodules and local scripts
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "api_cache_framework"))
sys.path.insert(0, SCRIPTS)

# Import without loading Django-dependent package __init__
from anomaly import check_anomaly
from score import cache_score

from generate_synthetic_data import generate_all, S0, S1, ALPHA, P, K, Q, LAMBDA_MIN


def evaluate(
    cas_threshold: float = 0.05,
    min_requests: int = 15,
    s0: float = S0,
    s1: float = S1,
    alpha: float = ALPHA,
    p: float = P,
    k: float = K,
    q: float = Q,
    lambda_min: float = LAMBDA_MIN,
) -> dict:
    """
    Run evaluation on synthetic data.
    Returns dict with metrics and per-scenario breakdown.
    """
    data = generate_all()

    tp = fp = tn = fn = 0
    results: list[dict] = []
    by_scenario: dict[str, dict] = {}

    for ep in data:
        cas = cache_score(
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

        if label == 1 and pred == 1:
            tp += 1
        elif label == 0 and pred == 1:
            fp += 1
        elif label == 0 and pred == 0:
            tn += 1
        else:
            fn += 1

        if ep.scenario not in by_scenario:
            by_scenario[ep.scenario] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0, "total": 0}
        by_scenario[ep.scenario]["total"] += 1
        if label == 1 and pred == 1:
            by_scenario[ep.scenario]["tp"] += 1
        elif label == 0 and pred == 1:
            by_scenario[ep.scenario]["fp"] += 1
        elif label == 0 and pred == 0:
            by_scenario[ep.scenario]["tn"] += 1
        else:
            by_scenario[ep.scenario]["fn"] += 1

        results.append({
            "scenario": ep.scenario,
            "label": "anomaly" if label == 1 else "normal",
            "predicted": "anomaly" if pred == 1 else "normal",
            "correct": label == pred,
            "cas": round(cas, 4),
            "reasons": reasons,
        })

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(data) if data else 0.0

    for sc, m in by_scenario.items():
        p = m["tp"] / (m["tp"] + m["fp"]) if (m["tp"] + m["fp"]) > 0 else 0.0
        r = m["tp"] / (m["tp"] + m["fn"]) if (m["tp"] + m["fn"]) > 0 else 0.0
        m["precision"] = round(p, 4)
        m["recall"] = round(r, 4)
        m["f1"] = round(2 * p * r / (p + r), 4) if (p + r) > 0 else 0.0
        m["correct_rate"] = round((m["tp"] + m["tn"]) / m["total"], 4)

    return {
        "config": {
            "cas_threshold": cas_threshold,
            "min_requests": min_requests,
            "s0": s0,
            "s1": s1,
            "alpha": alpha,
            "p": p,
            "k": k,
            "q": q,
        },
        "overall": {
            "total": len(data),
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
        },
        "by_scenario": by_scenario,
        "results": results,
    }


def main() -> None:
    as_json = "--json" in sys.argv
    report = evaluate()

    if as_json:
        print(json.dumps(report, indent=2))
        return

    # Human-readable report
    o = report["overall"]
    c = report["config"]
    print("=" * 60)
    print("CAS-based Anomaly Detection — Synthetic Evaluation Report")
    print("=" * 60)
    print(f"\nConfig: cas_threshold={c['cas_threshold']}, min_requests={c['min_requests']}")
    print(f"        s0={c['s0']} B, s1={c['s1']} B, alpha={c['alpha']}, p={c['p']}, k={c['k']}, q={c['q']}")
    print(f"\nOverall (n={o['total']})")
    print(f"  TP={o['tp']}  FP={o['fp']}  TN={o['tn']}  FN={o['fn']}")
    print(f"  Precision: {o['precision']:.4f}")
    print(f"  Recall:    {o['recall']:.4f}")
    print(f"  F1:        {o['f1']:.4f}")
    print(f"  Accuracy:  {o['accuracy']:.4f}")
    print("\nPer-scenario (correct_rate = fraction correctly classified):")
    for sc, m in report["by_scenario"].items():
        print(f"  {sc}: P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f} correct={m['correct_rate']:.4f} (n={m['total']})")
    print("=" * 60)


if __name__ == "__main__":
    main()
