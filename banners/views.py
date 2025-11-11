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

	# --- Domain lookup ---
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		return _js("Domain not found — check your embed key.")

	user = domain.user
	if not user:
		return _js("No user associated with this domain.")

	# --- Subscription check ---
	profile = BillingProfile.objects.filter(user=user).first()
	sub_status = (profile.subscription_status or "").lower() if profile else None
	if sub_status not in ("active", "trialing"):
		return _js("// CookieGuard: inactive or free account")

	# --- Banner lookup ---
	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return _js("// CookieGuard: no active banner for this domain")

	# --- Environment-based API URL ---
	env = getattr(settings, "DJANGO_ENV", "production")
	if env == "development":
		API_URL = "http://127.0.0.1:8000/api/consents/create/"
		BASE_STATIC = "http://127.0.0.1:8000/static"
	else:
		API_URL = "https://api.cookieguard.app/api/consents/create/"
		BASE_STATIC = "https://api.cookieguard.app/static"

	# --- Compute text color (fallbacks) ---
	text_color = getattr(banner, "text_color", None)
	if not text_color:
		text_color = "#ffffff" if banner.theme == "dark" else "#111827"

	# --- Config ---
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
		"border_radius_px": banner.border_radius_px,
		"spacing_px": banner.spacing_px,
		"text_align": banner.text_align,
	}

	js = f"""
    (function() {{
        console.log("[CookieGuard] ✅ Banner loaded for {domain.url}");
        const cfg = {json.dumps(cfg)};
        const EMBED_KEY = "{embed_key}";
        const API_URL = "{API_URL}";
        const BASE_STATIC = "{BASE_STATIC}";

        // Inject base stylesheet
        const css = document.createElement("link");
        css.rel = "stylesheet";
        css.href = BASE_STATIC + "/banner-base.css";
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
            .then(d => console.log("[CookieGuard] Consent logged", d))
            .catch(err => console.warn("[CookieGuard] Log failed", err));
        }}

        // Create host + shadow DOM
        const host = document.createElement("div");
        host.style.position = "fixed";
        host.style.bottom = "24px";
        host.style.left = "50%";
        host.style.transform = "translateX(-50%)";
        host.style.zIndex = "99999";
        document.body.appendChild(host);

        const shadow = host.attachShadow({{ mode: "open" }});

        const style = document.createElement("style");
        style.textContent = `
            .cg-wrap {{
                position: relative;
                background: ${{cfg.background_color}};
                color: ${{cfg.text_color}};
                border-radius: ${banner.border_radius_px}px;
                padding: ${banner.padding_y_px}px ${banner.padding_x_px}px;
                text-align: ${banner.text_align};
                font-family: system-ui, sans-serif;
                line-height: 1.45;
                box-shadow: ${banner.box_shadow_css};
                max-width: 520px;
                animation: cgFadeIn .3s ease;
            }}
            @keyframes cgFadeIn {{
                from {{ opacity: 0; transform: scale(0.95); }}
                to {{ opacity: 1; transform: scale(1); }}
            }}
            .cg-title {{
                font-size: 1.125rem;
                font-weight: 700;
                margin-bottom: 6px;
            }}
            .cg-desc {{
                font-size: .95rem;
                margin-bottom: ${banner.spacing_px}px;
            }}
            .cg-buttons {{
                display: flex;
                gap: ${banner.spacing_px}px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            .cg-btn {{
                font-size: .9rem;
                padding: 8px 14px;
                cursor: pointer;
                border: none;
                border-radius: 6px;
                transition: transform .05s ease;
            }}
            .cg-btn:active {{ transform: scale(.97); }}
            .cg-accept {{
                background: ${{cfg.accept_bg_color}};
                color: ${{cfg.accept_text_color}};
            }}
            .cg-reject {{
                background: ${{cfg.reject_bg_color}};
                color: ${{cfg.reject_text_color}};
            }}
            .cg-prefs {{
                background: ${{cfg.prefs_bg_color}};
                color: ${{cfg.prefs_text_color}};
            }}
        `;

        const box = document.createElement("div");
        box.className = "cg-wrap";
        box.innerHTML = `
            <div class="cg-title">${{cfg.title}}</div>
            <div class="cg-desc">${{cfg.description}}</div>
            <div class="cg-buttons">
                <button class="cg-btn cg-accept">${{cfg.accept_text}}</button>
                <button class="cg-btn cg-reject">${{cfg.reject_text}}</button>
            </div>`;

        shadow.appendChild(style);
        shadow.appendChild(box);

        // Button events
        const acceptBtn = shadow.querySelector(".cg-accept");
        const rejectBtn = shadow.querySelector(".cg-reject");
        if (acceptBtn) acceptBtn.onclick = () => {{ logConsent("accept_all"); host.remove(); }};
        if (rejectBtn) rejectBtn.onclick = () => {{ logConsent("reject_all"); host.remove(); }};
    }})();"""

	return HttpResponse(js, content_type="application/javascript")
