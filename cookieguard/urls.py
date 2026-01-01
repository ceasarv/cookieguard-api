from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
	TokenObtainPairView,
	TokenRefreshView,
)
from banners.views import embed_script
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from drf_spectacular.utils import extend_schema, extend_schema_view


# Customize JWT views with proper schema tags
@extend_schema_view(
	post=extend_schema(
		description="Obtain JWT access and refresh tokens",
		tags=["Auth"]
	)
)
class CustomTokenObtainPairView(TokenObtainPairView):
	pass


@extend_schema_view(
	post=extend_schema(
		description="Refresh JWT access token",
		tags=["Auth"]
	)
)
class CustomTokenRefreshView(TokenRefreshView):
	pass


urlpatterns = [
	path('admin/', admin.site.urls),
	path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
	path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
	path('api/auth/', include('users.urls')),
	path("scripts/<str:embed_key>.js", embed_script, name="embed_script"),
	path('api/', include('scanner.urls')),
	path('api/billing/', include('billing.urls')),
	path('api/domains/', include('domains.urls')),
	path('api/consents/', include('consents.urls')),
	path('api/banners/', include('banners.urls')),
	path("api/support/", include("support.urls")),
	path("api/analytics/", include("analytics.urls")),

	# Testing dashboard (staff only)
	path('testing/', include('testing.urls')),

	# API Documentation (superuser only - redirects to admin login if not authenticated)
	path('api/schema/', staff_member_required(SpectacularAPIView.as_view()), name='schema'),
	path('api/docs/', staff_member_required(SpectacularSwaggerView.as_view(url_name='schema')), name='swagger-ui'),
	path('api/redoc/', staff_member_required(SpectacularRedocView.as_view(url_name='schema')), name='redoc'),
]

# Serve media files in development (in production, use whitenoise or nginx)
if settings.DEBUG:
	urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
