from django.urls import path
from . import views

urlpatterns = [
	path("create/", views.log_consent, name="log_consent"),  # POST /api/consents/create/
	path("", views.list_consents, name="list_consents"),
	path("pageview/", views.track_pageview, name="track_pageview"),  # POST /api/consents/pageview/
	path("export/", views.export_consents_csv, name="export_consents_csv"),  # GET /api/consents/export/
]
