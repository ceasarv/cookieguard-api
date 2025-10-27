from django.urls import path
from .views import BannerListCreateView, BannerDetailView

urlpatterns = [
	path("", BannerListCreateView.as_view(), name="banner-list-create"),
	path("<int:pk>/", BannerDetailView.as_view(), name="banner-detail"),
]
