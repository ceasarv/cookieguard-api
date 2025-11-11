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
			'console.warn("[CookieGuard] Invalid embed key");',
			content_type="application/javascript",
		)

	user = domain.user
	if not user:
		return HttpResponse(
			'console.warn("[CookieGuard] Domain has no user");',
			content_type="application/javascript",
		)

	profile = BillingProfile.objects.filter(user=user).first()
	status = (profile.subscription_status or "").lower() if profile else "inactive"
	if status not in ("active", "trialing"):
		return HttpResponse(
			f'console.warn("[CookieGuard] Inactive subscription ({status})");',
			content_type="application/javascript",
		)

	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return HttpResponse(
			'console.warn("[CookieGuard] No active banner");',
			content_type="application/javascript",
		)

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
	}

	js = f"""
	(function() {{
		console.log("[CookieGuard] ✅ Banner loaded for {domain.url}");
		const cfg = {json.dumps(cfg)};
		const EMBED_KEY = "{embed_key}";
		const API_URL = "{API_URL}";

		function logConsent(choice, prefs=null) {{
			const body = {{
				embed_key: EMBED_KEY,
				banner_id: cfg.id,
				banner_version: 1,
				choice,
				preferences: prefs
			}};
			fetch(API_URL, {{
				method: "POST",
				headers: {{ "Content-Type": "application/json" }},
				body: JSON.stringify(body),
			}})
			.then(r => r.json())
			.then(d => console.log("[CookieGuard] consent logged", d))
			.catch(err => console.warn("[CookieGuard] log failed", err));
		}}

		// Build host
		const host = document.createElement("div");
		host.style.position = "fixed";
		host.style.bottom = "20px";
		host.style.left = "20px";
		host.style.zIndex = "9999";
		document.body.appendChild(host);
		const shadow = host.attachShadow({{mode:"open"}});

		const style = document.createElement("style");
		style.textContent = `
			.cg-wrap {{
				background: ${{cfg.background_color}};
				border-radius: ${{cfg.border_radius_px}}px;
				padding: 16px;
				max-width: 420px;
				font-family: system-ui,sans-serif;
				box-shadow: 0 4px 12px rgba(0,0,0,0.15);
			}}
			.cg-buttons {{
				display: flex;
				gap: ${{cfg.spacing_px}}px;
				justify-content: center;
				flex-wrap: wrap;
			}}
			.cg-btn {{
				cursor: pointer;
				padding: 8px 14px;
				border: none;
				border-radius: 6px;
				font-size: .9rem;
			}}
			.cg-accept {{ background: ${{cfg.accept_bg_color}}; color: ${{cfg.accept_text_color}}; }}
			.cg-reject {{ background: ${{cfg.reject_bg_color}}; color: ${{cfg.reject_text_color}}; }}
			.cg-prefs {{ background: ${{cfg.prefs_bg_color}}; color: ${{cfg.prefs_text_color}}; }}
			.cg-footer {{ margin-top: 8px; font-size: 11px; opacity: .6; text-align: right; }}
			.cg-footer a {{ color: inherit; text-decoration: none; }}
			.cg-footer a:hover {{ text-decoration: underline; opacity: 1; }}
			.cg-modal {{
				position: fixed;
				inset: 0;
				background: rgba(0,0,0,0.5);
				display: flex;
				align-items: center;
				justify-content: center;
				z-index: 999999;
			}}
			.cg-modal-content {{
				background: #fff;
				padding: 20px;
				border-radius: 10px;
				max-width: 400px;
				font-family: system-ui,sans-serif;
			}}
			.cg-toggle-row {{
				display: flex;
				justify-content: space-between;
				margin: 10px 0;
			}}
		`;

		const box = document.createElement("div");
		box.className = "cg-wrap";
		box.innerHTML = `
			<div class="cg-title" style="font-weight:700;margin-bottom:6px;">${{cfg.title}}</div>
			<div class="cg-desc" style="font-size:0.95rem;margin-bottom:${{cfg.spacing_px}}px;">${{cfg.description}}</div>
			<div class="cg-buttons">
				<button class="cg-btn cg-accept">${{cfg.accept_text}}</button>
				<button class="cg-btn cg-reject">${{cfg.reject_text}}</button>
				${{cfg.show_prefs ? `<button class="cg-btn cg-prefs">${{cfg.prefs_text}}</button>` : ""}}
			</div>
			${{cfg.show_logo ? `
			<div class="cg-footer">
				<a href='https://cookieguard.app' target='_blank' rel='noopener noreferrer'>
					Powered by CookieGuard
				</a>
			</div>` : ""}}
		`;

		shadow.appendChild(style);
		shadow.appendChild(box);

		const acceptBtn = shadow.querySelector(".cg-accept");
		const rejectBtn = shadow.querySelector(".cg-reject");
		const prefsBtn = shadow.querySelector(".cg-prefs");

		acceptBtn.onclick = () => {{ logConsent("accept_all"); host.remove(); }};
		rejectBtn.onclick = () => {{ logConsent("reject_all"); host.remove(); }};

		if (prefsBtn) {{
			prefsBtn.onclick = () => {{
				const modal = document.createElement("div");
				modal.className = "cg-modal";
				modal.innerHTML = `
					<div class="cg-modal-content">
						<h3>Cookie Preferences</h3>
						<div class="cg-toggle-row">
							<span>Necessary</span>
							<input type="checkbox" checked disabled />
						</div>
						<div class="cg-toggle-row">
							<span>Analytics</span>
							<input id="cg-analytics" type="checkbox" />
						</div>
						<div class="cg-toggle-row">
							<span>Marketing</span>
							<input id="cg-marketing" type="checkbox" />
						</div>
						<div style="margin-top:16px;text-align:right;">
							<button id="cg-save-prefs" class="cg-btn" style="background:#2563eb;color:#fff;">
								Save preferences
							</button>
						</div>
					</div>
				`;
				document.body.appendChild(modal);

				modal.querySelector("#cg-save-prefs").onclick = () => {{
					const prefs = {{
						analytics: modal.querySelector("#cg-analytics").checked,
						marketing: modal.querySelector("#cg-marketing").checked
					}};
					localStorage.setItem("cookieguard_prefs", JSON.stringify(prefs));
					logConsent("preferences_saved", prefs);
					modal.remove();
					host.remove();
				}};
			}};
		}}
	}})();
	"""

	return HttpResponse(js, content_type="application/javascript")
