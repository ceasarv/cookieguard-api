# domains/views.py
import re, secrets
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Domain, CookieCategory
from .serializers import CookieCategorySerializer
from billing.guards import get_user_plan, get_domain_limit, can_use_feature

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


@api_view(["POST"])
def rotate_key(request, id):
	d = _get_owned(request, id=id)
	d.embed_key = secrets.token_urlsafe(24)[:40]
	d.save(update_fields=["embed_key", "updated_at"])
	return Response({"embed_key": d.embed_key})


@api_view(["POST"])
def run_scan(request, id):
	d = _get_owned(request, id=id)
	d.last_scan_at = timezone.now()
	d.save(update_fields=["last_scan_at", "updated_at"])
	return Response({"status": "queued", "last_scan_at": d.last_scan_at})


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
