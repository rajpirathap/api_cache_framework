"""
In-memory response cache with TTL. Cache is only used when the
Cache Admission Score (CAS) says "should cache" for that key; stats are updated on every request.
"""
import time
from threading import Lock
from typing import Any, Optional

from .anomaly import check_anomaly, key_to_display_path
from .score import cache_score, cache_score_breakdown, compute_lambda_sigma, should_cache as score_should_cache
from .stats import StatsCollector


class FormulaCacheStore:
    """
    In-memory cache for API responses. A key is stored only when
    should_cache(key) is True (Cache Admission Score, CAS). Stats are recorded
    on every request to drive the CAS.
    """

    def __init__(
        self,
        stats: StatsCollector,
        window_seconds: float,
        num_windows: int,
        s0: float,
        s1: float,
        alpha: float,
        threshold: float,
        default_ttl_seconds: float,
        min_requests: int = 0,
        recency_decay_per_window: float = 0.0,
        p: float = 1.0,
        k: float = 1.0,
        q: float = 1.0,
        lambda_min: float = 1.0,
    ):
        self._stats = stats
        self._window_seconds = window_seconds
        self._num_windows = num_windows
        self._s0 = s0
        self._s1 = s1
        self._alpha = alpha
        self._p = p
        self._k = k
        self._q = q
        self._lambda_min = lambda_min
        self._threshold = threshold
        self._default_ttl = default_ttl_seconds
        self._min_requests = min_requests
        self._recency_decay = recency_decay_per_window
        self._cache: dict[str, tuple[Any, float]] = {}  # key -> (value, expiry_time)
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        with self._lock:
            self._cache[key] = (value, time.time() + ttl)

    def should_cache_for_key(self, key: str) -> bool:
        counts, mean_size, sigma_size = self._stats.get_stats_for_score(
            key,
            self._window_seconds,
            self._num_windows,
            self._recency_decay,
        )
        return score_should_cache(
            counts_per_window=counts,
            mean_size=mean_size,
            sigma_size=sigma_size,
            s0=self._s0,
            s1=self._s1,
            alpha=self._alpha,
            threshold=self._threshold,
            min_requests=self._min_requests,
            p=self._p,
            k=self._k,
            q=self._q,
            lambda_min=self._lambda_min,
        )

    def get_score_for_key(self, key: str) -> float:
        """Return current Cache Admission Score (CAS) for key (for debugging/admin)."""
        counts, mean_size, sigma_size = self._stats.get_stats_for_score(
            key,
            self._window_seconds,
            self._num_windows,
            self._recency_decay,
        )
        lambda_, sigma_lambda = compute_lambda_sigma(counts)
        return cache_score(
            lambda_=lambda_,
            sigma_lambda=sigma_lambda,
            mean_size=mean_size,
            sigma_size=sigma_size,
            s0=self._s0,
            s1=self._s1,
            alpha=self._alpha,
            p=self._p,
            k=self._k,
            q=self._q,
            lambda_min=self._lambda_min,
        )

    def record_and_maybe_set(
        self,
        key: str,
        response_body: Any,
        response_size_bytes: int,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """
        Record this request in stats (always). If should_cache(key) is True,
        also store response in cache.
        """
        self._stats.record(key, response_size_bytes)
        if self.should_cache_for_key(key):
            self.set(key, response_body, ttl_seconds=ttl_seconds)

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def cleanup_expired(self) -> int:
        now = time.time()
        with self._lock:
            to_remove = [k for k, (_, exp) in self._cache.items() if now > exp]
            for k in to_remove:
                del self._cache[k]
        return len(to_remove)

    def get_anomaly_dashboard_data(self) -> list[dict[str, Any]]:
        """Return per-key stats + anomaly flags for dashboard UI."""
        rows: list[dict[str, Any]] = []
        for key in self._stats.get_all_keys():
            counts, mean_size, sigma_size = self._stats.get_stats_for_score(
                key,
                self._window_seconds,
                self._num_windows,
                self._recency_decay,
            )
            lambda_, sigma_lambda = compute_lambda_sigma(counts)
            cas = cache_score(
                lambda_=lambda_,
                sigma_lambda=sigma_lambda,
                mean_size=mean_size,
                sigma_size=sigma_size,
                s0=self._s0,
                s1=self._s1,
                alpha=self._alpha,
                p=self._p,
                k=self._k,
                q=self._q,
                lambda_min=self._lambda_min,
            )
            breakdown = cache_score_breakdown(
                lambda_, sigma_lambda, mean_size, sigma_size,
                self._s0, self._s1, self._alpha, self._p, self._k, self._q,
                self._lambda_min,
            )
            total = int(sum(counts)) if counts else 0
            is_anomaly, reasons = check_anomaly(
                lambda_, sigma_lambda, mean_size, sigma_size, cas, total
            )
            rows.append({
                "key": key,
                "path": key_to_display_path(key),
                "lambda": round(lambda_, 2),
                "sigma_lambda": round(sigma_lambda, 2),
                "mean_size": round(mean_size, 1),
                "sigma_size": round(sigma_size, 1),
                "cas": round(cas, 3),
                "total_requests": total,
                "anomaly": is_anomaly,
                "reasons": reasons,
                "breakdown": breakdown,
            })
        return rows
