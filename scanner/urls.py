from django.urls import path
from .views import (
	scan_view, trigger_scan, scan_status,
	domain_cookies, classify_cookie, cookie_definitions, serve_screenshot
)

urlpatterns = [
	path('scan/', scan_view),
	path("trigger-scan/", trigger_scan, name="trigger_scan"),
	path("scan-status/<str:task_id>/", scan_status, name="scan_status"),
	path("screenshots/<str:filename>", serve_screenshot, name="serve_screenshot"),

	# Cookie classification endpoints
	path("domains/<uuid:domain_id>/cookies/", domain_cookies, name="domain_cookies"),
	path("cookies/<int:cookie_id>/classify/", classify_cookie, name="classify_cookie"),
	path("cookie-definitions/", cookie_definitions, name="cookie_definitions"),
]
