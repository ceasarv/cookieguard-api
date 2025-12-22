import csv
import json
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import F
from ipaddress import ip_address, IPv4Address, IPv6Address
from .models import ConsentLog
from .serializers import ConsentLogSerializer
from domains.models import Domain
from billing.models import UsageRecord
from billing.guards import get_user_plan, get_effective_pageview_limit, get_pageview_limit
from billing.permissions import CanExportCSV


def truncate_ip(ip_str: str) -> str:
	"""Return anonymized IP (e.g., 192.168.54.203 -> 192.168.54.0)."""
	if not ip_str:
		return ""
	try:
		ip_obj = ip_address(ip_str)
		if isinstance(ip_obj, IPv4Address):
			parts = ip_str.split(".")
			return ".".join(parts[:3] + ["0"])
		elif isinstance(ip_obj, IPv6Address):
			hextets = ip_str.split(":")
			return ":".join(hextets[:3]) + "::"
	except ValueError:
		pass
	return ip_str  # fallback if invalid format


@api_view(["POST"])
@permission_classes([AllowAny])
def log_consent(request):
	"""
	Logs a consent event from the embedded banner.
	Automatically links the correct domain via embed_key,
	captures anonymized IP & user agent, and maps choice aliases.
	"""
	data = request.data.copy()

	# 1️⃣ Find the domain via embed_key
	embed_key = data.get("embed_key")
	try:
		domain = Domain.objects.get(embed_key=embed_key)
		data["domain"] = domain.id
	except Domain.DoesNotExist:
		return Response(
			{"success": False, "error": "Invalid embed_key"},
			status=status.HTTP_400_BAD_REQUEST,
		)

	# 2️⃣ Rename banner_id -> banner for serializer
	if "banner_id" in data:
		data["banner"] = data.pop("banner_id")

	# 3️⃣ Map JS choice → model choice
	choice_map = {
		"accept_all": "accept",
		"reject_all": "reject",
		"preferences_opened": "prefs",
		"preferences_saved": "prefs",  # When user saves custom preferences
	}
	choice = data.get("choice")
	if choice in choice_map:
		data["choice"] = choice_map[choice]

	# 3.5️⃣ Map "preferences" to "categories" field
	if "preferences" in data:
		data["categories"] = data.pop("preferences")

	# 4️⃣ Capture IP + UA
	xff = request.META.get("HTTP_X_FORWARDED_FOR")
	real_ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
	data["truncated_ip"] = truncate_ip(real_ip)
	data["user_agent"] = request.META.get("HTTP_USER_AGENT", "")

	# 5️⃣ Timestamp
	data["created_at"] = timezone.now()

	# 6️⃣ Validate + save
	serializer = ConsentLogSerializer(data=data)
	if serializer.is_valid():
		log = serializer.save()
		return Response(
			{
				"success": True,
				"consent_id": str(log.consent_id),
				"choice": log.choice,
				"banner_id": log.banner_id,
				"domain": domain.url,
				"timestamp": log.created_at,
			},
			status=status.HTTP_201_CREATED,
		)

	return Response(
		{"success": False, "errors": serializer.errors},
		status=status.HTTP_400_BAD_REQUEST,
	)


@api_view(["GET"])
def list_consents(request):
	"""
	Returns consent logs for all domains owned by the logged-in user.
	Supports pagination and includes banner + domain info.
	"""
	domains = Domain.objects.filter(user=request.user)
	logs = ConsentLog.objects.filter(domain__in=domains).select_related("banner", "domain")

	# Optional filtering by domain or choice
	domain_id = request.query_params.get("domain")
	if domain_id:
		logs = logs.filter(domain_id=domain_id)

	choice = request.query_params.get("choice")
	if choice:
		logs = logs.filter(choice=choice)

	# Pagination
	paginator = PageNumberPagination()
	paginator.page_size = 50
	page = paginator.paginate_queryset(logs, request)

	data = [
		{
			"id": str(log.id),
			"domain": log.domain.url,
			"banner_name": log.banner.name if log.banner else None,
			"banner_version": log.banner_version,
			"choice": log.choice,
			"truncated_ip": log.truncated_ip,
			"user_agent": log.user_agent,
			"created_at": log.created_at,
		}
		for log in page
	]

	return paginator.get_paginated_response(data)


@api_view(["POST"])
@permission_classes([AllowAny])
def track_pageview(request):
	"""
	Track a pageview for usage metering.
	Called by embed.js on each page load.
	Pageviews are tracked per account (shared across all domains).
	"""
	embed_key = request.data.get("embed_key")
	if not embed_key:
		return Response(
			{"success": False, "error": "embed_key required"},
			status=status.HTTP_400_BAD_REQUEST,
		)

	try:
		domain = Domain.objects.select_related("user").get(embed_key=embed_key)
	except Domain.DoesNotExist:
		return Response(
			{"success": False, "error": "Invalid embed_key"},
			status=status.HTTP_400_BAD_REQUEST,
		)

	user = domain.user
	if not user:
		return Response({"success": False, "error": "Domain has no owner"}, status=status.HTTP_400_BAD_REQUEST)

	# Get or create this month's usage record (per account)
	today = timezone.now().date()
	month_start = today.replace(day=1)
	usage, _ = UsageRecord.objects.get_or_create(
		user=user,
		month=month_start,
		defaults={"pageviews": 0, "scans_used": 0}
	)

	# Increment pageviews atomically
	UsageRecord.objects.filter(pk=usage.pk).update(pageviews=F("pageviews") + 1)
	usage.refresh_from_db()

	# Check limits with 15% grace period
	plan = get_user_plan(user)
	base_limit = get_pageview_limit(user)
	effective_limit = get_effective_pageview_limit(user)

	over_soft_limit = usage.pageviews > base_limit
	over_hard_limit = usage.pageviews > effective_limit

	# Send warning email at 100% (first time only)
	if over_soft_limit and not usage.limit_warning_sent:
		usage.limit_warning_sent = True
		usage.save(update_fields=["limit_warning_sent"])
		# TODO: Trigger async email task
		# send_pageview_limit_warning.delay(user.id, usage.pageviews, base_limit)

	return Response({
		"success": True,
		"pageviews": usage.pageviews,
		"limit": base_limit,
		"over_limit": over_soft_limit,
		"blocked": over_hard_limit,
	})


@api_view(["GET"])
@permission_classes([CanExportCSV])
def export_consents_csv(request):
	"""
	Export consent logs as CSV.
	Requires Pro or Agency plan.
	"""
	domains = Domain.objects.filter(user=request.user)
	consents = ConsentLog.objects.filter(domain__in=domains).select_related("domain", "banner")

	# Optional filtering
	domain_id = request.query_params.get("domain")
	if domain_id:
		consents = consents.filter(domain_id=domain_id)

	response = HttpResponse(content_type="text/csv")
	response["Content-Disposition"] = 'attachment; filename="cookieguard_consents.csv"'

	writer = csv.writer(response)
	writer.writerow(["Date", "Domain", "Banner", "Choice", "Categories", "IP", "User Agent"])

	for c in consents:
		writer.writerow([
			c.created_at.isoformat(),
			c.domain.url,
			c.banner.name if c.banner else "",
			c.choice,
			json.dumps(c.categories) if c.categories else "",
			c.truncated_ip,
			c.user_agent,
		])

	return response
