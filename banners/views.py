from django.http import HttpResponse
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from .models import Banner
from .serializers import BannerSerializer
from domains.models import Domain
from django.conf import settings
import logging, json, hashlib
from billing.models import BillingProfile

log = logging.getLogger(__name__)


class BannerListCreateView(generics.ListCreateAPIView):
	serializer_class = BannerSerializer

	def get_queryset(self):
		# Banners where at least one of the linked domains belongs to the user
		return Banner.objects.filter(domains__user=self.request.user).distinct()

	def perform_create(self, serializer):
		domain_ids = self.request.data.get("domains", [])
		if not domain_ids:
			raise ValidationError({"domains": ["At least one domain is required."]})

		# Validate each domain
		domains = Domain.objects.filter(id__in=domain_ids, user=self.request.user)
		if not domains.exists():
			raise ValidationError({"domains": ["No valid domains provided."]})

		# Auto-generate a default name if missing
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


def embed_script(request, embed_key: str):
	def _js(msg: str):
		return HttpResponse(
			f'console.warn("[CookieGuard] {msg}");',
			content_type="application/javascript",
			status=200,
		)

	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		return _js("Domain not found — check your embed key.")

	user = domain.user
	if not user:
		return _js("No user associated with this domain.")

	# check subscription
	profile = BillingProfile.objects.filter(user=user).first()
	if not profile or (profile.subscription_status or "").lower() not in ("active", "trialing"):
		return _js("// CookieGuard: inactive or free account")

	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return _js("// CookieGuard: no active banner for this domain")

	API_URL = (
		"http://127.0.0.1:8000/api/consents/create/"
		if getattr(settings, "DJANGO_ENV", "production") == "development"
		else "https://cookieguard.app/api/consents/create/"
	)

	text_color = getattr(banner, "text_color", "#111827")  # fallback if not added yet

	cfg = {
		"id": banner.id,
		"version": banner.version,
		"title": banner.title,
		"description": banner.description,
		"accept_text": banner.accept_text,
		"reject_text": banner.reject_text,
		"prefs_text": banner.prefs_text,
		"background_color": banner.background_color,
		"text_color": text_color,
		"accept_bg_color": banner.accept_bg_color,
		"accept_text_color": banner.accept_text_color,
		"reject_bg_color": banner.reject_bg_color,
		"reject_text_color": banner.reject_text_color,
		"prefs_bg_color": banner.prefs_bg_color,
		"prefs_text_color": banner.prefs_text_color,
	}

	js = f"""
	(function() {{
		console.log("[CookieGuard] ✅ Banner loaded for {domain.url}");
		const cfg = {json.dumps(cfg)};
		const EMBED_KEY = "{embed_key}";
		const API_URL = "{API_URL}";

		// 🧩 inject base CSS
		const css = document.createElement("link");
		css.rel = "stylesheet";
		css.href = "https://api.cookieguard.app/static/banner-base.css";
		css.crossOrigin = "anonymous";
		document.head.appendChild(css);

		function logConsent(choice) {{
			fetch(API_URL, {{
				method: "POST",
				headers: {{ "Content-Type": "application/json" }},
				body: JSON.stringify({{
					embed_key: EMBED_KEY,
					banner_id: cfg.id,
					banner_version: cfg.version,
					choice: choice,
				}}),
			}})
			.then(r => r.json())
			.then(d => console.log("[CookieGuard] consent logged", d))
			.catch(err => console.warn("[CookieGuard] consent log failed", err));
		}}

		// Render banner
		const host = document.createElement("div");
		host.className = "cg-banner";
		host.innerHTML = `
			<div class="cg-content" style="color:${{cfg.text_color}};background:${{cfg.background_color}}">
				<h3 class="cg-title">${{cfg.title}}</h3>
				<p class="cg-desc">${{cfg.description}}</p>
				<div class="cg-buttons">
					<button class="cg-btn cg-accept" style="background:${{cfg.accept_bg_color}};color:${{cfg.accept_text_color}}">
						${{cfg.accept_text}}
					</button>
					<button class="cg-btn cg-reject" style="background:${{cfg.reject_bg_color}};color:${{cfg.reject_text_color}}">
						${{cfg.reject_text}}
					</button>
				</div>
			</div>`;

		document.body.appendChild(host);
		host.querySelector(".cg-accept").addEventListener("click", () => logConsent("accept_all"));
		host.querySelector(".cg-reject").addEventListener("click", () => logConsent("reject_all"));
	}})();
	"""

	return HttpResponse(js, content_type="application/javascript")
