from django.urls import path
from .views import ConsentAnalyticsView

urlpatterns = [
	path("consents/", ConsentAnalyticsView.as_view(), name="consent-analytics"),
]
