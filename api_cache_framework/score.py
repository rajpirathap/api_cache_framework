"""
Cache Admission Score (CAS): A Stability-Aware Admission Policy.

Prioritizes flows that are:
1. Frequent (high λ)
2. Stable (low σ_λ) - signal-to-noise ratio
3. Bandwidth-efficient (larger payloads, up to saturation)

Penalizes "cache pollution" patterns (high frequency + tiny size).
Reduces CAS for low-volume / rare flows (anomaly indicator).
Optimizes for Byte Hit Rate and Traffic Stability rather than simple Object Hit Rate.
"""
import math
from typing import List, Tuple, Union


def compute_lambda_sigma(
    counts_per_window: List[Union[int, float]],
) -> Tuple[float, float]:
    """
    From list of request counts per time window, return (λ, σ_λ).
    λ = mean count, σ_λ = std dev of counts. (0.0, 0.0) if no data.
    """
    if not counts_per_window:
        return 0.0, 0.0
    n = len(counts_per_window)
    mean = sum(counts_per_window) / n
    variance = sum((x - mean) ** 2 for x in counts_per_window) / n
    std = math.sqrt(variance)
    return mean, std


def cache_score(
    lambda_: float,
    sigma_lambda: float,
    mean_size: float,
    sigma_size: float,
    s0: float,
    s1: float,
    alpha: float,
    p: float = 1.0,
    k: float = 1.0,
    q: float = 1.0,
    lambda_min: float = 1.0,
) -> float:
    """
    Compute Cache Admission Score (CAS).
    Returns max(raw_CAS, 0).
    Asymmetric variant: use p>1, k>1, q>1 for stronger anomaly rejection.
    Volume term: low λ (rare flows) reduces CAS via λ/(λ + λ_min).
    """
    b = cache_score_breakdown(
        lambda_, sigma_lambda, mean_size, sigma_size, s0, s1, alpha, p, k, q, lambda_min
    )
    return b["final"]


def cache_score_breakdown(
    lambda_: float,
    sigma_lambda: float,
    mean_size: float,
    sigma_size: float,
    s0: float,
    s1: float,
    alpha: float,
    p: float = 1.0,
    k: float = 1.0,
    q: float = 1.0,
    lambda_min: float = 1.0,
) -> dict:
    """
    Return formula breakdown: term1, size_benefit, term3, volume_term, penalty, raw, final.
    Asymmetric: term3 = 1/(1+(σ_s/S₁)^p), penalty = α·λ^k·(S₀/(s̄+S₀))^q.
    Volume: volume_term = λ/(λ+λ_min) so low request count reduces CAS.
    """
    if lambda_ <= 0:
        return {
            "term1": 0.0,
            "size_benefit": 0.0,
            "term3": 0.0,
            "volume_term": 0.0,
            "penalty": 0.0,
            "positive": 0.0,
            "raw": 0.0,
            "final": 0.0,
        }
    mean_size = max(mean_size, 1.0)
    term1 = lambda_ / (1.0 + sigma_lambda)
    size_benefit = mean_size / (mean_size + s0)
    size_ratio = s0 / (mean_size + s0)
    term3 = 1.0 / (1.0 + (sigma_size / s1) ** p)
    # Low-volume / rare flows: reduce CAS when λ is below λ_min
    volume_term = lambda_ / (lambda_ + lambda_min)
    penalty = alpha * (lambda_ ** k) * (size_ratio ** q)
    positive = term1 * size_benefit * term3 * volume_term
    raw = positive - penalty
    final = max(raw, 0.0)
    return {
        "term1": round(term1, 4),
        "size_benefit": round(size_benefit, 4),
        "term3": round(term3, 4),
        "volume_term": round(volume_term, 4),
        "penalty": round(penalty, 4),
        "positive": round(positive, 4),
        "raw": round(raw, 4),
        "final": round(final, 4),
    }


def should_cache(
    counts_per_window: List[Union[int, float]],
    mean_size: float,
    sigma_size: float,
    s0: float,
    s1: float,
    alpha: float,
    threshold: float,
    min_requests: int = 0,
    p: float = 1.0,
    k: float = 1.0,
    q: float = 1.0,
    lambda_min: float = 1.0,
) -> bool:
    """
    Decide whether to cache based on Cache Admission Score (CAS).
    Returns True if CAS >= threshold.
    Requires at least min_requests total requests in the window (cold-start guard).
    """
    if min_requests > 0 and sum(counts_per_window) < min_requests:
        return False
    lambda_, sigma_lambda = compute_lambda_sigma(counts_per_window)
    score = cache_score(
        lambda_=lambda_,
        sigma_lambda=sigma_lambda,
        mean_size=mean_size,
        sigma_size=sigma_size,
        s0=s0,
        s1=s1,
        alpha=alpha,
        p=p,
        k=k,
        q=q,
        lambda_min=lambda_min,
    )
    return score >= threshold
