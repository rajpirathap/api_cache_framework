#!/usr/bin/env python
"""
Download UNSW-NB15 (real-world network traffic) and convert to our CSV format.

UNSW-NB15: UNSW Canberra network intrusion dataset (2015).
49 features; labels: 0=normal, 1=attack (DoS, Exploits, Fuzzers, etc.)
Source: https://research.unsw.edu.au/projects/unsw-nb15-dataset

Usage:
  python scripts/download_unsw_nb15.py                     # HTTP download from HuggingFace
  python scripts/download_unsw_nb15.py --kaggle            # Download via Kaggle
  python scripts/download_unsw_nb15.py --skip-download     # Convert existing CSV in data/

Output: data/unsw_nb15_converted.csv (ready for evaluate_real.py)
"""
import argparse
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_CSV = DATA_DIR / "unsw_nb15_converted.csv"
TRAINING_CSV = DATA_DIR / "UNSW_NB15_training-set.csv"

# HuggingFace direct URL (training set ~175k rows)
HUGGINGFACE_URL = "https://huggingface.co/datasets/Mouwiya/UNSW-NB15/resolve/main/UNSW_NB15_training-set.csv"

# Kaggle dataset (multiple versions exist)
KAGGLE_DATASET = "mrwellsdavid/unsw-nb15"


def download_http(output_path: Path) -> bool:
    """Download UNSW-NB15 training set from HuggingFace."""
    print(f"Downloading from HuggingFace (~60 MB)...")
    try:
        urlretrieve(HUGGINGFACE_URL, output_path)
        return output_path.exists() and output_path.stat().st_size > 1_000_000
    except Exception as e:
        print(f"HTTP download failed: {e}")
        return False


def download_kaggle(data_dir: Path) -> Path | None:
    """Download UNSW-NB15 via Kaggle CLI. Returns path to first large CSV."""
    try:
        subprocess.run(
            [sys.executable, "-m", "kaggle", "datasets", "download", "-d", KAGGLE_DATASET, "-p", str(data_dir), "--unzip"],
            check=True,
            capture_output=True,
        )
        csvs = list(data_dir.rglob("*.csv"))
        for f in sorted(csvs, key=lambda p: p.stat().st_size, reverse=True):
            if f.stat().st_size > 10_000:
                return f
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Kaggle download failed: {e}")
        print("  Install: pip install kaggle")
        print("  Configure: place kaggle.json in ~/.kaggle/ or %USERPROFILE%\\.kaggle\\")
    return None


def convert_csv(input_path: Path, output_path: Path, limit: int) -> int:
    """Convert UNSW-NB15 CSV to our format."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from convert_unsw_nb15 import convert
    return convert(str(input_path), str(output_path), limit=limit)


def main() -> None:
    ap = argparse.ArgumentParser(description="Download UNSW-NB15 and convert to our format")
    ap.add_argument("--limit", type=int, default=100000, help="Max rows to convert (default: 100000)")
    ap.add_argument("--skip-download", action="store_true", help="Skip download; use existing CSV in data/")
    ap.add_argument("--kaggle", action="store_true", help="Download via Kaggle CLI")
    ap.add_argument("-o", "--output", default=None, help="Output CSV path")
    ap.add_argument("-i", "--input", default=None, help="Input CSV path (with --skip-download)")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output) if args.output else OUTPUT_CSV

    csv_path: Path | None = None
    if args.skip_download:
        if args.input:
            csv_path = Path(args.input)
            if not csv_path.exists():
                print(f"Input not found: {csv_path}")
                sys.exit(1)
        else:
            # Prefer raw UNSW training file; exclude our converted output
            skip_names = {"unsw_nb15_converted.csv", "cicids_converted.csv"}
            csv_path = None
            for name in ("UNSW_NB15_training-set.csv", "UNSW_NB15_testing-set.csv"):
                p = DATA_DIR / name
                if p.exists():
                    csv_path = p
                    break
                for pat in ("UNSW*.csv", "*NB15*.csv", "*unsw*.csv"):
                    for f in DATA_DIR.glob(pat):
                        if f.name not in skip_names and f.stat().st_size > 100_000:
                            csv_path = f
                            break
                    if csv_path:
                        break
                if not csv_path:
                    csv_path = next((f for f in DATA_DIR.glob("*.csv") if f.name not in skip_names and f.stat().st_size > 100_000), None)
        if not csv_path or not csv_path.exists():
            print("\n--- No UNSW-NB15 CSV found ---")
            print("1. Run without --skip-download to download from HuggingFace")
            print("2. Or download from: https://www.kaggle.com/datasets/mrwellsdavid/unsw-nb15")
            print("3. Place CSV in data/ and run: python scripts/download_unsw_nb15.py --skip-download -i data/UNSW_NB15_training-set.csv")
            sys.exit(1)
    else:
        if args.kaggle:
            csv_path = download_kaggle(DATA_DIR)
        elif TRAINING_CSV.exists() and TRAINING_CSV.stat().st_size > 1_000_000:
            csv_path = TRAINING_CSV
            print(f"Using existing: {csv_path}")
        else:
            if download_http(TRAINING_CSV):
                csv_path = TRAINING_CSV
            else:
                print("\n--- Fallback: manual download ---")
                print("1. Download from: https://huggingface.co/datasets/Mouwiya/UNSW-NB15")
                print("   Or: https://www.kaggle.com/datasets/mrwellsdavid/unsw-nb15")
                print(f"2. Save UNSW_NB15_training-set.csv to: {DATA_DIR}")
                print("3. Run: python scripts/download_unsw_nb15.py --skip-download")
                sys.exit(1)
        if not csv_path:
            sys.exit(1)

    print(f"Converting {csv_path} (limit={args.limit})...")
    n = convert_csv(csv_path, out_path, args.limit)
    print(f"Converted {n} rows to {out_path}")
    print(f"\nRun evaluation:")
    print(f"  python scripts/evaluate_real.py {out_path}")
    print(f"  python scripts/evaluate_real.py {out_path} --json")


if __name__ == "__main__":
    main()
