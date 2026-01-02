from django.http import HttpResponse, JsonResponse
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
import logging, json

from .models import Banner
from .serializers import BannerSerializer
from domains.models import Domain
from billing.models import BillingProfile
from billing.guards import get_user_plan, can_use_feature

log = logging.getLogger(__name__)


# Fields that free tier users can customize
FREE_TIER_FIELDS = {
	"name", "domains", "is_active", "type", "position",
	"title", "description", "accept_text", "reject_text", "prefs_text",
	"theme", "has_reject_button", "show_preferences_button",
}

# Fields that require Pro+ plan (full customization)
PREMIUM_FIELDS = {
	"background_color", "background_opacity", "text_color",
	"accept_bg_color", "accept_text_color", "accept_border_color",
	"accept_border_width_px", "accept_border_radius_px",
	"reject_bg_color", "reject_text_color", "reject_border_color",
	"reject_border_width_px", "reject_border_radius_px",
	"prefs_bg_color", "prefs_text_color", "prefs_border_color",
	"prefs_border_width_px", "prefs_border_radius_px",
	"border_radius_px", "border_color", "border_width_px",
	"padding_x_px", "padding_y_px", "spacing_px", "text_align",
	"shadow", "shadow_custom", "z_index", "width", "height",
	"overlay_enabled", "overlay_color", "overlay_opacity", "overlay_blur_px",
	"cookie_policy_text",
}


@extend_schema_view(
	list=extend_schema(description="List all banners for the current user", tags=["Banners"]),
	create=extend_schema(description="Create a new banner", tags=["Banners"])
)
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

		# Skip plan checks in development mode
		is_dev = getattr(settings, "DJANGO_ENV", "production") == "development"

		# Check plan limitations
		plan = get_user_plan(self.request.user)
		is_free = plan == "free" and not is_dev

		# Free tier: force branding to show
		if is_free:
			serializer.validated_data["show_cookieguard_logo"] = True

		# Free tier: check for premium field usage
		if is_free:
			used_premium = set(self.request.data.keys()) & PREMIUM_FIELDS
			if used_premium:
				raise ValidationError({
					"detail": f"Your Free plan does not allow customizing: {', '.join(used_premium)}. Upgrade to Pro for full customization.",
					"code": "premium_features_required",
					"premium_fields": list(used_premium),
				})

		banner = serializer.save(name=name)
		banner.domains.set(domains)


@extend_schema_view(
	retrieve=extend_schema(description="Get banner details", tags=["Banners"]),
	update=extend_schema(description="Update a banner", tags=["Banners"]),
	partial_update=extend_schema(description="Partially update a banner", tags=["Banners"]),
	destroy=extend_schema(description="Delete a banner", tags=["Banners"])
)
class BannerDetailView(generics.RetrieveUpdateDestroyAPIView):
	serializer_class = BannerSerializer

	def get_queryset(self):
		return Banner.objects.filter(domains__user=self.request.user).distinct()

	def perform_update(self, serializer):
		# Skip plan checks in development mode
		is_dev = getattr(settings, "DJANGO_ENV", "production") == "development"

		plan = get_user_plan(self.request.user)
		is_free = plan == "free" and not is_dev

		# Free tier: force branding to show
		if is_free:
			serializer.validated_data["show_cookieguard_logo"] = True

			# Block if trying to hide branding
			if self.request.data.get("show_cookieguard_logo") is False:
				raise ValidationError({
					"detail": "Removing CookieGuard branding requires a Pro or Multi-Site plan.",
					"code": "premium_feature_required",
				})

		# Free tier: check for premium field usage
		if is_free:
			used_premium = set(self.request.data.keys()) & PREMIUM_FIELDS
			if used_premium:
				raise ValidationError({
					"detail": f"Your Free plan does not allow customizing: {', '.join(used_premium)}. Upgrade to Pro for full customization.",
					"code": "premium_features_required",
					"premium_fields": list(used_premium),
				})

		serializer.save()


# --- 🧠 New endpoint for metadata only ---
@extend_schema(
	responses={200: {"type": "object", "properties": {
		"domain": {"type": "string"},
		"user": {"type": "string", "nullable": True},
		"subscription_status": {"type": "string", "nullable": True},
		"banner": {"type": "object"},
		"categories": {"type": "object"}
	}}},
	description="Get banner metadata for an embed key (public)",
	tags=["Banners"]
)
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

	# Get cookie categories for this domain
	categories_qs = domain.cookie_categories.all()
	categories_config = {}
	for cat in categories_qs:
		if cat.category not in categories_config:
			categories_config[cat.category] = []
		categories_config[cat.category].append({
			'name': cat.script_name,
			'pattern': cat.script_pattern,
			'description': cat.description
		})

	return JsonResponse({
		"domain": domain.url,
		"user": user.email if user else None,
		"subscription_status": status,
		"banner": serialized,
		"categories": categories_config
	})


# Used to bypass subscription checks during testing
TEST_EMBED_KEYS = ['X9oOsVr4IYqLTSsjqaEtZg0J9OuYsByF', '3-uK4ofsHmlqNq0LIsZaTmY37OJN_HmD', 'GoTfwqm04veYlewWPrrkd8BJ7GHb3uZ8']


@extend_schema(exclude=True)
@permission_classes([AllowAny])
def embed_script(request, embed_key: str):
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		return HttpResponse('console.warn("[CookieGuard] Invalid embed key");', content_type="application/javascript")

	user = domain.user

	# Skip subscription check for test embed keys, test domains, or local dev
	host = request.get_host().lower()
	is_local = 'localhost' in host or '127.0.0.1' in host or 'ngrok' in host
	is_test = (
			is_local or
			embed_key in TEST_EMBED_KEYS or
			'cookieguard-test-site.vercel.app' in domain.url.lower()
	)

	if not is_test:
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
		"embed_key": domain.embed_key,
		"title": banner.title,
		"description": banner.description,
		"accept_text": banner.accept_text,
		"reject_text": banner.reject_text,
		"prefs_text": banner.prefs_text,
		"cookie_policy_text": banner.cookie_policy_text,
		"background_color": banner.background_color,
		"background_opacity": banner.background_opacity,
		"text_color": "#111827" if banner.theme == "light" else "#ffffff",
		"accept_bg_color": banner.accept_bg_color,
		"accept_text_color": banner.accept_text_color,
		"reject_bg_color": banner.reject_bg_color,
		"reject_text_color": banner.reject_text_color,
		"prefs_bg_color": banner.prefs_bg_color,
		"prefs_text_color": banner.prefs_text_color,
		"accept_border_color": banner.accept_border_color,
		"accept_border_width_px": banner.accept_border_width_px,
		"accept_border_radius_px": banner.accept_border_radius_px,
		"reject_border_color": banner.reject_border_color,
		"reject_border_width_px": banner.reject_border_width_px,
		"reject_border_radius_px": banner.reject_border_radius_px,
		"prefs_border_color": banner.prefs_border_color,
		"prefs_border_width_px": banner.prefs_border_width_px,
		"prefs_border_radius_px": banner.prefs_border_radius_px,
		"border_radius_px": banner.border_radius_px,
		"border_color": banner.border_color,
		"border_width_px": banner.border_width_px,
		"padding_x_px": banner.padding_x_px,
		"padding_y_px": banner.padding_y_px,
		"spacing_px": banner.spacing_px,
		"text_align": banner.text_align,
		"shadow": banner.shadow,
		"shadow_custom": banner.shadow_custom,
		"overlay_enabled": banner.overlay_enabled,
		"overlay_color": banner.overlay_color,
		"overlay_opacity": banner.overlay_opacity,
		"overlay_blur_px": banner.overlay_blur_px,
		"z_index": banner.z_index,
		"has_reject_button": banner.has_reject_button,
		"show_logo": banner.show_cookieguard_logo,
		"show_prefs": banner.show_preferences_button,
		"position": banner.position,
		"type": banner.type,
		"api_url": API_URL,
		"gradient_enabled": banner.gradient_enabled,
		"gradient_color_1": banner.gradient_color_1,
		"gradient_color_2": banner.gradient_color_2,
		"gradient_color_3": banner.gradient_color_3,
		"gradient_speed": banner.gradient_speed,
		"gradient_persist": banner.gradient_persist,
	}

	if is_local:
		# Use the same host that served the script request
		protocol = "https" if "ngrok" in host else "http"
		STATIC_URL = f"{protocol}://{request.get_host()}/static/embed.js"
	else:
		STATIC_URL = "https://api.cookieguard.app/static/embed.js?v=1.0.0"

	js = f"""
    (function() {{
        window.CookieGuardConfig = {json.dumps(cfg)};
        var s = document.createElement('script');
        s.src = '{STATIC_URL}';
        s.async = true;
        document.head.appendChild(s);
    }})();
    """

	return HttpResponse(js, content_type="application/javascript")
