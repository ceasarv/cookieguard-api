from django.urls import path
from .views import HelpRequestView

urlpatterns = [
	path("request/", HelpRequestView.as_view(), name="help-request"),
]
