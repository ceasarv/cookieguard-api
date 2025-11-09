from django.http import HttpResponse
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from .models import Banner
from .serializers import BannerSerializer
from domains.models import Domain
from django.conf import settings
import logging, json, random

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
	try:
		domain = Domain.objects.get(embed_key=embed_key)
	except Domain.DoesNotExist:
		log.warning(f"[EmbedScript] ❌ Domain not found for key={embed_key}")
		return HttpResponse(
			"// CookieGuard: domain not found\n",
			content_type="application/javascript",
			status=200,
		)

	user = domain.user
	if not user:
		log.warning(f"[EmbedScript] ❌ Domain {domain.id} has no associated user")
		return HttpResponse("// CookieGuard: no user assigned\n", content_type="application/javascript")

	has_sub = getattr(user, "has_active_subscription", None)
	if not has_sub:
		log.warning(f"[EmbedScript] ⚠️ User {user.email} has_active_subscription={has_sub!r}")
		try:
			from billing.models import BillingProfile
			bp = BillingProfile.objects.filter(user=user).first()
			if bp:
				log.warning(
					f"[EmbedScript] BillingProfile: status={bp.subscription_status}, "
					f"ends={bp.current_period_end}, cancel={bp.cancel_at_period_end}"
				)
			else:
				log.warning("[EmbedScript] No BillingProfile found for user")
		except Exception as e:
			log.error(f"[EmbedScript] BillingProfile lookup failed: {e}")

		return HttpResponse("// CookieGuard: inactive subscription\n", content_type="application/javascript")

	banners = list(domain.banners.filter(is_active=True))
	if not banners:
		log.warning(f"[EmbedScript] ⚠️ Domain {domain.id} has no active banners")
		return HttpResponse("// CookieGuard: no active banner\n", content_type="application/javascript")

	banner = random.choice(banners)
	env = getattr(settings, "DJANGO_ENV", "production")
	API_URL = (
		"http://127.0.0.1:8000/api/consents/create/"
		if env == "development"
		else "https://api.cookieguard.app/api/consents/create/"
	)

	# --- Build the working banner JS ---
	html = f"""
        <div class="cg-title">{banner.title}</div>
        <div class="cg-desc">{banner.description}</div>
        <div class="cg-buttons">
            <button class="cg-btn cg-accept">{banner.accept_text}</button>
        </div>
    """
	cfg = {
		"id": banner.id,
		"version": banner.version,
		"title": banner.title,
		"description": banner.description,
	}

	js = f"""
    (function(){{
        console.log("[CookieGuard] Banner loaded for {domain.url}");
        const cfg = {json.dumps(cfg)};
        const API_URL = "{API_URL}";
        // your normal banner logic here...
    }})();
    """

	log.info(f"[EmbedScript] ✅ Served banner for {domain.url} ({user.email})")
	return HttpResponse(js, content_type="application/javascript")
