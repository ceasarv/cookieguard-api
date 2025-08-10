from django.urls import path
from .views import scan_view, trigger_scan, scan_status

urlpatterns = [
	path('scan/', scan_view),
	path("trigger-scan/", trigger_scan, name="trigger_scan"),
	path("scan-status/<str:task_id>/", scan_status, name="scan_status"),

]
