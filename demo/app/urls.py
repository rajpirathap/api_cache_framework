from django.urls import path
from . import views

urlpatterns = [
    path("api/items/", views.list_items),
    path("api/small/", views.small),
    path("api/health/", views.health),
    path("api/anomaly-dashboard/", views.anomaly_dashboard_api),
    path("anomaly/", views.anomaly_dashboard_html),
]
