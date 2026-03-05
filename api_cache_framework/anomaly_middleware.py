"""
Django middleware for CAS-based anomaly detection.
Records request/response stats only (no cache). Uses the same CAS formula.
"""
import hashlib
import json
from typing import Callable

from django.http import HttpRequest, HttpResponse

from .anomaly_stats import _get_anomaly_service


def _build_key(request: HttpRequest) -> str:
    """Stable key from path + sorted query string."""
    path = request.path
    params = [(k, v) for k, v in request.GET.items() if k not in ("_", "refresh")]
    param_str = json.dumps(sorted(params), sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:16]
    return f"anomaly:{path}:{param_hash}"


class AnomalyDetectionMiddleware:
    """
    Records GET request stats (path, response size) for CAS-based anomaly detection.
    No caching; only stats collection. Same CAS formula used for scoring.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if request.method != "GET" or response.status_code != 200:
            return response
        try:
            size = len(response.content)
            key = _build_key(request)
            _get_anomaly_service().record(key, size)
        except Exception:
            pass
        return response
