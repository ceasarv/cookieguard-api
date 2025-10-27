from django.urls import path
from . import views

urlpatterns = [
	path("create/", views.log_consent, name="log_consent"),  # POST /api/consents/create/
	path("", views.list_consents, name="list_consents"),
]
