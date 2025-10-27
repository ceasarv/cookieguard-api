from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
	TokenObtainPairView,
	TokenRefreshView,
)
from banners.views import embed_script

urlpatterns = [
	path('admin/', admin.site.urls),
	path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
	path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
	path('api/auth/', include('users.urls')),
	path("scripts/<str:embed_key>.js", embed_script, name="embed_script"),
	path('api/', include('scanner.urls')),
	path('api/billing/', include('billing.urls')),
	path('api/domains/', include('domains.urls')),
	path('api/consents/', include('consents.urls')),
	path('api/banners/', include('banners.urls')),
	path("api/support/", include("support.urls")),
]
