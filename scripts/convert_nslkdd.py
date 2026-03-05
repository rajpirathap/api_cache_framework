#!/usr/bin/env python
"""
Convert NSL-KDD CSV to the format expected by load_real_data and evaluate_real.

NSL-KDD: 41 features + label (normal / attack type). Standard columns include
duration, protocol_type, service, src_bytes, dst_bytes, ... result.

Output format: timestamp, key, size_bytes, label
  - key = service or protocol_type:service
  - size_bytes = src_bytes + dst_bytes
  - timestamp = duration (or row index if duration missing)
  - label = normal (0) or anomaly (1)

Usage:
  python scripts/convert_nslkdd.py input.csv -o output.csv
  python scripts/convert_nslkdd.py input.csv -o output.csv --limit 50000
"""
import argparse
import csv
import re
import sys

# NSL-KDD column names (case-insensitive); order from KDD Cup 99 / NSL-KDD
SERVICE_COLS = ["service", "Service"]
PROTO_COLS = ["protocol_type", "protocol type", "protocol"]
SRC_BYTES_COLS = ["src_bytes", "src bytes"]
DST_BYTES_COLS = ["dst_bytes", "dst bytes"]
DURATION_COLS = ["duration", "Duration"]
LABEL_COLS = ["label", "result", "class", "attack", "outcome"]


def _norm(s: str) -> str:
    return re.sub(r"[\s._-]+", "", str(s).strip().lower())


def _find_col(fieldnames: list[str], candidates: list[str]) -> str | None:
    if not fieldnames:
        return None
    norm_fn = {_norm(h): h for h in fieldnames}
    for c in candidates:
        if _norm(c) in norm_fn:
            return norm_fn[_norm(c)]
    return None


def _parse_label(s: str) -> int:
    s = str(s).strip().lower()
    if s in ("0", "normal", "benign", ""):
        return 0
    try:
        if float(s) == 0.0:
            return 0
    except ValueError:
        pass
    return 1


# Positional indices for no-header NSL-KDD (duration, protocol_type, service, flag, src_bytes, dst_bytes, ..., label)
_IDX_DURATION, _IDX_PROTO, _IDX_SERVICE = 0, 1, 2
_IDX_SRC_BYTES, _IDX_DST_BYTES = 4, 5
_IDX_LABEL = 41  # last column


def convert(
    input_path: str,
    output_path: str,
    *,
    limit: int | None = None,
    key_use_protocol: bool = True,
) -> int:
    """Convert NSL-KDD CSV to simple format. Returns rows written."""
    written = 0
    with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if not first:
            return 0
        # No header if first row looks numeric (duration) or has protocol type in col 1
        no_header = len(first) > _IDX_LABEL and (
            first[_IDX_PROTO].lower() in ("tcp", "udp", "icmp") or first[_IDX_DURATION].replace(".", "").isdigit()
        )
        if no_header:
            rows_iter = iter([first] + list(reader))
            use_pos = True
        else:
            fieldnames = first
            service_col = _find_col(fieldnames, SERVICE_COLS)
            proto_col = _find_col(fieldnames, PROTO_COLS)
            src_col = _find_col(fieldnames, SRC_BYTES_COLS)
            dst_col = _find_col(fieldnames, DST_BYTES_COLS)
            ts_col = _find_col(fieldnames, DURATION_COLS)
            label_col = _find_col(fieldnames, LABEL_COLS) or (fieldnames[-1] if fieldnames else None)
            if not service_col and not proto_col:
                print("ERROR: No service or protocol_type column found", file=sys.stderr)
                return 0
            rows_iter = reader
            use_pos = False

        with open(output_path, "w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow(["timestamp", "key", "size_bytes", "label"])
            for row_num, row in enumerate(rows_iter):
                if limit is not None and written >= limit:
                    break
                try:
                    if use_pos:
                        if len(row) <= _IDX_LABEL:
                            continue
                        ts = float(row[_IDX_DURATION]) if row[_IDX_DURATION].replace(".", "").replace("-", "").isdigit() else float(row_num)
                        proto = str(row[_IDX_PROTO]).strip()
                        svc = str(row[_IDX_SERVICE]).strip() or "unknown"
                        src = int(float(row[_IDX_SRC_BYTES]))
                        dst = int(float(row[_IDX_DST_BYTES]))
                        lbl = _parse_label(row[_IDX_LABEL])
                    else:
                        row_dict = dict(zip(fieldnames, row)) if isinstance(row, list) else row
                        ts = float(row_dict.get(ts_col or "0", 0)) if ts_col else float(row_num)
                        proto = str(row_dict.get(proto_col or "", "")).strip()
                        svc = str(row_dict.get(service_col or "", "")).strip() or "unknown"
                        src = int(float(row_dict.get(src_col or "0", 0)))
                        dst = int(float(row_dict.get(dst_col or "0", 0)))
                        lbl = _parse_label(row_dict.get(label_col or "", "normal"))
                    key = f"{proto}:{svc}" if (key_use_protocol and proto) else svc
                    if not key or key == ":":
                        key = "unknown"
                    size = max(0, src + dst)
                except (ValueError, TypeError, IndexError):
                    continue
                w.writerow([ts, key, size, "anomaly" if lbl == 1 else "normal"])
                written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert NSL-KDD CSV to simple format")
    ap.add_argument("input", help="Input NSL-KDD CSV path (train.csv or test.csv)")
    ap.add_argument("-o", "--output", required=True, help="Output CSV path")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to convert")
    ap.add_argument("--no-protocol", action="store_true", help="Use service only as key")
    args = ap.parse_args()
    n = convert(
        args.input,
        args.output,
        limit=args.limit,
        key_use_protocol=not args.no_protocol,
    )
    print(f"Converted {n} rows to {args.output}")


if __name__ == "__main__":
    main()
