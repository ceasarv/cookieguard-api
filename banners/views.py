from django.http import HttpResponse
from django.http import JsonResponse
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
	def _err(msg: str):
		return JsonResponse({"error": msg}, status=400)

	# --- Lookup domain ---
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		return _err("Domain not found — invalid embed key.")

	user = domain.user
	if not user:
		return _err("No user associated with this domain.")

	# --- Verify billing ---
	profile = BillingProfile.objects.filter(user=user).first()
	sub_status = (profile.subscription_status or "").lower() if profile else None
	if sub_status not in ("active", "trialing"):
		return _err(f"Inactive or free account (status={sub_status or 'unknown'})")

	# --- Get banner ---
	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return _err("No active banner configured for this domain.")

	# --- Environment URLs ---
	env = getattr(settings, "DJANGO_ENV", "production")
	if env == "development":
		API_URL = "http://127.0.0.1:8000/api/consents/create/"
		BASE_STATIC = "http://127.0.0.1:8000/static"
	else:
		API_URL = "https://api.cookieguard.app/api/consents/create/"
		BASE_STATIC = "https://api.cookieguard.app/static"

	# --- Prepare banner data ---
	banner_data = {
		"id": banner.id,
		"version": banner.version,
		"title": banner.title,
		"description": banner.description,
		"background_color": banner.background_color,
		"accept_text": banner.accept_text,
		"reject_text": banner.reject_text,
		"prefs_text": banner.prefs_text,
		"accept_bg_color": banner.accept_bg_color,
		"accept_text_color": banner.accept_text_color,
		"reject_bg_color": banner.reject_bg_color,
		"reject_text_color": banner.reject_text_color,
		"prefs_bg_color": banner.prefs_bg_color,
		"prefs_text_color": banner.prefs_text_color,
		"text_align": banner.text_align,
		"border_radius_px": banner.border_radius_px,
		"spacing_px": banner.spacing_px,
	}

	# --- Generate JS ---
	js = f"""
    (function() {{
        console.log("[CookieGuard] ✅ Banner loaded for {domain.url}");
        const cfg = {json.dumps(banner_data)};
        const EMBED_KEY = "{embed_key}";
        const API_URL = "{API_URL}";
        const BASE_STATIC = "{BASE_STATIC}";

        // inject base CSS
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
                    banner_version: cfg.version,
                    choice: choice,
                }}),
            }})
            .then(r => r.json())
            .then(d => console.log("[CookieGuard] Consent logged", d))
            .catch(err => console.warn("[CookieGuard] Log failed", err));
        }}

        // render banner
        const host = document.createElement("div");
        host.style.position = "fixed";
        host.style.bottom = "20px";
        host.style.left = "50%";
        host.style.transform = "translateX(-50%)";
        host.style.zIndex = "9999";
        document.body.appendChild(host);

        const shadow = host.attachShadow({{ mode: "open" }});
        const style = document.createElement("style");
        style.textContent = `
            .cg-wrap {{
                background: ${{cfg.background_color}};
                color: ${{cfg.text_color || "#111827"}};
                border-radius: ${{cfg.border_radius_px}}px;
                padding: 12px 16px;
                text-align: ${{cfg.text_align}};
                font-family: system-ui,sans-serif;
                box-shadow: 0 4px 6px rgba(0,0,0,0.15);
                animation: cgFadeIn .3s ease;
            }}
            @keyframes cgFadeIn {{
                from {{ opacity: 0; transform: scale(.95); }}
                to {{ opacity: 1; transform: scale(1); }}
            }}
            .cg-title {{
                font-weight: 700;
                margin-bottom: 4px;
            }}
            .cg-desc {{
                margin-bottom: 10px;
                font-size: .95rem;
            }}
            .cg-buttons {{
                display: flex;
                gap: ${{cfg.spacing_px}}px;
                justify-content: center;
            }}
            .cg-btn {{
                cursor: pointer;
                padding: 8px 14px;
                border: none;
                border-radius: 6px;
                font-size: .9rem;
            }}
            .cg-accept {{
                background: ${{cfg.accept_bg_color}};
                color: ${{cfg.accept_text_color}};
            }}
            .cg-reject {{
                background: ${{cfg.reject_bg_color}};
                color: ${{cfg.reject_text_color}};
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
            </div>
        `;

        shadow.appendChild(style);
        shadow.appendChild(box);

        const acceptBtn = shadow.querySelector(".cg-accept");
        const rejectBtn = shadow.querySelector(".cg-reject");
        acceptBtn.onclick = () => {{ logConsent("accept_all"); host.remove(); }};
        rejectBtn.onclick = () => {{ logConsent("reject_all"); host.remove(); }};
    }})();"""

	# --- Return JSON with both JS and banner data ---
	return JsonResponse({
		"domain": domain.url,
		"user": user.email if user else None,
		"subscription_status": sub_status,
		"banner": banner_data,
		"script": js,
	})
