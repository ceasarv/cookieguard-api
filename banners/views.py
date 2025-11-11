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
		return HttpResponse(
			'console.warn("[CookieGuard] Invalid embed key — domain not found");',
			content_type="application/javascript",
		)

	user = domain.user
	if not user:
		return HttpResponse(
			'console.warn("[CookieGuard] No user for this domain");',
			content_type="application/javascript",
		)

	profile = BillingProfile.objects.filter(user=user).first()
	status = (profile.subscription_status or "").lower() if profile else "inactive"
	if status not in ("active", "trialing"):
		return HttpResponse(
			f'console.warn("[CookieGuard] Banner disabled — subscription {status}");',
			content_type="application/javascript",
		)

	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return HttpResponse(
			'console.warn("[CookieGuard] No active banner configured");',
			content_type="application/javascript",
		)

	env = getattr(settings, "DJANGO_ENV", "production")
	if env == "development":
		API_URL = "http://127.0.0.1:8000/api/consents/create/"
		BASE_STATIC = "http://127.0.0.1:8000/static"
	else:
		API_URL = "https://api.cookieguard.app/api/consents/create/"
		BASE_STATIC = "https://api.cookieguard.app/static"

	# Banner config payload
	cfg = {
		"id": banner.id,
		"title": banner.title,
		"description": banner.description,
		"accept_text": banner.accept_text,
		"reject_text": banner.reject_text,
		"prefs_text": banner.prefs_text,
		"background_color": banner.background_color,
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
		"position": banner.position,
		"type": banner.type,
	}

	# JS embed
	js = f"""
	(function() {{
		console.log("[CookieGuard] ✅ Banner loaded for {domain.url}");
		const cfg = {json.dumps(cfg)};
		const EMBED_KEY = "{embed_key}";
		const API_URL = "{API_URL}";
		const BASE_STATIC = "{BASE_STATIC}";

		// load base CSS
		const css = document.createElement("link");
		css.rel = "stylesheet";
		css.href = BASE_STATIC + "/banner-base.css";
		document.head.appendChild(css);

		function logConsent(choice) {{
			fetch(API_URL, {{
				method: "POST",
				headers: {{ "Content-Type": "application/json" }},
				body: JSON.stringify({{
					embed_key: EMBED_KEY,
					banner_id: cfg.id,
					banner_version: 1,
					choice: choice
				}}),
			}}).catch(err => console.warn("[CookieGuard] log failed", err));
		}}

		// position mapping
		const positions = {{
			"bottom-left": {{bottom: "20px", left: "20px", right: "auto", top: "auto", transform: "none"}},
			"bottom-right": {{bottom: "20px", right: "20px", left: "auto", top: "auto", transform: "none"}},
			"bottom": {{bottom: "0", left: "0", right: "0", transform: "none"}},
			"top": {{top: "0", left: "0", right: "0", transform: "none"}},
			"top-left": {{top: "20px", left: "20px"}},
			"top-right": {{top: "20px", right: "20px"}},
			"center": {{top: "50%", left: "50%", transform: "translate(-50%, -50%)"}},
		}};
		const pos = positions[cfg.position] || positions["bottom"];

		// build banner host
		const host = document.createElement("div");
		Object.assign(host.style, {{
			position: "fixed",
			zIndex: "9999",
			...pos
		}});
		document.body.appendChild(host);

		const shadow = host.attachShadow({{mode:"open"}});
		const box = document.createElement("div");
		box.className = "cg-wrap";
		box.style.background = cfg.background_color;
		box.style.color = "#111827";
		box.style.borderRadius = cfg.border_radius_px + "px";
		box.style.padding = "12px 16px";
		box.style.maxWidth = cfg.type === "bar" ? "100%" : "400px";
		box.style.width = cfg.type === "bar" ? "100%" : "auto";
		box.style.boxShadow = "0 4px 10px rgba(0,0,0,0.15)";
		box.style.textAlign = cfg.text_align;

		box.innerHTML = `
			<div class="cg-title" style="font-weight:700;margin-bottom:6px;">${{cfg.title}}</div>
			<div class="cg-desc" style="font-size:0.95rem;margin-bottom:${{cfg.spacing_px}}px;">${{cfg.description}}</div>
			<div class="cg-buttons" style="display:flex;gap:${{cfg.spacing_px}}px;flex-wrap:wrap;justify-content:center;">
				<button class="cg-btn cg-accept" style="background:${{cfg.accept_bg_color}};color:${{cfg.accept_text_color}};border:none;padding:8px 14px;border-radius:6px;cursor:pointer;">${{cfg.accept_text}}</button>
				<button class="cg-btn cg-reject" style="background:${{cfg.reject_bg_color}};color:${{cfg.reject_text_color}};border:none;padding:8px 14px;border-radius:6px;cursor:pointer;">${{cfg.reject_text}}</button>
			</div>
			${{cfg.show_logo ? `
			<div class="cg-footer" style="margin-top:8px;font-size:11px;opacity:.6;text-align:right;">
				<a href='https://cookieguard.app' target='_blank' rel='noopener noreferrer' style='color:inherit;text-decoration:none;'>Powered by CookieGuard</a>
			</div>` : ""}}
		`;

		shadow.appendChild(box);

		shadow.querySelector(".cg-accept").onclick = () => {{ logConsent("accept_all"); host.remove(); }};
		shadow.querySelector(".cg-reject").onclick = () => {{ logConsent("reject_all"); host.remove(); }};
	}})();
	"""

	return HttpResponse(js, content_type="application/javascript")
