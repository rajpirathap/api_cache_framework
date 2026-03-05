import json

from django.http import JsonResponse
from django.shortcuts import render


def list_items(request):
    """Example list API. Hit repeatedly to raise score; large payload to favour caching."""
    items = [{"id": i, "name": f"Item {i}"} for i in range(500)]
    return JsonResponse(items, safe=False)


def small(request):
    """Small response: frequent hits here get penalised (frequent + low size)."""
    return JsonResponse({"ok": True, "size": "small"})


def health(request):
    """Tiny response, usually not worth caching by the formula."""
    return JsonResponse({"status": "ok"})


def anomaly_dashboard_api(request):
    """JSON API for anomaly dashboard. Accepts ?alpha=&s0_kb=&s1_kb=&window_min= for tuning."""
    from api_cache_framework.anomaly_stats import _get_anomaly_service
    overrides = {}
    if request.GET.get("alpha") is not None:
        try:
            overrides["alpha"] = float(request.GET["alpha"])
        except ValueError:
            pass
    if request.GET.get("s0_kb") is not None:
        try:
            overrides["s0"] = float(request.GET["s0_kb"]) * 1024
        except ValueError:
            pass
    if request.GET.get("s1_kb") is not None:
        try:
            overrides["s1"] = float(request.GET["s1_kb"]) * 1024
        except ValueError:
            pass
    if request.GET.get("window_min") is not None:
        try:
            overrides["window_minutes"] = float(request.GET["window_min"])
        except ValueError:
            pass
    data = _get_anomaly_service().get_anomaly_dashboard_data(
        overrides=overrides if overrides else None
    )
    return JsonResponse({"endpoints": data})


def anomaly_dashboard_html(request):
    """HTML page for anomaly dashboard with chart."""
    from api_cache_framework.anomaly_stats import _get_anomaly_service
    data = _get_anomaly_service().get_anomaly_dashboard_data()
    return render(request, "anomaly_dashboard.html", {
        "endpoints": data,
        "endpoints_json": json.dumps(data),
    })
