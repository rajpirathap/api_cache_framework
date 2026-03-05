"""
Stability-Aware HTTP Priority Queue.

Queues incoming requests based on the Cache Admission Score (CAS), prioritizing
stable, meaningful traffic flows over bursty or erratic "cache pollution" traffic.
"""
import hashlib
import json
import queue
import threading
from itertools import count
from typing import Any, Callable, Optional

from django.http import HttpRequest, HttpResponse

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
    API_QUEUE_DEFAULT_PRIORITY,
    API_QUEUE_MAX_SIZE,
    API_QUEUE_NUM_WORKERS,
    API_QUEUE_REJECT_WHEN_FULL,
)
from .score import cache_score, compute_lambda_sigma
from .stats import StatsCollector


def _build_queue_key(request: HttpRequest) -> str:
    """Stable key from path + sorted query string (same idea as cache key)."""
    path = request.path
    params = [(k, v) for k, v in request.GET.items() if k not in ("_", "refresh")]
    param_str = json.dumps(sorted(params), sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:16]
    return f"queue:{path}:{param_hash}"


# Module-level singleton: queue, stats, config, worker(s). Lazy-initialized.
_queue_manager: Optional["_QueueManager"] = None
_queue_lock = threading.Lock()


class _QueueManager:
    """Holds priority queue, stats, CAS config, and worker thread(s)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        from django.conf import settings
        cfg = getattr(settings, "API_CACHE_FRAMEWORK", {})
        qcfg = getattr(settings, "API_QUEUE_FRAMEWORK", {})
        self._window_min = qcfg.get("window_minutes", cfg.get("window_minutes", API_CACHE_WINDOW_MINUTES))
        self._window_seconds = self._window_min * 60.0
        self._num_windows = max(5, 60 // max(1, self._window_min))
        self._s0 = float(qcfg.get("s0_bytes", cfg.get("s0_bytes", API_CACHE_S0_BYTES)))
        self._s1 = float(qcfg.get("s1_bytes", cfg.get("s1_bytes", API_CACHE_S1_BYTES)))
        self._alpha = float(qcfg.get("alpha", cfg.get("alpha", API_CACHE_ALPHA)))
        self._p = float(qcfg.get("p", cfg.get("p", API_CACHE_P)))
        self._k = float(qcfg.get("k", cfg.get("k", API_CACHE_K)))
        self._q = float(qcfg.get("q", cfg.get("q", API_CACHE_Q)))
        self._lambda_min = float(qcfg.get("lambda_min", cfg.get("lambda_min", API_CACHE_LAMBDA_MIN)))
        self._recency_decay = float(
            qcfg.get("recency_decay_per_window", cfg.get("recency_decay_per_window", API_CACHE_RECENCY_DECAY_PER_WINDOW))
        )
        self._max_queue_size = int(qcfg.get("max_size", API_QUEUE_MAX_SIZE))
        self._reject_when_full = bool(qcfg.get("reject_when_full", API_QUEUE_REJECT_WHEN_FULL))
        self._default_priority = float(qcfg.get("default_priority", API_QUEUE_DEFAULT_PRIORITY))
        self._num_workers = max(1, int(qcfg.get("num_workers", API_QUEUE_NUM_WORKERS)))

        self._stats = StatsCollector(
            max_timestamps_per_key=API_CACHE_MAX_TIMESTAMPS_PER_KEY,
            max_sizes_per_key=API_CACHE_MAX_SIZES_PER_KEY,
        )
        # PriorityQueue: min-heap; we use (-score, seq) so higher score = served first.
        self._pq: queue.PriorityQueue = queue.PriorityQueue(maxsize=self._max_queue_size)
        self._seq = count(0)
        self._workers: list[threading.Thread] = []
        self._start_workers()

    def _start_workers(self) -> None:
        for _ in range(self._num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self._workers.append(t)

    def _worker_loop(self) -> None:
        while True:
            try:
                priority, seq, (request, key, response_holder) = self._pq.get()
            except Exception:
                break
            response = None
            try:
                response = self.get_response(request)
                size = len(response.content) if response else 0
                self._stats.record(key, size)
            except Exception as exc:
                response = HttpResponse(
                    status=500,
                    content=str(exc).encode("utf-8") if exc else b"Internal Server Error",
                    content_type="text/plain",
                )
            finally:
                response_holder["response"] = response
                response_holder["event"].set()

    def priority_for_key(self, key: str) -> float:
        """Compute CAS score for key (from historical stats). Used as priority."""
        counts, mean_size, sigma_size = self._stats.get_stats_for_score(
            key,
            self._window_seconds,
            self._num_windows,
            self._recency_decay,
        )
        if not counts and mean_size <= 0:
            return self._default_priority
        lambda_, sigma_lambda = compute_lambda_sigma(counts)
        score = cache_score(
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
        return max(score, 0.0)

    def enqueue(self, request: HttpRequest, key: str) -> Optional[dict]:
        """
        Enqueue request. Returns a response_holder dict with 'response' and 'event'.
        If queue is full and reject_when_full, returns None (caller should return 503).
        """
        priority = self.priority_for_key(key)
        response_holder: dict[str, Any] = {"response": None, "event": threading.Event()}
        item = (-priority, next(self._seq), (request, key, response_holder))
        try:
            self._pq.put(item, block=not self._reject_when_full, timeout=0.1)
        except queue.Full:
            return None
        return response_holder


def _get_queue_manager(get_response: Callable[[HttpRequest], HttpResponse]) -> _QueueManager:
    global _queue_manager
    with _queue_lock:
        if _queue_manager is None:
            from django.conf import settings
            cfg = getattr(settings, "API_CACHE_FRAMEWORK", {})
            # Allow queue overrides in same config or a dedicated key
            queue_cfg = getattr(settings, "API_QUEUE_FRAMEWORK", cfg)
            # We already use module-level defaults; could override from queue_cfg here.
            _queue_manager = _QueueManager(get_response)
        return _queue_manager


class FormulaRequestQueueMiddleware:
    """
    Middleware that queues GET requests and serves them in CAS priority order.
    Higher-scored URLs (frequent, stable, larger responses) are processed first.
    After each response, stats are updated so priorities adapt. Other methods
    are passed through without queuing.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method != "GET":
            return self.get_response(request)

        manager = _get_queue_manager(self.get_response)
        key = _build_queue_key(request)
        response_holder = manager.enqueue(request, key)
        if response_holder is None:
            return HttpResponse(
                status=503,
                content=b"Service Unavailable (queue full)",
                content_type="text/plain",
            )
        response_holder["event"].wait()
        return response_holder["response"]
