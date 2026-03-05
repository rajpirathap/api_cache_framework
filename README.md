# CAS-based Anomaly Detection (Django)

A Django framework for **anomaly detection** using the **Cache Admission Score (CAS)** formula. It records request frequency, traffic stability, response size, and uses the same formula to flag suspicious patterns (e.g. frequent + small, bursty traffic).

## Cache Admission Score (CAS) — used for anomaly scoring

### Formula

**Raw score (asymmetric variant with p, k, q):**
```
CAS = (λ / (1 + σ_λ)) × g(s̄) × (1 / (1 + (σ_s/S₁)^p)) − α × λ^k × (S₀ / (s̄ + S₀))^q
```
Default: p=2, k=1.2, q=1.5. With p=k=q=1, reduces to the original linear form.

**Size benefit:**
```
g(s̄) = s̄ / (s̄ + S₀)
```

**Final score:**
```
final_CAS = max(CAS, 0)
```

### Notation

| Symbol | Meaning |
|--------|---------|
| **λ** | Mean request count per time window (frequency) |
| **σ_λ** | Std dev of request count per window (traffic stability) |
| **s̄** | Mean response size (bytes) |
| **σ_s** | Std dev of response size (bytes) |
| **S₀** | Size scale for mean (default 10 KB) |
| **S₁** | Size scale for size std dev (default 5 KB) |
| **α** | Penalty weight for "frequent but small" (default 0.2) |
| **g(s̄)** | Size benefit factor (0 → 1 as size grows) |

## Install

```bash
cd "C:\Raj Files\api_cache_framework"
pip install -r requirements.txt
```

## Use in your Django project

1. **Add the package to the path** (or install it in your env).

2. **Add the anomaly middleware** in `settings.py`:

   ```python
   MIDDLEWARE = [
       # ...
       "api_cache_framework.anomaly_middleware.AnomalyDetectionMiddleware",
   ]
   ```

3. **Config** in `settings.py`:

   ```python
   API_ANOMALY_FRAMEWORK = {
       "s0_bytes": 10 * 1024,
       "s1_bytes": 5 * 1024,
       "alpha": 0.1,
       "window_minutes": 0.05,
       "max_timestamps_per_key": 500,
       "max_sizes_per_key": 200,
       "recency_decay_per_window": 0.0,
   }
   ```

The middleware records GET response sizes per path. CAS is computed from λ, σ_λ, s̄, σ_s. Anomaly rules flag patterns such as "frequent_small", "bursty", "low_cas".

## Run the demo

```bash
cd "C:\Raj Files\api_cache_framework"
.\.venv\Scripts\Activate.ps1
cd demo
python manage.py runserver
```

- `GET /api/items/` — larger payload
- `GET /api/small/` — small payload (often flagged as anomaly)
- `GET /api/health/` — tiny response (often flagged as anomaly)
- `GET /anomaly/` — **Anomaly dashboard** with CAS breakdown and anomaly flags

## Evaluation (for research reporting)

### Synthetic data

```bash
python scripts/evaluate_synthetic.py
python scripts/evaluate_synthetic.py --json
```

### Real data (CSV)

```bash
# Sample data (included)
python scripts/evaluate_real.py data/sample_real_traffic.csv

# CICIDS2017: convert first, then evaluate
python scripts/convert_cicids.py path/to/cicids.csv -o data/cicids.csv
python scripts/evaluate_real.py data/cicids.csv
```

See [EVALUATION.md](EVALUATION.md) for methodology, scenarios, CICIDS conversion, and reproducibility notes.

## Layout

```
api_cache_framework/
  api_cache_framework/
    anomaly.py           # check_anomaly(), key_to_display_path()
    anomaly_middleware.py # AnomalyDetectionMiddleware (stats only)
    anomaly_stats.py     # AnomalyStatsService, get_anomaly_dashboard_data()
    score.py             # CAS: cache_score(), cache_score_breakdown()
    stats.py             # RequestStats, StatsCollector
    defaults.py
  demo/
  scripts/
    generate_synthetic_data.py   # Synthetic data generator
    evaluate_synthetic.py        # Synthetic evaluation (precision/recall/F1)
    load_real_data.py            # CSV loader for real traffic
    convert_cicids.py            # CICIDS2017 → simple CSV converter
    evaluate_real.py             # Real data evaluation
  data/
    sample_real_traffic.csv      # Sample CSV for quick testing
  requirements.txt
  README.md
  EVALUATION.md                  # Evaluation methodology
```

## Notes

- **No cache**: This setup records stats only; no caching.
- Stats are **sliding window** (last N timestamps/sizes per key).
- CAS is recomputed when fetching dashboard data; low CAS + patterns (frequent_small, bursty) trigger anomaly flags.
