from django.http import Http404, HttpResponse
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError
from .models import Banner
from .serializers import BannerSerializer
from domains.models import Domain
import random
import json
from django.conf import settings


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
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		raise Http404("Domain not found")

	# Verify user has an active subscription
	user = domain.user
	if not getattr(user, "has_active_subscription", False):
		raise Http404("Inactive or free account — banner disabled")

	banners = list(domain.banners.filter(is_active=True))
	if not banners:
		raise Http404("No banner configured for this domain")

	banner = random.choice(banners)

	# 🔧 Switch API URL based on DJANGO_ENV
	env = getattr(settings, "DJANGO_ENV", "production")
	if env == "development":
		API_URL = "http://127.0.0.1:8000/api/consents/create/"
	else:
		API_URL = "https://cookieguard.app/api/consents/create/"

	# ✅ Build button HTML server-side (so f-strings are evaluated correctly)
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

	# ✅ Config payload for JS
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
		"accept_border_color": banner.accept_border_color,
		"accept_border_width_px": banner.accept_border_width_px,
		"accept_border_radius_px": banner.accept_border_radius_px,
		"reject_border_color": banner.reject_border_color,
		"reject_border_width_px": banner.reject_border_width_px,
		"reject_border_radius_px": banner.reject_border_radius_px,
		"prefs_border_color": banner.prefs_border_color,
		"prefs_border_width_px": banner.prefs_border_width_px,
		"prefs_border_radius_px": banner.prefs_border_radius_px,
		"show_cookieguard_logo": banner.show_cookieguard_logo,
		"padding_x_px": banner.padding_x_px,
		"padding_y_px": banner.padding_y_px,
		"spacing_px": banner.spacing_px,
		"text_align": banner.text_align,
		"z_index": banner.z_index,
		"overlay_enabled": banner.overlay_enabled,
		"overlay_color": banner.overlay_color,
		"overlay_opacity": banner.overlay_opacity,
		"overlay_blur_px": banner.overlay_blur_px,
		"width": banner.width or "",
		"height": banner.height or "",
	}

	# ✅ The generated JS script
	js = f"""
	(function() {{
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
			.then(res => res.json())
			.then(data => {{
				console.log("[CookieGuard] Consent logged:", data);
				if (data.consent_id) {{
					localStorage.setItem("cookieguard_consent_id", data.consent_id);
					localStorage.setItem("cookieguard_choice", choice);
				}}
			}})
			.catch(err => console.warn("Consent log failed:", err));
		}}

		// 🧱 Create modal container
		const host = document.createElement("div");
		host.style.position = "fixed";
		host.style.top = "50%";
		host.style.left = "50%";
		host.style.transform = "translate(-50%, -50%)";
		host.style.zIndex = cfg.z_index || 10;
		document.body.appendChild(host);

		const shadow = host.attachShadow({{ mode: "open" }});

		const style = document.createElement("style");
		style.textContent = `
			:host {{ all: initial; }}
			.cg-wrap {{
				position: relative;
				background: {banner.background_color};
				border: {banner.border_width_px}px solid {banner.border_color};
				border-radius: {banner.border_radius_px}px;
				padding: {banner.padding_y_px}px {banner.padding_x_px}px;
				text-align: {banner.text_align};
				font-family: system-ui, sans-serif;
				line-height: 1.45;
				max-width: 520px;
				animation: cgFadeIn 0.3s ease;
			}}
			@keyframes cgFadeIn {{
				from {{ opacity: 0; transform: scale(0.96); }}
				to {{ opacity: 1; transform: scale(1); }}
			}}
			.cg-title {{
				font-size: 1.125rem;
				font-weight: 700;
				margin-bottom: 6px;
			}}
			.cg-desc {{
				font-size: .95rem;
				margin-bottom: {banner.spacing_px}px;
			}}
			.cg-buttons {{
				display: flex;
				gap: {banner.spacing_px}px;
				flex-wrap: wrap;
				justify-content: {"center" if banner.text_align == "center" else "flex-end" if banner.text_align == "right" else "flex-start"};
			}}
			.cg-btn {{
				font-size: .95rem;
				padding: 8px 14px;
				cursor: pointer;
				transition: opacity .15s ease, transform .05s ease;
			}}
			.cg-btn:active {{ transform: scale(.97); }}
			.cg-accept {{
				background: {banner.accept_bg_color};
				color: {banner.accept_text_color};
				border: {banner.accept_border_width_px}px solid {banner.accept_border_color};
				border-radius: {banner.accept_border_radius_px}px;
			}}
			.cg-reject {{
				background: {banner.reject_bg_color};
				color: {banner.reject_text_color};
				border: {banner.reject_border_width_px}px solid {banner.reject_border_color};
				border-radius: {banner.reject_border_radius_px}px;
			}}
			.cg-prefs {{
				background: {banner.prefs_bg_color};
				color: {banner.prefs_text_color};
				border: {banner.prefs_border_width_px}px solid {banner.prefs_border_color};
				border-radius: {banner.prefs_border_radius_px}px;
			}}
			.cg-footer {{
				position: absolute;
				bottom: 4px;
				right: 8px;
				font-size: 11px;
				opacity: .6;
			}}
			.cg-footer a {{
				color: inherit;
				text-decoration: none;
			}}
			.cg-footer a:hover {{
				opacity: 1;
				text-decoration: underline;
			}}
		`;

		const box = document.createElement("div");
		box.className = "cg-wrap";
		box.innerHTML = `{html}`;

		if (cfg.show_cookieguard_logo) {{
			box.innerHTML += `
				<div class="cg-footer">
					<a href='https://cookieguard.app' target='_blank' rel='noopener noreferrer'>
						Powered&nbsp;by&nbsp;CookieGuard
					</a>
				</div>`;
		}}

		if (cfg.width) {{
			box.style.width = cfg.width;
			box.style.maxWidth = cfg.width;
		}}
		if (cfg.height) box.style.height = cfg.height;

		shadow.appendChild(style);
		shadow.appendChild(box);

		if (cfg.overlay_enabled) {{
			const overlay = document.createElement("div");
			overlay.id = "cookieguard-overlay-" + cfg.id;
			overlay.style.position = "fixed";
			overlay.style.inset = "0";
			overlay.style.background = cfg.overlay_color || "#000";
			overlay.style.opacity = cfg.overlay_opacity ?? 0.3;
			overlay.style.backdropFilter = "blur(" + (cfg.overlay_blur_px || 0) + "px)";
			overlay.style.zIndex = (cfg.z_index || 10) - 1;
			document.body.appendChild(overlay);
		}}

		const acceptBtn = shadow.querySelector(".cg-accept");
		const rejectBtn = shadow.querySelector(".cg-reject");
		const prefsBtn  = shadow.querySelector(".cg-prefs");

		const cleanup = () => {{
			host.remove();
			const ov = document.querySelector("#cookieguard-overlay-" + cfg.id);
			if (ov) ov.remove();
		}};

		if (acceptBtn) acceptBtn.addEventListener("click", () => {{ logConsent("accept_all"); cleanup(); }});
		if (rejectBtn) rejectBtn.addEventListener("click", () => {{ logConsent("reject_all"); cleanup(); }});
		if (prefsBtn)  prefsBtn.addEventListener("click", () => {{ logConsent("preferences_opened"); }});
	}})();
	"""

	return HttpResponse(js, content_type="application/javascript")
