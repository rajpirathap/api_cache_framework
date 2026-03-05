# CAS-based Anomaly Detection — Evaluation with Simulated Data

This document describes the synthetic data setup and evaluation methodology for research reporting.

## Overview

- **Data**: Parameterized synthetic endpoints with known (λ, σ_λ, mean_size, σ_s).
- **Labels**: `normal` (0) vs `anomaly` (1) based on scenario design.
- **Decision rule**: ANOMALY if `total_requests >= min_requests` and `CAS < cas_threshold`.
- **Metrics**: Precision, Recall, F1, Accuracy.

## Scenarios

| Scenario       | Label   | Description                                         |
|----------------|---------|-----------------------------------------------------|
| normal         | 0       | High λ, low σ_λ, large mean_size → high CAS         |
| frequent_small | 1       | High λ + small mean_size (DoS/abuse pattern)        |
| bursty         | 1       | High σ_λ vs λ → term1 suppressed                    |
| erratic_size   | 1       | High σ_s vs mean_size → term3 suppressed            |
| low_cas        | 1       | Mixed factors yielding low CAS                      |

## Files

- `scripts/generate_synthetic_data.py` — Parameterized generator; produces labeled endpoints.
- `scripts/evaluate_synthetic.py` — Runs detector, computes metrics, outputs report.

## Usage

```bash
cd "C:\Raj Files\api_cache_framework"
.\.venv\Scripts\Activate.ps1

# Human-readable report
python scripts/evaluate_synthetic.py

# JSON output (for scripts, LaTeX tables, etc.)
python scripts/evaluate_synthetic.py --json
```

## Config

Defaults in the evaluator:

- `cas_threshold = 0.05`
- `min_requests = 15`
- `s0 = 10240` (10 KB), `s1 = 5120` (5 KB), `alpha = 0.2`

To change parameters, edit `evaluate()` in `scripts/evaluate_synthetic.py` or extend the CLI.

## Reproducibility

- Synthetic data is deterministic (fixed parameter sets per scenario).
- No random seeds; same run always yields the same metrics.
- Document the script version and config used for any reported results.

## Extending the Dataset

Add scenarios in `generate_synthetic_data.py`:

1. Create a generator function `generate_my_scenario()` yielding `SyntheticEndpoint` instances.
2. Add it to `generate_all()`.

Ensure endpoints have `total_requests >= min_requests` so they are eligible for anomaly decision.

## Real Data Evaluation

You can run the detector on real or public traffic data in CSV form.

### CSV format

Headers: `timestamp`, `key`, `size_bytes`, `label` (optional)

- **timestamp**: Unix epoch (float) or ISO datetime
- **key**: Endpoint identifier (e.g. `dest_ip:port`, URL path)
- **size_bytes**: Response/flow size in bytes
- **label**: `0`/`normal`/`benign` or `1`/`anomaly`/`attack` — if missing, metrics are skipped

### Quick test with sample data

```bash
cd "C:\Raj Files\api_cache_framework"
.\.venv\Scripts\Activate.ps1
python scripts/evaluate_real.py data/sample_real_traffic.csv
```

### API-like traffic (realistic synthetic)

A second real-world-like dataset mimics API/CDN traffic with varied patterns:

- **Normal**: stable endpoints (`/api/products`, `/api/users`, etc.) with consistent payload sizes
- **frequent_small**: health checks, probes (`/health`, `/ping`, `/metrics`)
- **bursty**: scan/bot traffic (`/api/scan`, `/api/probe`)
- **erratic_size**: variable response sizes (probing)

Generate and evaluate:

```bash
python scripts/generate_api_like_traffic.py -o data/api_like_traffic.csv
python scripts/evaluate_real.py data/api_like_traffic.csv
python scripts/evaluate_real.py data/api_like_traffic.csv --json
```

Result: 16 endpoints, 100% precision/recall/F1 on labeled data. Dataset included in `data/`.

### Using CICIDS2017 (Real-World Data)

**Automated download and convert:**

```bash
python scripts/download_cicids.py --limit 20000
# Or: python scripts/download_cicids.py --kaggle  # if you have Kaggle CLI
# Or: python scripts/download_cicids.py --skip-download  # if you have the zip
```

**Manual steps:**
1. Download CICIDS2017 from [UNB CIC](https://www.unb.ca/cic/datasets/ids-2017.html) or [Kaggle](https://www.kaggle.com/datasets/ernie55ernie/cleaned-cicids2017).
2. Save `MachineLearningCSV.zip` to `data/`.
3. Run `python scripts/download_cicids.py --skip-download --limit 20000`.
4. Or extract a CSV and convert directly:

   ```bash
   python scripts/convert_cicids.py path/to/cicids.csv -o data/cicids_converted.csv
   python scripts/convert_cicids.py path/to/cicids.csv -o data/cicids_sample.csv --limit 50000
   ```

4. Run evaluation:

   ```bash
   python scripts/evaluate_real.py data/cicids_converted.csv
   python scripts/evaluate_real.py data/cicids_converted.csv --json
   ```

### Files

- `scripts/load_real_data.py` — Generic CSV loader; computes per-key (λ, σ_λ, mean_size, σ_s).
- `scripts/convert_cicids.py` — Converts CICIDS2017 CSV to our format.
- `scripts/evaluate_real.py` — Evaluates on real CSV; outputs metrics + CAS per endpoint.
- `scripts/generate_api_like_traffic.py` — Generates API-like traffic CSV (normal + anomaly patterns).
- `data/sample_real_traffic.csv` — Small sample for immediate testing.
- `data/api_like_traffic.csv` — Realistic API-like traffic (~1.7k rows, 16 endpoints).

---

## Reporting

For papers or reports, include:

1. **Method**: CAS formula, decision rule (CAS &lt; threshold), parameter values.
2. **Data**: Synthetic and/or real (CICIDS, custom logs); describe format and labels.
3. **Metrics**: Overall and per-scenario Precision, Recall, F1, Accuracy.
4. **Limitations**: Synthetic vs real; dataset size; applicability to your deployment.
