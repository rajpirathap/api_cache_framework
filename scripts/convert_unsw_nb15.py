#!/usr/bin/env python
"""
Convert UNSW-NB15 CSV to the format expected by load_real_data and evaluate_real.

UNSW-NB15: Real-world network traffic from UNSW Canberra (2015).
49 features; labels: 0=normal, 1=attack (DoS, Exploits, Fuzzers, etc.)

Output format: timestamp, key, size_bytes, label
  - key = dstip:dsport (destination IP:port)
  - size_bytes = sbytes + dbytes
  - label = normal (0) or anomaly (1)

Usage:
  python scripts/convert_unsw_nb15.py input.csv -o output.csv
  python scripts/convert_unsw_nb15.py input.csv -o output.csv --limit 20000
"""
import argparse
import csv
import re
import sys

# UNSW-NB15 column names (case-insensitive); raw CSV may have no header
# Order from UNSW-NB15_features: srcip, sport, dstip, dsport, proto, state, dur,
#   sbytes, dbytes, sttl, dttl, sloss, dloss, service, Sload, Dload, Spkts, Dpkts,
#   swin, dwin, stcpb, dtcpb, smeansz, dmeansz, trans_depth, res_bdy_len,
#   Sjit, Djit, Stime, Ltime, Sintpkt, Dintpkt, tcprtt, synack, ackdat,
#   is_sm_ips_ports, ct_state_ttl, ct_flw_http_mthd, is_ftp_login, ct_ftp_cmd,
#   ct_srv_src, ct_srv_dst, ct_dst_ltm, ct_src_ltm, ct_src_dport_ltm, ct_dst_sport_ltm,
#   ct_dst_src_ltm, attack_cat, label
#
# Positional indices (0-based) when no header:
DSTIP_IDX = 2
DSTPORT_IDX = 3
SBYTES_IDX = 7
DBYTES_IDX = 8
STIME_IDX = 28   # Stime
LABEL_IDX = -1   # last column


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
    s = str(s).strip()
    if s in ("0", "normal", "benign", ""):
        return 0
    return 1


def convert(
    input_path: str,
    output_path: str,
    *,
    limit: int | None = None,
) -> int:
    """Convert UNSW-NB15 CSV to simple format. Returns rows written."""
    written = 0
    with open(input_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        first_row = next(reader, None)
        if not first_row:
            return 0

        # Detect if header row
        has_header = len(first_row) > 1 and not first_row[0].replace(".", "").isdigit()
        if has_header and len(first_row) >= 50:
            fieldnames = first_row
            ts_col = _find_col(fieldnames, ["stime", "Stime", "stime_"])
            key_col = _find_col(fieldnames, ["dstip", "dst ip", "dst_ip"])
            port_col = _find_col(fieldnames, ["dsport", "dst port", "dst_port"])
            sbytes_col = _find_col(fieldnames, ["sbytes", "src bytes"])
            dbytes_col = _find_col(fieldnames, ["dbytes", "dst bytes"])
            label_col = _find_col(fieldnames, ["label", "Label"])
            use_header_cols = True
            # Fallback to positional
            if not key_col:
                key_col = fieldnames[DSTIP_IDX] if DSTIP_IDX < len(fieldnames) else None
            if not port_col:
                port_col = fieldnames[DSTPORT_IDX] if DSTPORT_IDX < len(fieldnames) else None
            if not sbytes_col:
                sbytes_col = fieldnames[SBYTES_IDX] if SBYTES_IDX < len(fieldnames) else None
            if not dbytes_col:
                dbytes_col = fieldnames[DBYTES_IDX] if DBYTES_IDX < len(fieldnames) else None
            if not ts_col:
                ts_col = fieldnames[STIME_IDX] if STIME_IDX < len(fieldnames) else None
            if not label_col:
                label_col = fieldnames[-1] if len(fieldnames) > 0 else None

            def get_val(row: list, col) -> str:
                if col and col in fieldnames:
                    idx = fieldnames.index(col)
                    return row[idx] if idx < len(row) else ""
                return ""

            rows_iter = reader
            use_header_cols = True
        else:
            # No header or too few columns; use positional
            fieldnames = None
            rows_iter = iter([first_row] + list(reader))
            key_col = DSTIP_IDX
            port_col = DSTPORT_IDX
            sbytes_col = SBYTES_IDX
            dbytes_col = DBYTES_IDX
            ts_col = STIME_IDX
            label_col = -1
            use_header_cols = False

            def get_val(row: list, idx: int) -> str:
                return row[idx] if (0 <= idx < len(row) or (idx == -1 and row)) else ""

        with open(output_path, "w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow(["timestamp", "key", "size_bytes", "label"])

            for row in rows_iter:
                if limit is not None and written >= limit:
                    break
                if len(row) < 10:
                    continue
                try:
                    if use_header_cols:
                        dstip = str(get_val(row, key_col)).strip()
                        dsport = str(get_val(row, port_col)).strip()
                        sbytes = int(float(get_val(row, sbytes_col) or 0))
                        dbytes = int(float(get_val(row, dbytes_col) or 0))
                        ts = float(get_val(row, ts_col) or 0)
                        lbl = _parse_label(get_val(row, label_col))
                    else:
                        dstip = str(row[DSTIP_IDX]).strip()
                        dsport = str(row[DSTPORT_IDX]).strip()
                        sbytes = int(float(row[SBYTES_IDX] if SBYTES_IDX < len(row) else 0))
                        dbytes = int(float(row[DBYTES_IDX] if DBYTES_IDX < len(row) else 0))
                        ts = float(row[STIME_IDX] if STIME_IDX < len(row) else 0)
                        lbl = _parse_label(row[LABEL_IDX] if row else "0")

                    key = f"{dstip}:{dsport}" if (dsport and dsport != "0") else dstip
                    if not key or key == ":":
                        continue
                    size = max(0, sbytes + dbytes)
                except (ValueError, TypeError, IndexError):
                    continue
                w.writerow([ts, key, size, "anomaly" if lbl == 1 else "normal"])
                written += 1
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert UNSW-NB15 CSV to simple format")
    ap.add_argument("input", help="Input UNSW-NB15 CSV path")
    ap.add_argument("-o", "--output", required=True, help="Output CSV path")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to convert")
    args = ap.parse_args()
    n = convert(args.input, args.output, limit=args.limit)
    print(f"Converted {n} rows to {args.output}")


if __name__ == "__main__":
    main()
