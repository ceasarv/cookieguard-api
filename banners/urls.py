from django.urls import path
from .views import BannerListCreateView, BannerDetailView, embed_script, banner_metadata

urlpatterns = [
	path("", BannerListCreateView.as_view(), name="banner-list-create"),
	path("<int:pk>/", BannerDetailView.as_view(), name="banner-detail"),
	path("embed/<str:embed_key>/", banner_metadata, name="banner-metadata"),
]
