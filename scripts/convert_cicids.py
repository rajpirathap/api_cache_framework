#!/usr/bin/env python
"""
Convert CICIDS2017 CSV to the simple format expected by load_real_data and evaluate_real.

CICIDS format: flow-level data with columns such as Flow ID, Timestamp, Source IP,
Destination IP, ..., Total Length of Fwd Packets, Total Length of Bwd Packets, Label.

Output format: timestamp, key, size_bytes, label
  - key = Destination_IP or Destination_IP:Destination_Port
  - size_bytes = Total Length of Bwd Packets (or Fwd+Bwd if Bwd missing)
  - label = 0 (Benign) or 1 (attack)

Usage:
  python scripts/convert_cicids.py input.csv -o output.csv
  python scripts/convert_cicids.py input.csv -o output.csv --limit 10000  # first 10k rows
"""
import argparse
import csv
import re
import sys


# CICIDS column name variants (case-insensitive)
TS_COLS = ["timestamp", "timestamp_"]
KEY_COLS = ["destination ip", "dst ip", "destination_ip", "dst_ip", "source ip", "src ip"]
PORT_COLS = ["destination port", "dst port", "destination_port", "dst_port"]
# pcap_ISCX format (HuggingFace) uses " Destination Port", " Total Length of Bwd Packets", etc.
PORT_ONLY_COLS = ["destination port", " dst port", " destination port"]
SIZE_COLS = [
    "total length of bwd packets",
    "total length of backward packets",
    "tot bwd pkts",
    "total bwd packets",
]
SIZE_FWD_COLS = [
    "total length of fwd packets",
    "total length of forward packets",
    "tot fwd pkts",
]
LABEL_COLS = ["label", "label_", "label.", "category", "benign"]


def _norm(s: str) -> str:
    return re.sub(r"[\s._-]+", " ", s.strip().lower())


def _find_col(fieldnames: list[str], candidates: list[str]) -> str | None:
    norm_fn = {_norm(h): h for h in fieldnames}
    for c in candidates:
        if _norm(c) in norm_fn:
            return norm_fn[_norm(c)]
    return None


def _parse_cicids_ts(s: str) -> float:
    """CICIDS uses format like '3/07/2017 10:02:45' or similar."""
    s = str(s).strip()
    try:
        return float(s)
    except ValueError:
        pass
    try:
        from datetime import datetime
        for fmt in (
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(s[:26], fmt).timestamp()
            except ValueError:
                continue
    except Exception:
        pass
    return 0.0


def _parse_label(s: str) -> int:
    s = str(s).strip().lower()
    if s in ("benign", "normal", "0", "false", "no", ""):
        return 0
    return 1  # any attack type


def convert(
    input_path: str,
    output_path: str,
    *,
    limit: int | None = None,
    key_use_port: bool = True,
) -> int:
    """Convert CICIDS CSV to simple format. Returns number of rows written."""
    with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        ts_col = _find_col(fieldnames, TS_COLS)
        key_col = _find_col(fieldnames, KEY_COLS)
        port_col = _find_col(fieldnames, PORT_COLS) if key_use_port else None
        size_col = _find_col(fieldnames, SIZE_COLS)
        if not size_col:
            size_col = _find_col(fieldnames, SIZE_FWD_COLS)
        label_col = _find_col(fieldnames, LABEL_COLS)
        size_fwd_col = _find_col(fieldnames, SIZE_FWD_COLS)

        # Fallback for pcap_ISCX format: no IP, use port as key
        port_only = False
        port_col_fb = _find_col(fieldnames, PORT_ONLY_COLS) or port_col
        if not key_col and port_col_fb:
            key_col = port_col_fb
            port_only = True
            print("WARNING: No IP column; using port as key (pcap_ISCX format)", file=sys.stderr)
        if not key_col:
            print("ERROR: Could not find destination IP or port column", file=sys.stderr)
            return 0
        if not ts_col:
            print("WARNING: No timestamp column, using row index", file=sys.stderr)
        if not size_col:
            size_col = _find_col(fieldnames, ["total length of fwd packets", " total length of fwd packets"])

        written = 0
        with open(output_path, "w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow(["timestamp", "key", "size_bytes", "label"])
            for row_num, row in enumerate(reader):
                if limit is not None and written >= limit:
                    break
                try:
                    ts = _parse_cicids_ts(row.get(ts_col or "", "0")) if ts_col else float(row_num)
                    ip = str(row.get(key_col, "")).strip()
                    port = str(row.get(port_col or port_col_fb or "", "")).strip()
                    if port_only:
                        key = f"port:{ip}" if ip else f"port:{port}"
                    else:
                        key = f"{ip}:{port}" if (port and port != "0") else ip
                    if not key or key == ":" or key == "port:":
                        continue
                    bwd = int(float(row.get(size_col or "0", 0)))
                    fwd = int(float(row.get(size_fwd_col or "0", 0)))
                    size = bwd if bwd > 0 else (fwd + bwd)
                    if size < 0:
                        size = 0
                    lbl = _parse_label(row.get(label_col or "", "Benign"))
                except (ValueError, TypeError):
                    continue
                w.writerow([ts, key, size, "anomaly" if lbl == 1 else "normal"])
                written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert CICIDS2017 CSV to simple format")
    ap.add_argument("input", help="Input CICIDS CSV path")
    ap.add_argument("-o", "--output", required=True, help="Output CSV path")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to convert (default: all)")
    ap.add_argument("--no-port", action="store_true", help="Use IP only as key (no port)")
    args = ap.parse_args()
    n = convert(args.input, args.output, limit=args.limit, key_use_port=not args.no_port)
    print(f"Converted {n} rows to {args.output}")


if __name__ == "__main__":
    main()
