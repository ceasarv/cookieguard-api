# domains/views.py
import re, secrets
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from .models import Domain, CookieCategory
from .serializers import CookieCategorySerializer
from billing.guards import get_user_plan, get_domain_limit, can_use_feature
from scanner.tasks import run_scan_task
from scanner.models import ScanResult

URL_RE = re.compile(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(:\d+)?(/.*)?$", re.I)


def _serialize(d: Domain):
	return {
		"id": str(d.id),
		"url": d.url,
		"embed_key": d.embed_key,
		"created_at": d.created_at.isoformat(),
		"updated_at": d.updated_at.isoformat(),
		"last_scan_at": d.last_scan_at.isoformat() if d.last_scan_at else None,
		"industry": d.industry,
		"is_ready": d.is_ready,
		"user": d.user_id and str(d.user_id),
		"created_by": d.created_by_id and str(d.created_by_id),
	}


def _get_owned(request, **kwargs) -> Domain:
	return get_object_or_404(Domain, user=request.user, **kwargs)


@extend_schema(
	methods=["GET"],
	responses={200: {"type": "array", "items": {"type": "object"}}},
	description="List all domains for the current user",
	tags=["Domains"]
)
@extend_schema(
	methods=["POST"],
	request={"application/json": {"type": "object", "properties": {"url": {"type": "string"}, "industry": {"type": "string"}}, "required": ["url"]}},
	responses={201: {"type": "object"}},
	description="Create a new domain",
	tags=["Domains"]
)
@api_view(["GET", "POST"])
def domains_list(request):
	if request.method == "GET":
		qs = Domain.objects.filter(user=request.user).order_by("-created_at")
		return Response([_serialize(d) for d in qs])

	# POST (create)
	# Check domain limit before creating
	current_count = Domain.objects.filter(user=request.user).count()
	domain_limit = get_domain_limit(request.user)
	plan = get_user_plan(request.user)

	if current_count >= domain_limit:
		return Response(
			{
				"detail": f"Your {plan.title()} plan allows {domain_limit} domain(s). Please upgrade to add more.",
				"code": "domain_limit_reached",
				"current": current_count,
				"limit": domain_limit,
			},
			status=status.HTTP_403_FORBIDDEN
		)

	url = (request.data.get("url") or "").strip().rstrip("/") or ""
	if not URL_RE.match(url):
		return Response({"url": ["Enter a valid URL like https://example.com"]}, status=400)

	industry = (request.data.get("industry") or "").strip()
	if industry and len(industry) > 120:
		return Response({"industry": ["Max length is 120 characters."]}, status=400)

	d = Domain.objects.create(
		user=request.user,
		created_by=request.user,
		url=url,
		industry=industry or None,
	)
	return Response(_serialize(d), status=status.HTTP_201_CREATED)


@extend_schema(
	methods=["GET"],
	responses={200: {"type": "object"}},
	description="Get domain details",
	tags=["Domains"]
)
@extend_schema(
	methods=["PATCH"],
	request={"application/json": {"type": "object", "properties": {"url": {"type": "string"}, "industry": {"type": "string"}, "is_ready": {"type": "boolean"}}}},
	responses={200: {"type": "object"}},
	description="Update domain",
	tags=["Domains"]
)
@extend_schema(
	methods=["DELETE"],
	responses={204: None},
	description="Delete domain",
	tags=["Domains"]
)
@api_view(["GET", "PATCH", "DELETE"])
def domain_detail(request, id):
	d = _get_owned(request, id=id)

	if request.method == "GET":
		return Response(_serialize(d))

	if request.method == "PATCH":
		updated_fields = []

		# url (optional)
		if "url" in request.data:
			url = (request.data.get("url") or "").strip().rstrip("/")
			if not url:
				return Response({"url": ["This field may not be blank."]}, status=400)
			if not URL_RE.match(url):
				return Response({"url": ["Enter a valid URL like https://example.com"]}, status=400)
			d.url = url
			updated_fields += ["url"]

		# industry (optional free text)
		if "industry" in request.data:
			industry = (request.data.get("industry") or "").strip()
			if not industry:
				return Response({"industry": ["This field may not be blank."]}, status=400)
			if len(industry) > 120:
				return Response({"industry": ["Max length is 120 characters."]}, status=400)
			d.industry = industry
			updated_fields += ["industry"]

		# mark ready toggle
		if "is_ready" in request.data:
			is_ready = bool(request.data.get("is_ready"))
			if is_ready and not d.industry:
				return Response({"detail": "Set industry before marking ready."}, status=400)
			d.is_ready = is_ready
			updated_fields += ["is_ready"]

		if updated_fields:
			updated_fields.append("updated_at")
			d.save(update_fields=updated_fields)

		return Response(_serialize(d))

	# DELETE
	d.delete()
	return Response(status=204)


@extend_schema(
	responses={200: {"type": "object", "properties": {"embed_key": {"type": "string"}}}},
	description="Rotate the embed key for a domain",
	tags=["Domains"]
)
@api_view(["POST"])
def rotate_key(request, id):
	d = _get_owned(request, id=id)
	d.embed_key = secrets.token_urlsafe(24)[:40]
	d.save(update_fields=["embed_key", "updated_at"])
	return Response({"embed_key": d.embed_key})


@extend_schema(
	responses={200: {"type": "object", "properties": {
		"status": {"type": "string"},
		"task_id": {"type": "string"},
		"last_scan_at": {"type": "string", "format": "date-time"}
	}}},
	description="Trigger a cookie scan for a domain. Returns a task_id to poll for results.",
	tags=["Domains"]
)
@api_view(["POST"])
def run_scan(request, id):
	"""
	Trigger a manual scan for the user's domain.
	Queues the scan via Celery and returns a task_id for polling.
	"""
	d = _get_owned(request, id=id)

	# Queue the scan via Celery with save_result=True to store in database
	task = run_scan_task.delay(
		d.url,
		domain_id=str(d.id),
		save_result=True,
	)

	d.last_scan_at = timezone.now()
	d.save(update_fields=["last_scan_at", "updated_at"])

	return Response({
		"status": "queued",
		"task_id": task.id,
		"last_scan_at": d.last_scan_at.isoformat(),
	})


@extend_schema(
	methods=["GET"],
	responses={200: {"type": "array", "items": {"type": "object"}}},
	description="List cookie categories for a domain",
	tags=["Domains"]
)
@extend_schema(
	methods=["POST"],
	responses={201: {"type": "object"}},
	description="Create a cookie category for a domain (Pro+ plan required)",
	tags=["Domains"]
)
@api_view(["GET", "POST"])
def cookie_categories_list(request, domain_id):
	"""List or create cookie categories for a domain"""
	domain = _get_owned(request, id=domain_id)

	if request.method == "GET":
		categories = CookieCategory.objects.filter(domain=domain).order_by("category", "script_name")
		serializer = CookieCategorySerializer(categories, many=True)
		return Response(serializer.data)

	# POST - create new category (requires Pro+ plan)
	if not can_use_feature(request.user, "cookie_categorization"):
		return Response(
			{
				"detail": "Cookie categorization requires a Pro or Agency plan.",
				"code": "feature_not_available",
			},
			status=status.HTTP_403_FORBIDDEN
		)

	serializer = CookieCategorySerializer(data=request.data)
	if serializer.is_valid():
		serializer.save(domain=domain)
		return Response(serializer.data, status=status.HTTP_201_CREATED)
	return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
	methods=["GET"],
	responses={200: {"type": "object"}},
	description="Get cookie category details",
	tags=["Domains"]
)
@extend_schema(
	methods=["PATCH"],
	responses={200: {"type": "object"}},
	description="Update a cookie category (Pro+ plan required)",
	tags=["Domains"]
)
@extend_schema(
	methods=["DELETE"],
	responses={204: None},
	description="Delete a cookie category (Pro+ plan required)",
	tags=["Domains"]
)
@api_view(["GET", "PATCH", "DELETE"])
def cookie_category_detail(request, domain_id, category_id):
	"""Retrieve, update, or delete a cookie category"""
	domain = _get_owned(request, id=domain_id)
	category = get_object_or_404(CookieCategory, id=category_id, domain=domain)

	if request.method == "GET":
		serializer = CookieCategorySerializer(category)
		return Response(serializer.data)

	# PATCH and DELETE require Pro+ plan
	if not can_use_feature(request.user, "cookie_categorization"):
		return Response(
			{
				"detail": "Cookie categorization requires a Pro or Agency plan.",
				"code": "feature_not_available",
			},
			status=status.HTTP_403_FORBIDDEN
		)

	if request.method == "PATCH":
		serializer = CookieCategorySerializer(category, data=request.data, partial=True)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	# DELETE
	category.delete()
	return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
	responses={200: {"type": "object", "properties": {
		"scans": {"type": "array"},
		"total": {"type": "integer"}
	}}},
	description="Get scan history for a domain",
	tags=["Domains"]
)
@api_view(["GET"])
def scan_history(request, id):
	"""Get all past scans for a domain with summary info."""
	d = _get_owned(request, id=id)

	scans = ScanResult.objects.filter(domain=d).order_by("-scanned_at")[:50]

	return Response({
		"scans": [
			{
				"id": str(scan.id),
				"url": scan.url,
				"scanned_at": scan.scanned_at.isoformat(),
				"cookies_found": scan.cookies_found,
				"first_party_count": scan.first_party_count,
				"third_party_count": scan.third_party_count,
				"tracker_count": scan.tracker_count,
				"unclassified_count": scan.unclassified_count,
				"compliance_score": scan.compliance_score,
				"has_consent_banner": scan.has_consent_banner,
				"pages_scanned": scan.pages_scanned,
				"duration": scan.duration,
				"issues_count": len(scan.issues) if scan.issues else 0,
			}
			for scan in scans
		],
		"total": scans.count(),
	})


@extend_schema(
	responses={200: {"type": "object"}},
	description="Get the latest scan result with full cookie data for a domain",
	tags=["Domains"]
)
@api_view(["GET"])
def latest_scan(request, id):
	"""Get the most recent scan result with full cookie details."""
	d = _get_owned(request, id=id)

	scan = ScanResult.objects.filter(domain=d).first()
	if not scan:
		return Response({"error": "No scans found for this domain"}, status=404)

	# Get cookies with their classifications
	cookies = scan.cookies.all()
	cookies_data = [
		{
			"id": cookie.id,
			"name": cookie.name,
			"domain": cookie.domain,
			"path": cookie.path,
			"expires": cookie.expires,
			"type": cookie.type,
			"category": cookie.get_effective_category(),
			"classification": cookie.classification,
			"user_category": cookie.user_category,
			"user_description": cookie.user_description,
			"has_definition": cookie.definition is not None,
			"definition_confidence": cookie.definition.classification_confidence if cookie.definition else 0,
			"provider": cookie.definition.provider if cookie.definition else None,
		}
		for cookie in cookies
	]

	return Response({
		"id": str(scan.id),
		"url": scan.url,
		"scanned_at": scan.scanned_at.isoformat(),
		"cookies_found": scan.cookies_found,
		"first_party_count": scan.first_party_count,
		"third_party_count": scan.third_party_count,
		"tracker_count": scan.tracker_count,
		"unclassified_count": scan.unclassified_count,
		"compliance_score": scan.compliance_score,
		"has_consent_banner": scan.has_consent_banner,
		"pages_scanned": scan.pages_scanned,
		"duration": scan.duration,
		"issues": scan.issues,
		"cookies": cookies_data,
	})
