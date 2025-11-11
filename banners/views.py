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

	profile = BillingProfile.objects.filter(user=user).first()
	if not profile or (profile.subscription_status or "").lower() not in ("active", "trialing"):
		return _js("Inactive or free account — banner disabled.")

	banner = domain.banners.filter(is_active=True).first()
	if not banner:
		return _js("No active banner configured for this domain.")

	# 🔒 unique namespace ID
	unique_id = f"cg-{hashlib.md5(embed_key.encode()).hexdigest()[:6]}"

	env = getattr(settings, "DJANGO_ENV", "production")
	API_URL = (
		"http://127.0.0.1:8000/api/consents/create/"
		if env == "development"
		else "https://api.cookieguard.app/api/consents/create/"
	)

	# optional hosted stylesheet (so you can push design tweaks later)
	base_css_url = (
		"http://127.0.0.1:8000/static/banner-base.css"
		if env == "development"
		else "https://api.cookieguard.app/static/banner-base.css"
	)

	js = f"""
    (function() {{
        const ROOT_ID = "{unique_id}";
        const API_URL = "{API_URL}";
        const EMBED_KEY = "{embed_key}";
        const cfg = {json.dumps({
		"title": banner.title,
		"description": banner.description,
		"accept_text": banner.accept_text,
		"accept_bg": banner.accept_bg_color,
		"accept_color": banner.accept_text_color,
		"bg": banner.background_color,
		"z": banner.z_index,
	})};

        // inject stylesheet
        if (!document.getElementById(ROOT_ID + "-style")) {{
            const link = document.createElement("link");
            link.id = ROOT_ID + "-style";
            link.rel = "stylesheet";
            link.href = "{base_css_url}";
            document.head.appendChild(link);
        }}

        // render container
        const root = document.createElement("div");
        root.id = ROOT_ID;
        root.className = "cookieguard-banner";
        root.style.position = "fixed";
        root.style.bottom = "20px";
        root.style.left = "20px";
        root.style.zIndex = cfg.z || 9999;
        document.body.appendChild(root);

        // build banner HTML
        root.innerHTML = `
            <div class="cg-wrap" style="background:${{cfg.bg}};color:#fff;padding:12px 18px;border-radius:10px;max-width:480px;">
                <div class="cg-title">${{cfg.title}}</div>
                <div class="cg-desc" style="font-size:.9rem;margin-bottom:10px;">${{cfg.description}}</div>
                <button class="cg-btn cg-accept" style="background:${{cfg.accept_bg}};color:${{cfg.accept_color}};padding:8px 14px;border-radius:6px;">${{cfg.accept_text}}</button>
            </div>
        `;

        // log consent
        const btn = root.querySelector(".cg-accept");
        btn.addEventListener("click", () => {{
            fetch(API_URL, {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{
                    embed_key: EMBED_KEY,
                    banner_id: {banner.id},
                    banner_version: {banner.version},
                    choice: "accept_all",
                }}),
            }});
            root.remove();
        }});
    }})();"""

	return HttpResponse(js, content_type="application/javascript")
