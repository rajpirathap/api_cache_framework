import os
import sys

# Ensure project root (containing api_cache_framework) is on PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SECRET_KEY = "demo-secret"
DEBUG = True
ALLOWED_HOSTS = ["*"]
INSTALLED_APPS = ["django.contrib.contenttypes", "app"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "api_cache_framework.anomaly_middleware.AnomalyDetectionMiddleware",
]
ROOT_URLCONF = "demo.urls"
WSGI_APPLICATION = "demo.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

# CAS formula config for anomaly detection (no cache)
API_ANOMALY_FRAMEWORK = {
    "s0_bytes": 10 * 1024,       # 10 KB scale for mean size
    "s1_bytes": 5 * 1024,        # 5 KB scale for size std dev
    "alpha": 0.1,                # penalty for frequent + small
    "window_minutes": 0.05,      # 3 sec windows for demo
}
