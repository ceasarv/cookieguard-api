from django.urls import path
from . import views

urlpatterns = [
	path("", views.domains_list, name="domains_list"),
	path("<uuid:id>/", views.domain_detail, name="domain_detail"),
	path("<uuid:id>/rotate-key/", views.rotate_key, name="domain_rotate_key"),
	path("<uuid:id>/run-scan/", views.run_scan, name="domain_run_scan"),
]
