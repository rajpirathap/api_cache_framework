#!/usr/bin/env python
"""
Sweep CAS tuning parameters on real datasets (UNSW-NB15, CICIDS2017, NSL-KDD).

This helps see how changing cas_threshold and min_requests affects precision/recall.

Usage:
  python scripts/evaluate_real_sweep.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

sys.path.insert(0, os.path.join(ROOT, "api_cache_framework"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from evaluate_real import evaluate  # type: ignore


DATASETS = [
    ("UNSW-NB15", os.path.join(DATA_DIR, "unsw_nb15_converted.csv")),
    ("CICIDS2017", os.path.join(DATA_DIR, "cicids_converted.csv")),
    ("NSL-KDD", os.path.join(DATA_DIR, "nslkdd_converted.csv")),
]

CONFIGS = [
    ("baseline", 0.05, 15),
    ("lower_minreq", 0.05, 5),
    ("looser_threshold", 0.10, 5),
]


def main() -> None:
    for ds_name, ds_path in DATASETS:
        if not os.path.isfile(ds_path):
            print(f"{ds_name}: SKIP (missing {ds_path})")
            continue

        print(f"\n=== {ds_name} ({ds_path}) ===")
        for cfg_name, thr, minreq in CONFIGS:
            report = evaluate(
                ds_path,
                cas_threshold=thr,
                min_requests=minreq,
            )
            overall = report.get("overall")
            if not overall:
                print(f"  {cfg_name}: no labels in CSV")
                continue

            o = overall
            print(
                f"  {cfg_name}: thr={thr:.3f}, minreq={minreq:2d} -> "
                f"TP={o['tp']} FP={o['fp']} TN={o['tn']} FN={o['fn']} "
                f"Prec={o['precision']:.3f} Rec={o['recall']:.3f} "
                f"F1={o['f1']:.3f} Acc={o['accuracy']:.3f}"
            )


if __name__ == "__main__":
    main()

