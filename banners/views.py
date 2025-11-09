from django.http import HttpResponse
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from .models import Banner
from .serializers import BannerSerializer
from domains.models import Domain
from django.conf import settings
import logging, json, random
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
		"""Return JS with a visible console warning."""
		return HttpResponse(
			f'console.warn("[CookieGuard] {msg}");',
			content_type="application/javascript",
			status=200,
		)

	# --- Lookup domain by embed key ---
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		log.warning(f"[EmbedScript] ❌ Domain not found for key={embed_key}")
		return _js("Domain not found — check your embed key.")

	user = domain.user
	if not user:
		log.warning(f"[EmbedScript] ❌ Domain {domain.id} has no user.")
		return _js("No user associated with this domain.")

	# --- Check BillingProfile ---
	try:
		profile = BillingProfile.objects.filter(user=user).first()
	except Exception as e:
		log.error(f"[EmbedScript] BillingProfile lookup failed for {user.email}: {e}")
		return _js("Billing profile lookup failed.")

	if not profile:
		log.warning(f"[EmbedScript] ⚠️ No BillingProfile found for {user.email}")
		return _js("No billing profile found — user not subscribed.")

	sub_status = (profile.subscription_status or "").lower()
	if sub_status not in ("active", "trialing"):
		log.warning(
			f"[EmbedScript] ⚠️ Inactive subscription for {user.email} (status={sub_status})"
		)
		return _js(f"Banner disabled — subscription status: {sub_status or 'unknown'}")

	log.info(f"[EmbedScript] ✅ Valid subscription for {user.email} (status={sub_status})")

	# --- Fetch active banners ---
	banners = list(domain.banners.filter(is_active=True))
	if not banners:
		log.warning(f"[EmbedScript] ⚠️ Domain {domain.id} has no active banners.")
		return _js("No active banner configured for this domain.")

	banner = random.choice(banners)

	# --- Environment-based API URL ---
	env = getattr(settings, "DJANGO_ENV", "production")
	API_URL = (
		"http://127.0.0.1:8000/api/consents/create/"
		if env == "development"
		else "https://cookieguard.app/api/consents/create/"
	)

	# --- Build banner HTML ---
	reject_button_html = (
		f"<button class='cg-btn cg-reject'>{banner.reject_text}</button>"
		if banner.has_reject_button else ""
	)
	prefs_button_html = (
		f"<button class='cg-btn cg-prefs'>{banner.prefs_text}</button>"
		if banner.show_preferences_button else ""
	)

	html = f"""
        <div class="cg-title">{banner.title}</div>
        <div class="cg-desc">{banner.description}</div>
        <div class="cg-buttons">
            <button class="cg-btn cg-accept">{banner.accept_text}</button>
            {reject_button_html}
            {prefs_button_html}
        </div>
    """

	# --- JS config payload ---
	cfg = {
		"id": banner.id,
		"version": banner.version,
		"title": banner.title,
		"description": banner.description,
		"accept_text": banner.accept_text,
		"reject_text": banner.reject_text,
		"prefs_text": banner.prefs_text,
		"has_reject_button": banner.has_reject_button,
		"show_preferences_button": banner.show_preferences_button,
		"background_color": banner.background_color,
		"border_color": banner.border_color,
		"border_width_px": banner.border_width_px,
		"border_radius_px": banner.border_radius_px,
		"accept_bg_color": banner.accept_bg_color,
		"accept_text_color": banner.accept_text_color,
		"reject_bg_color": banner.reject_bg_color,
		"reject_text_color": banner.reject_text_color,
		"prefs_bg_color": banner.prefs_bg_color,
		"prefs_text_color": banner.prefs_text_color,
		"padding_x_px": banner.padding_x_px,
		"padding_y_px": banner.padding_y_px,
		"spacing_px": banner.spacing_px,
		"text_align": banner.text_align,
		"z_index": banner.z_index,
		"width": banner.width or "",
		"height": banner.height or "",
	}

	# --- Inject JS ---
	js = f"""
    (function() {{
        console.log("[CookieGuard] ✅ Banner loaded for {domain.url}");
        const cfg = {json.dumps(cfg)};
        const EMBED_KEY = "{embed_key}";
        const API_URL = "{API_URL}";

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

        // 🧱 Basic banner rendering
        const host = document.createElement("div");
        host.style.position = "fixed";
        host.style.bottom = "20px";
        host.style.left = "20px";
        host.style.background = cfg.background_color || "#222";
        host.style.color = "#fff";
        host.style.padding = "10px 16px";
        host.style.borderRadius = "8px";
        host.style.fontFamily = "system-ui,sans-serif";
        host.style.zIndex = cfg.z_index || 9999;
        host.innerHTML = `
            <div style="font-weight:700;margin-bottom:4px;">{banner.title}</div>
            <p style="font-size:0.9rem;margin-bottom:8px;">{banner.description}</p>
            <button id="cg-accept" style="
                background:{banner.accept_bg_color};
                color:{banner.accept_text_color};
                border:none;border-radius:6px;
                padding:6px 12px;
                cursor:pointer;">
                {banner.accept_text}
            </button>`;
        document.body.appendChild(host);

        document.getElementById("cg-accept").onclick = () => {{
            logConsent("accept_all");
            host.remove();
        }};
    }})();"""

	log.info(f"[EmbedScript] ✅ Served banner for {domain.url} (user={user.email})")
	return HttpResponse(js, content_type="application/javascript")
