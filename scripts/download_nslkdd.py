#!/usr/bin/env python
"""
Download NSL-KDD and convert to our CSV format for CAS evaluation.

NSL-KDD: Network intrusion dataset (41 features + label), successor to KDD Cup 99.
Source: https://www.unb.ca/cic/datasets/nsl.html

Usage:
  python scripts/download_nslkdd.py                  # Download via HuggingFace, convert 50k
  python scripts/download_nslkdd.py --limit 30000
  python scripts/download_nslkdd.py --skip-download -i data/KDDTrain+.csv

Output: data/nslkdd_converted.csv
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_CSV = DATA_DIR / "nslkdd_converted.csv"
# GitHub raw: KDDTrain+ (no header, 42 columns)
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Jehuty4949/NSL_KDD/master/KDDTrain%2B.csv"


def download_http(output_path: Path) -> bool:
    """Download NSL-KDD from GitHub raw (~11 MB)."""
    print("Downloading NSL-KDD from GitHub...")
    try:
        from urllib.request import urlretrieve
        urlretrieve(GITHUB_RAW_URL, output_path)
        return output_path.exists() and output_path.stat().st_size > 100_000
    except Exception as e:
        print(f"HTTP download failed: {e}")
        return False


def download_huggingface(output_path: Path) -> bool:
    """Download NSL-KDD via HuggingFace datasets (avoids LFS)."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("Install: pip install datasets")
        return False
    print("Downloading NSL-KDD from HuggingFace...")
    try:
        ds = load_dataset("Mireu-Lab/NSL-KDD")
        if "train" in ds:
            df = ds["train"].to_pandas()
        else:
            df = ds[list(ds.keys())[0]].to_pandas()
        df.to_csv(output_path, index=False)
        return output_path.exists() and output_path.stat().st_size > 10_000
    except Exception as e:
        print(f"HuggingFace download failed: {e}")
        return False


def download_kaggle(data_dir: Path) -> Path | None:
    """Download NSL-KDD via Kaggle CLI."""
    try:
        subprocess.run(
            [sys.executable, "-m", "kaggle", "datasets", "download", "-d", "hassan06/nslkdd", "-p", str(data_dir), "--unzip"],
            check=True,
            capture_output=True,
        )
        for f in data_dir.rglob("*.csv"):
            if f.stat().st_size > 10_000:
                return f
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Kaggle failed: {e}")
    return None


def convert_csv(input_path: Path, output_path: Path, limit: int) -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from convert_nslkdd import convert
    return convert(str(input_path), str(output_path), limit=limit)


def main() -> None:
    ap = argparse.ArgumentParser(description="Download NSL-KDD and convert for CAS evaluation")
    ap.add_argument("--limit", type=int, default=50000, help="Max rows to convert")
    ap.add_argument("--skip-download", action="store_true", help="Use existing CSV in data/")
    ap.add_argument("-i", "--input", default=None, help="Input CSV path (with --skip-download)")
    ap.add_argument("-o", "--output", default=None, help="Output CSV path")
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
            for name in ("KDDTrain+.csv", "KDDTest+.csv", "train.csv", "test.csv", "Train.csv"):
                p = DATA_DIR / name
                if p.exists() and p.stat().st_size > 10_000:
                    csv_path = p
                    break
            if not csv_path:
                csv_path = next((f for f in DATA_DIR.rglob("*.csv") if "nsl" in f.name.lower() or "kdd" in f.name.lower()), None)
                if csv_path and csv_path.stat().st_size < 10_000:
                    csv_path = None
        if not csv_path:
            print("No NSL-KDD CSV found. Run without --skip-download or download from:")
            print("  https://www.kaggle.com/datasets/hassan06/nslkdd")
            print("  https://huggingface.co/datasets/Mireu-Lab/NSL-KDD")
            sys.exit(1)
    else:
        http_path = DATA_DIR / "KDDTrain+.csv"
        if download_http(http_path):
            csv_path = http_path
        elif download_huggingface(DATA_DIR / "nslkdd_train.csv"):
            csv_path = DATA_DIR / "nslkdd_train.csv"
        else:
            csv_path = download_kaggle(DATA_DIR)
        if not csv_path:
            print("Download failed. Manual: download from Kaggle (hassan06/nslkdd) or HuggingFace (Mireu-Lab/NSL-KDD)")
            print(f"Save CSV to {DATA_DIR} and run: python scripts/download_nslkdd.py --skip-download")
            sys.exit(1)

    print(f"Converting (limit={args.limit})...")
    n = convert_csv(csv_path, out_path, args.limit)
    print(f"Converted {n} rows to {out_path}")
    print(f"\nEvaluate: python scripts/evaluate_real.py {out_path}")
    print(f"          python scripts/evaluate_real.py {out_path} --breakdown")


if __name__ == "__main__":
    main()
