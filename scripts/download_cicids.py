#!/usr/bin/env python
"""
Download CICIDS2017 (real-world network traffic) and convert to our CSV format.

CICIDS2017: Canadian Institute for Cybersecurity intrusion detection dataset.
Source: https://www.unb.ca/cic/datasets/ids-2017.html

Usage:
  python scripts/download_cicids.py                    # Download zip, convert first 50k rows
  python scripts/download_cicids.py --limit 20000      # Convert 20k rows
  python scripts/download_cicids.py --skip-download    # Use existing zip (manual download)
  python scripts/download_cicids.py --kaggle           # Download via Kaggle CLI

Output: data/cicids_converted.csv (ready for evaluate_real.py)
"""
import argparse
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

# CICIDS2017 MachineLearningCSV (~224 MB)
CICIDS_URLS = [
    "http://cicresearch.ca/CICDataset/CIC-IDS-2017/Dataset/CIC-IDS-2017/CSVs/MachineLearningCSV.zip",
    "http://205.174.165.80/CICDataset/CIC-IDS-2017/Dataset/CSVs/MachineLearningCSV.zip",
]

# HuggingFace: smaller CSV (~52 MB), pcap_ISCX format
HUGGINGFACE_URL = "https://huggingface.co/datasets/c01dsnap/CIC-IDS2017/resolve/main/Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ZIP_PATH = DATA_DIR / "MachineLearningCSV.zip"
CICIDS_CSV = DATA_DIR / "CICIDS_Thursday_WebAttacks.csv"
OUTPUT_CSV = DATA_DIR / "cicids_converted.csv"


def download_huggingface(output_path: Path) -> bool:
    """Download CICIDS2017 CSV from HuggingFace (~52 MB)."""
    print("Downloading from HuggingFace (~52 MB)...")
    try:
        from urllib.request import urlretrieve
        urlretrieve(HUGGINGFACE_URL, output_path)
        return output_path.exists() and output_path.stat().st_size > 1_000_000
    except Exception as e:
        print(f"HuggingFace download failed: {e}")
        return False


def download_http(urls: list[str], path: Path) -> bool:
    """Try each URL until one succeeds."""
    for url in urls:
        print(f"Trying {url}...")
        print("  (File ~224 MB; may take several minutes)")
        try:
            urlretrieve(url, path)
            if path.exists() and path.stat().st_size > 1_000_000:
                return True
            path.unlink(missing_ok=True)
        except Exception as e:
            print(f"  Failed: {e}")
            path.unlink(missing_ok=True)
    return False


def download_kaggle(data_dir: Path) -> Path | None:
    """Download via Kaggle CLI. Returns path to zip or first large CSV."""
    try:
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", "ernie55ernie/cleaned-cicids2017", "-p", str(data_dir)],
            check=True,
            capture_output=True,
        )
        for f in data_dir.glob("*.csv"):
            if f.stat().st_size > 10_000:
                return f
        for z in data_dir.glob("*.zip"):
            if z.stat().st_size > 1_000_000:
                return z
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Kaggle download failed: {e}")
        print("  Install: pip install kaggle")
        print("  Configure: place kaggle.json in ~/.kaggle/")
    return None


def extract_and_convert(input_path: Path, output_path: Path, limit: int) -> int:
    """Convert CICIDS CSV (from zip or direct). Returns rows written."""
    sys.path.insert(0, str(ROOT / "scripts"))

    if input_path.suffix.lower() == ".csv":
        from convert_cicids import convert
        return convert(str(input_path), str(output_path), limit=limit)

    # Zip: extract first CSV, convert, delete temp
    csv_path = None
    with zipfile.ZipFile(input_path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".csv"):
                csv_path = DATA_DIR / Path(name).name
                with zf.open(name) as src, open(csv_path, "wb") as dst:
                    dst.write(src.read())
                break
    if not csv_path or not csv_path.exists():
        print("No CSV found in zip", file=sys.stderr)
        return 0

    from convert_cicids import convert
    n = convert(str(csv_path), str(output_path), limit=limit)
    csv_path.unlink(missing_ok=True)
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description="Download CICIDS2017 and convert to our format")
    ap.add_argument("--limit", type=int, default=50000, help="Max rows to convert (default: 50000)")
    ap.add_argument("--skip-download", action="store_true", help="Skip download; use existing zip")
    ap.add_argument("--kaggle", action="store_true", help="Download via Kaggle CLI (ernie55ernie/cleaned-cicids2017)")
    ap.add_argument("-o", "--output", default=None, help="Output CSV path")
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output) if args.output else OUTPUT_CSV
    zip_to_use = ZIP_PATH

    if not args.skip_download:
        if ZIP_PATH.exists():
            print(f"Zip already exists: {ZIP_PATH}")
        elif CICIDS_CSV.exists() and CICIDS_CSV.stat().st_size > 1_000_000:
            zip_to_use = CICIDS_CSV
            print(f"Using existing: {CICIDS_CSV}")
        elif args.kaggle:
            got = download_kaggle(DATA_DIR)
            if not got:
                sys.exit(1)
            zip_to_use = got
        else:
            if download_huggingface(CICIDS_CSV):
                zip_to_use = CICIDS_CSV
            elif not download_http(CICIDS_URLS, ZIP_PATH):
                print("\n--- Manual download ---")
                print("1. Go to: https://www.unb.ca/cic/datasets/ids-2017.html")
                print("2. Download MachineLearningCSV.zip (~224 MB)")
                print(f"3. Save to: {ZIP_PATH}")
                print("4. Run: python scripts/download_cicids.py --skip-download")
                sys.exit(1)
    else:
        if not ZIP_PATH.exists() and not CICIDS_CSV.exists():
            alt = next(DATA_DIR.glob("*.zip"), None) or next((f for f in DATA_DIR.glob("*.csv") if f.stat().st_size > 100_000), None)
            if alt:
                zip_to_use = alt
            else:
                print("No CICIDS file found. Run without --skip-download to fetch from HuggingFace.")
                sys.exit(1)
        elif CICIDS_CSV.exists() and not ZIP_PATH.exists():
            zip_to_use = CICIDS_CSV

    print(f"Converting (limit={args.limit})...")
    n = extract_and_convert(zip_to_use, out_path, args.limit)
    print(f"Converted {n} rows to {out_path}")
    print(f"\nRun evaluation:")
    print(f"  python scripts/evaluate_real.py {out_path}")
    print(f"  python scripts/evaluate_real.py {out_path} --json")


if __name__ == "__main__":
    main()
