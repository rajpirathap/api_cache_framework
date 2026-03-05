"""
Per-URL stats for the Cache Admission Score (CAS): request counts per time window and response sizes.
Thread-safe, in-memory, sliding-window.
"""
import time
from collections import deque
from threading import Lock
from typing import Deque, List, Tuple


class RequestStats:
    """
    Tracks for a single cache key (e.g. URL + params):
    - Timestamps of recent requests (for λ, σ_λ in fixed time windows).
    - Recent response sizes (for s̄, σ_s).
    """

    def __init__(self, max_timestamps: int = 500, max_sizes: int = 200):
        self._timestamps: Deque[float] = deque(maxlen=max_timestamps)
        self._sizes: Deque[int] = deque(maxlen=max_sizes)
        self._lock = Lock()

    def record(self, response_size_bytes: int) -> None:
        with self._lock:
            self._timestamps.append(time.time())
            self._sizes.append(response_size_bytes)

    def get_request_counts_per_window(
        self,
        window_seconds: float,
        num_windows: int,
        recency_decay_per_window: float = 0.0,
    ) -> List[float]:
        """
        Split the last (num_windows * window_seconds) into windows and return
        request count per window. Used to compute λ and σ_λ.
        If recency_decay_per_window > 0 (e.g. 0.9), recent windows are weighted
        more: window i gets weight decay^(num_windows-1-i). Returns effective
        counts (may be float when decay is used).
        """
        with self._lock:
            if not self._timestamps:
                return []
            now = time.time()
            window_start = now - num_windows * window_seconds
            timestamps = [t for t in self._timestamps if t >= window_start]
        if not timestamps:
            return []

        counts: List[float] = []
        for i in range(num_windows):
            w_start = window_start + i * window_seconds
            w_end = w_start + window_seconds
            count = sum(1 for t in timestamps if w_start <= t < w_end)
            if recency_decay_per_window > 0:
                weight = recency_decay_per_window ** (num_windows - 1 - i)
                count = count * weight
            counts.append(float(count))
        return counts

    def get_size_stats(self) -> Tuple[float, float]:
        """Return (mean size, std dev of size). (0.0, 0.0) if no data."""
        with self._lock:
            sizes = list(self._sizes)
        if not sizes:
            return 0.0, 0.0
        n = len(sizes)
        mean = sum(sizes) / n
        variance = sum((x - mean) ** 2 for x in sizes) / n
        std = variance ** 0.5
        return mean, std


class StatsCollector:
    """Maps cache key -> RequestStats. Thread-safe."""

    def __init__(
        self,
        max_timestamps_per_key: int = 500,
        max_sizes_per_key: int = 200,
    ):
        self._max_ts = max_timestamps_per_key
        self._max_sizes = max_sizes_per_key
        self._key_to_stats: dict[str, RequestStats] = {}
        self._lock = Lock()

    def record(self, key: str, response_size_bytes: int) -> None:
        with self._lock:
            if key not in self._key_to_stats:
                self._key_to_stats[key] = RequestStats(
                    max_timestamps=self._max_ts,
                    max_sizes=self._max_sizes,
                )
            self._key_to_stats[key].record(response_size_bytes)

    def get_all_keys(self) -> List[str]:
        """Return all keys that have stats (for anomaly dashboard, etc.)."""
        with self._lock:
            return list(self._key_to_stats.keys())

    def get_stats_for_score(
        self,
        key: str,
        window_seconds: float,
        num_windows: int,
        recency_decay_per_window: float = 0.0,
    ) -> Tuple[List[float], float, float]:
        """
        Returns (counts_per_window, mean_size, std_size) for the given key.
        counts_per_window can be empty; then mean_size, std_size may still be set.
        """
        with self._lock:
            stats = self._key_to_stats.get(key)
        if not stats:
            return [], 0.0, 0.0
        counts = stats.get_request_counts_per_window(
            window_seconds, num_windows, recency_decay_per_window
        )
        mean_s, std_s = stats.get_size_stats()
        return counts, mean_s, std_s
