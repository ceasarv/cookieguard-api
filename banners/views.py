from django.http import HttpResponse, JsonResponse
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from django.conf import settings
import logging, json

from .models import Banner
from .serializers import BannerSerializer
from domains.models import Domain
from billing.models import BillingProfile

log = logging.getLogger(__name__)


class BannerListCreateView(generics.ListCreateAPIView):
	serializer_class = BannerSerializer

	def get_queryset(self):
		return Banner.objects.filter(domains__user=self.request.user).distinct()

	def perform_create(self, serializer):
		domain_ids = self.request.data.get("domains", [])
		if not domain_ids:
			raise ValidationError({"domains": ["At least one domain is required."]})

		domains = Domain.objects.filter(id__in=domain_ids, user=self.request.user)
		if not domains.exists():
			raise ValidationError({"domains": ["No valid domains provided."]})

		name = self.request.data.get("name", "").strip()
		if not name:
			existing_names = (
				Banner.objects.filter(domains__user=self.request.user)
				.values_list("name", flat=True)
			)
			numbers = []
			for n in existing_names:
				if n and n.startswith("Banner "):
					try:
						numbers.append(int(n.split(" ")[1]))
					except (ValueError, IndexError):
						pass
			next_num = max(numbers) + 1 if numbers else 1
			name = f"Banner {next_num:02d}"

		banner = serializer.save(name=name)
		banner.domains.set(domains)


class BannerDetailView(generics.RetrieveUpdateDestroyAPIView):
	serializer_class = BannerSerializer

	def get_queryset(self):
		return Banner.objects.filter(domains__user=self.request.user).distinct()


# --- 🧠 New endpoint for metadata only ---
@api_view(["GET"])
@permission_classes([AllowAny])
def banner_metadata(request, embed_key: str):
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		return JsonResponse({"error": "Domain not found"}, status=404)

	user = domain.user
	profile = BillingProfile.objects.filter(user=user).first()
	status = (profile.subscription_status or "").lower() if profile else None

	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return JsonResponse({"error": "No active banner found"}, status=404)

	serialized = BannerSerializer(banner).data
	return JsonResponse({
		"domain": domain.url,
		"user": user.email if user else None,
		"subscription_status": status,
		"banner": serialized
	})


# --- Original JS embed endpoint ---
@permission_classes([AllowAny])
def embed_script(request, embed_key: str):
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		return HttpResponse('console.warn("[CookieGuard] Invalid embed key");', content_type="application/javascript")

	user = domain.user
	profile = BillingProfile.objects.filter(user=user).first()
	status = (profile.subscription_status or "").lower() if profile else "inactive"
	if status not in ("active", "trialing"):
		return HttpResponse(f'console.warn("[CookieGuard] Inactive subscription ({status})");',
							content_type="application/javascript")

	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return HttpResponse('console.warn("[CookieGuard] No active banner");', content_type="application/javascript")

	env = getattr(settings, "DJANGO_ENV", "production")
	API_URL = (
		"http://127.0.0.1:8000/api/consents/create/"
		if env == "development"
		else "https://api.cookieguard.app/api/consents/create/"
	)

	cfg = {
		"id": banner.id,
		"title": banner.title,
		"description": banner.description,
		"accept_text": banner.accept_text,
		"reject_text": banner.reject_text,
		"prefs_text": banner.prefs_text,
		"background_color": banner.background_color,
		"text_color": "#111827" if banner.theme == "light" else "#ffffff",
		"accept_bg_color": banner.accept_bg_color,
		"accept_text_color": banner.accept_text_color,
		"reject_bg_color": banner.reject_bg_color,
		"reject_text_color": banner.reject_text_color,
		"prefs_bg_color": banner.prefs_bg_color,
		"prefs_text_color": banner.prefs_text_color,
		"border_radius_px": banner.border_radius_px,
		"spacing_px": banner.spacing_px,
		"text_align": banner.text_align,
		"show_logo": banner.show_cookieguard_logo,
		"show_prefs": banner.show_preferences_button,
		"position": banner.position,
		"type": banner.type,
		"api_url": API_URL,
	}

	js = f"""
    (function() {{
        window.CookieGuardConfig = {json.dumps(cfg)};
        var s = document.createElement('script');
        s.src = 'https://api.cookieguard.app/static/embed.js?v=1.0.0';
        s.async = true;
        document.head.appendChild(s);
    }})();
    """

	return HttpResponse(js, content_type="application/javascript")
