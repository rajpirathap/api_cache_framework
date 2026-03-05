"""
CAS-based anomaly detection for cybersecurity demonstration.
Decision: ANOMALY if CAS < threshold (single metric).
Reasons: derived from raw stats to explain why CAS is low.
"""
from typing import List, Tuple


def _get_anomaly_reasons(
    lambda_: float,
    sigma_lambda: float,
    mean_size: float,
    sigma_size: float,
) -> List[str]:
    """Derive reasons from raw stats to explain why CAS is low. Used for explainability only."""
    reasons: List[str] = []

    if lambda_ > 3 and mean_size < 1024:
        reasons.append("frequent_small: high rate + tiny responses")
    if lambda_ > 2 and sigma_lambda > 3.0 * lambda_:
        reasons.append("bursty: traffic very unstable")
    if mean_size > 100 and sigma_size > 3.0 * mean_size:
        reasons.append("erratic_size: response sizes highly variable")

    if not reasons:
        reasons.append("low_cas: score suppressed by formula components")

    return reasons


def check_anomaly(
    lambda_: float,
    sigma_lambda: float,
    mean_size: float,
    sigma_size: float,
    cas: float,
    total_requests: int,
    *,
    cas_threshold: float = 0.05,
    min_requests: int = 15,
) -> Tuple[bool, List[str]]:
    """
    Return (is_anomaly, list of reasons).

    Decision: ANOMALY if total_requests >= min_requests and CAS < cas_threshold.
    Reasons: derived from raw stats when anomalous (for explainability).
    """
    is_anomaly = total_requests >= min_requests and cas < cas_threshold

    if is_anomaly:
        reasons = _get_anomaly_reasons(lambda_, sigma_lambda, mean_size, sigma_size)
    else:
        reasons = []

    return is_anomaly, reasons


def key_to_display_path(key: str) -> str:
    """Extract display path from key (e.g. api:/api/items/:hash or anomaly:/api/items/:hash -> /api/items/)."""
    for prefix in ("api:", "anomaly:"):
        if key.startswith(prefix) and ":" in key[len(prefix):]:
            return key.split(":", 2)[1]
    return key
