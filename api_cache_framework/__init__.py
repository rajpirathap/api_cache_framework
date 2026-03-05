"""
Cache Admission Score (CAS) API response cache for Django.
Uses λ, σ_λ, mean/size σ_s and a penalty for frequent+low-size to decide whether to admit a URL into cache.
"""
from .defaults import (
    API_CACHE_ALPHA,
    API_CACHE_DEFAULT_TTL_MINUTES,
    API_CACHE_S0_BYTES,
    API_CACHE_S1_BYTES,
    API_CACHE_SCORE_THRESHOLD,
    API_CACHE_WINDOW_MINUTES,
)
from .score import cache_score, compute_lambda_sigma, should_cache
from .stats import RequestStats, StatsCollector
from .store import FormulaCacheStore

__all__ = [
    "FormulaCacheMiddleware",
    "FormulaCacheStore",
    "RequestStats",
    "StatsCollector",
    "cache_score",
    "compute_lambda_sigma",
    "should_cache",
    "API_CACHE_ALPHA",
    "API_CACHE_DEFAULT_TTL_MINUTES",
    "API_CACHE_S0_BYTES",
    "API_CACHE_S1_BYTES",
    "API_CACHE_SCORE_THRESHOLD",
    "API_CACHE_WINDOW_MINUTES",
]

# Import after __all__ so middleware is available
from .middleware import FormulaCacheMiddleware  # noqa: E402
