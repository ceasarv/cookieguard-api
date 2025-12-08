from django.urls import path
from . import views

urlpatterns = [
	path("", views.domains_list, name="domains_list"),
	path("<uuid:id>/", views.domain_detail, name="domain_detail"),
	path("<uuid:id>/rotate-key/", views.rotate_key, name="domain_rotate_key"),
	path("<uuid:id>/run-scan/", views.run_scan, name="domain_run_scan"),
	path("<uuid:domain_id>/cookie-categories/", views.cookie_categories_list, name="cookie_categories_list"),
	path("<uuid:domain_id>/cookie-categories/<int:category_id>/", views.cookie_category_detail, name="cookie_category_detail"),
]
