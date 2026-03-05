"""
CAS-based anomaly detection: stats collection and dashboard data.
Uses the same CAS formula for anomaly scoring (no cache).
"""
from typing import Any, Optional

from .anomaly import check_anomaly, key_to_display_path
from .defaults import (
    API_CACHE_ALPHA,
    API_CACHE_LAMBDA_MIN,
    API_CACHE_P,
    API_CACHE_K,
    API_CACHE_Q,
    API_CACHE_MAX_SIZES_PER_KEY,
    API_CACHE_MAX_TIMESTAMPS_PER_KEY,
    API_CACHE_RECENCY_DECAY_PER_WINDOW,
    API_CACHE_S0_BYTES,
    API_CACHE_S1_BYTES,
    API_CACHE_WINDOW_MINUTES,
)
from .score import cache_score, cache_score_breakdown, compute_lambda_sigma
from .stats import StatsCollector

_anomaly_service: Optional["AnomalyStatsService"] = None


def _get_anomaly_service() -> "AnomalyStatsService":
    global _anomaly_service
    if _anomaly_service is None:
        from django.conf import settings
        cfg = getattr(settings, "API_ANOMALY_FRAMEWORK", getattr(settings, "API_CACHE_FRAMEWORK", {}))
        window_min = cfg.get("window_minutes", API_CACHE_WINDOW_MINUTES)
        w_min = max(0.01, float(window_min))
        _anomaly_service = AnomalyStatsService(
            stats=StatsCollector(
                max_timestamps_per_key=cfg.get("max_timestamps_per_key", API_CACHE_MAX_TIMESTAMPS_PER_KEY),
                max_sizes_per_key=cfg.get("max_sizes_per_key", API_CACHE_MAX_SIZES_PER_KEY),
            ),
            window_seconds=w_min * 60.0,
            num_windows=max(5, int(60 / max(0.01, w_min))),
            s0=float(cfg.get("s0_bytes", API_CACHE_S0_BYTES)),
            s1=float(cfg.get("s1_bytes", API_CACHE_S1_BYTES)),
            alpha=float(cfg.get("alpha", API_CACHE_ALPHA)),
            p=float(cfg.get("p", API_CACHE_P)),
            k=float(cfg.get("k", API_CACHE_K)),
            q=float(cfg.get("q", API_CACHE_Q)),
            lambda_min=float(cfg.get("lambda_min", API_CACHE_LAMBDA_MIN)),
            recency_decay=float(cfg.get("recency_decay_per_window", API_CACHE_RECENCY_DECAY_PER_WINDOW)),
        )
    return _anomaly_service


class AnomalyStatsService:
    """
    Collects request stats and provides CAS-based anomaly dashboard data.
    No cache; same CAS formula used for anomaly scoring.
    """

    def __init__(
        self,
        stats: StatsCollector,
        window_seconds: float,
        num_windows: int,
        s0: float,
        s1: float,
        alpha: float,
        recency_decay: float = 0.0,
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
        self._recency_decay = recency_decay

    def record(self, key: str, response_size_bytes: int) -> None:
        """Record a request for anomaly stats."""
        self._stats.record(key, response_size_bytes)

    def get_anomaly_dashboard_data(
        self,
        overrides: Optional[dict[str, float]] = None,
    ) -> list[dict[str, Any]]:
        """
        Return per-key stats + CAS + anomaly flags for dashboard.
        overrides: optional {s0, s1, alpha, window_minutes} to tune formula (e.g. from UI).
        """
        ov = overrides or {}
        s0 = float(ov.get("s0", self._s0))
        s1 = float(ov.get("s1", self._s1))
        alpha = float(ov.get("alpha", self._alpha))
        p = float(ov.get("p", self._p))
        k = float(ov.get("k", self._k))
        q = float(ov.get("q", self._q))
        lambda_min = float(ov.get("lambda_min", self._lambda_min))
        w_min = float(ov.get("window_minutes", self._window_seconds / 60.0))
        w_min = max(0.01, w_min)
        window_seconds = w_min * 60.0
        num_windows = max(5, int(60 / max(0.01, w_min)))
        rows: list[dict[str, Any]] = []
        for key in self._stats.get_all_keys():
            counts, mean_size, sigma_size = self._stats.get_stats_for_score(
                key,
                window_seconds,
                num_windows,
                self._recency_decay,
            )
            lambda_, sigma_lambda = compute_lambda_sigma(counts)
            cas = cache_score(
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
            breakdown = cache_score_breakdown(
                lambda_, sigma_lambda, mean_size, sigma_size,
                s0, s1, alpha, p, k, q, lambda_min,
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
