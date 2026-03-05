"""
Django middleware: records request/response stats and caches GET responses
when the Cache Admission Score (CAS) says to cache. Uses a single cache key from path + query string.
"""
import hashlib
import json
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse

from .defaults import (
    API_CACHE_ALPHA,
    API_CACHE_LAMBDA_MIN,
    API_CACHE_P,
    API_CACHE_K,
    API_CACHE_Q,
    API_CACHE_DEFAULT_TTL_MINUTES,
    API_CACHE_MAX_SIZES_PER_KEY,
    API_CACHE_MAX_TIMESTAMPS_PER_KEY,
    API_CACHE_MIN_REQUESTS,
    API_CACHE_RECENCY_DECAY_PER_WINDOW,
    API_CACHE_S0_BYTES,
    API_CACHE_S1_BYTES,
    API_CACHE_SCORE_THRESHOLD,
    API_CACHE_WINDOW_MINUTES,
)
from .store import FormulaCacheStore
from .stats import StatsCollector


def _build_cache_key(request: HttpRequest) -> str:
    """Stable key from path + sorted query string (excluding common bypass params)."""
    path = request.path
    params = [(k, v) for k, v in request.GET.items() if k not in ("_", "refresh")]
    param_str = json.dumps(sorted(params), sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:16]
    return f"api:{path}:{param_hash}"


# Module-level singleton store (lazy-initialized with config)
_store: Optional[FormulaCacheStore] = None
_config: Optional[dict] = None


def _get_store() -> FormulaCacheStore:
    global _store, _config
    if _store is None:
        # Use default config when no request (e.g. management command)
        from django.conf import settings
        cfg = getattr(settings, "API_CACHE_FRAMEWORK", {})
        window_min = cfg.get("window_minutes", API_CACHE_WINDOW_MINUTES)
        _config = {
            "s0": cfg.get("s0_bytes", API_CACHE_S0_BYTES),
            "s1": cfg.get("s1_bytes", API_CACHE_S1_BYTES),
            "alpha": cfg.get("alpha", API_CACHE_ALPHA),
            "p": cfg.get("p", API_CACHE_P),
            "k": cfg.get("k", API_CACHE_K),
            "q": cfg.get("q", API_CACHE_Q),
            "lambda_min": cfg.get("lambda_min", API_CACHE_LAMBDA_MIN),
            "threshold": cfg.get("score_threshold", API_CACHE_SCORE_THRESHOLD),
            "window_seconds": window_min * 60.0,
            "num_windows": max(5, 60 // max(1, window_min)),
            "default_ttl_minutes": cfg.get("default_ttl_minutes", API_CACHE_DEFAULT_TTL_MINUTES),
            "max_timestamps": cfg.get("max_timestamps_per_key", API_CACHE_MAX_TIMESTAMPS_PER_KEY),
            "max_sizes": cfg.get("max_sizes_per_key", API_CACHE_MAX_SIZES_PER_KEY),
            "min_requests": cfg.get("min_requests", API_CACHE_MIN_REQUESTS),
            "recency_decay_per_window": cfg.get(
                "recency_decay_per_window", API_CACHE_RECENCY_DECAY_PER_WINDOW
            ),
        }
        stats = StatsCollector(
            max_timestamps_per_key=_config["max_timestamps"],
            max_sizes_per_key=_config["max_sizes"],
        )
        _store = FormulaCacheStore(
            stats=stats,
            window_seconds=_config["window_seconds"],
            num_windows=_config["num_windows"],
            s0=float(_config["s0"]),
            s1=float(_config["s1"]),
            alpha=float(_config["alpha"]),
            p=float(_config["p"]),
            k=float(_config["k"]),
            q=float(_config["q"]),
            lambda_min=float(_config["lambda_min"]),
            threshold=float(_config["threshold"]),
            default_ttl_seconds=_config["default_ttl_minutes"] * 60.0,
            min_requests=int(_config["min_requests"]),
            recency_decay_per_window=float(_config["recency_decay_per_window"]),
        )
    return _store


class FormulaCacheMiddleware:
    """
    Middleware that:
    1. On GET: tries to return cached response if key exists (admitted by CAS).
    2. After response: records path+params and response size in stats; if CAS says cache, stores response.
    Only caches 200 JSON-like responses. Skip by adding ?refresh=1 if needed.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            return self.get_response(request)

        key = _build_cache_key(request)
        store = _get_store()

        if request.GET.get("refresh"):
            store.delete(key)

        cached = store.get(key)
        if cached is not None:
            return JsonResponse(cached)

        response = self.get_response(request)
        if response.status_code != 200:
            return response

        try:
            content = response.content
            size = len(content)
            data = json.loads(content)
        except (TypeError, ValueError):
            return response

        store.record_and_maybe_set(key, data, response_size_bytes=size)
        return response
