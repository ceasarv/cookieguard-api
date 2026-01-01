from scanner.tasks import run_scan_task
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from billing.permissions import HasPaidPlan
from celery.result import AsyncResult
from drf_spectacular.utils import extend_schema
from django.conf import settings
from django.http import Http404
import os, resend
from urllib.parse import urlparse

from users.permissions import NotBlocked

# Blocked domains - social media, adult sites, and other popular sites we don't allow scanning
BLOCKED_DOMAINS = [
	# Social media
	"reddit.com",
	"twitter.com",
	"x.com",
	"facebook.com",
	"fb.com",
	"instagram.com",
	"tiktok.com",
	"snapchat.com",
	"linkedin.com",
	"pinterest.com",
	"tumblr.com",
	"discord.com",
	"twitch.tv",
	"youtube.com",
	"whatsapp.com",
	"telegram.org",
	"t.me",
	# Gaming
	"roblox.com",
	"steam.com",
	"steampowered.com",
	"epicgames.com",
	"xbox.com",
	"playstation.com",
	# Adult sites
	"pornhub.com",
	"xvideos.com",
	"xnxx.com",
	"xhamster.com",
	"onlyfans.com",
	"chaturbate.com",
	"stripchat.com",
	# Other major platforms
	"google.com",
	"amazon.com",
	"apple.com",
	"microsoft.com",
	"netflix.com",
	"spotify.com",
	"github.com",
	"gitlab.com",
]

def is_blocked_url(url: str) -> bool:
	"""Check if a URL belongs to a blocked domain."""
	try:
		parsed = urlparse(url)
		hostname = parsed.netloc.lower()
		# Remove www. prefix if present
		if hostname.startswith("www."):
			hostname = hostname[4:]
		# Check if hostname matches or is a subdomain of any blocked domain
		for blocked in BLOCKED_DOMAINS:
			if hostname == blocked or hostname.endswith("." + blocked):
				return True
		return False
	except Exception:
		return False


@extend_schema(
	request={"application/json": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
	responses={200: {"type": "object", "properties": {"task_id": {"type": "string"}}}},
	description="Public scan endpoint - queues a cookie scan and returns a task_id to poll for results",
	tags=["Scanner"]
)
@api_view(["POST"])
@permission_classes([AllowAny])
def scan_view(request):
	"""Public scan endpoint - queues scan via Celery and returns task_id."""
	url = request.data.get("url")
	if not url:
		return Response({'error': 'Missing URL'}, status=400)

	# Normalize URL
	if not url.startswith(("http://", "https://")):
		url = f"https://{url}"

	# Check if URL is blocked
	if is_blocked_url(url):
		return Response({'error': 'This domain cannot be scanned. Social media, gaming platforms, and other major sites are not supported.'}, status=403)

	# Send notification email (only in production)
	if not settings.DEBUG:
		try:
			resend.api_key = os.environ.get("RESEND_API_KEY")
			sender_email = "support@resend.dev"
			receiver_email = os.environ.get("EMAIL_RECEIVER")

			subject = f"[Scan Attempt] {url}"
			html_body = f"""
				<h2>New Scan Attempt</h2>
				<p><strong>URL:</strong> {url}</p>
				<p>This scan was just triggered via the public endpoint.</p>
			"""

			resend.Emails.send({
				"from": sender_email,
				"to": receiver_email,
				"subject": subject,
				"html": html_body,
			})

			print(f"[Scan Email Sent] Notified for {url}")

		except Exception as email_err:
			print("[Scan Email Error]", email_err)

	# Queue scan via Celery
	task = run_scan_task.delay(url)
	return Response({'task_id': task.id})


@extend_schema(
	request={"application/json": {"type": "object", "properties": {
		"url": {"type": "string"},
		"max_pages": {"type": "integer"},
		"max_depth": {"type": "integer"},
		"include_subdomains": {"type": "boolean"},
		"dual_pass": {"type": "boolean"}
	}, "required": ["url"]}},
	responses={200: {"type": "object", "properties": {"task_id": {"type": "string"}}}},
	description="Trigger a cookie scan for authenticated users (paid plan required)",
	tags=["Scanner"]
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, NotBlocked, HasPaidPlan])
def trigger_scan(request):
	data = request.data or {}
	url = data.get("url")
	if not url:
		return Response({"error": "URL required"}, status=400)

	# normalize
	if not url.startswith(("http://", "https://")):
		url = f"https://{url}"

	# Check if URL is blocked
	if is_blocked_url(url):
		return Response({"error": "This domain cannot be scanned. Social media, gaming platforms, and other major sites are not supported."}, status=403)

	opts = {
		"max_pages": int(data.get("max_pages", 20)),
		"max_depth": int(data.get("max_depth", 2)),
		"include_subdomains": bool(data.get("include_subdomains", False)),
		"dual_pass": bool(data.get("dual_pass", False)),
	}
	task = run_scan_task.delay(url, **opts)
	return Response({"task_id": task.id})


@extend_schema(
	responses={200: {"type": "object", "properties": {
		"status": {"type": "string"},
		"result": {"type": "object", "nullable": True}
	}}},
	description="Get the status and result of a scan task",
	tags=["Scanner"]
)
@api_view(["GET"])
@permission_classes([AllowAny])
def scan_status(request, task_id):
	result = AsyncResult(task_id)
	return Response({
		"status": result.status,
		"result": result.result if result.ready() else None
	})


# Cookie Classification API
from django.db import models
from scanner.models import Cookie, CookieDefinition
from domains.models import Domain


@extend_schema(
	responses={200: {"type": "object", "properties": {
		"cookies": {"type": "array"},
		"total": {"type": "integer"}
	}}},
	description="Get cookies for a domain with their classifications",
	tags=["Cookies"]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, NotBlocked])
def domain_cookies(request, domain_id):
	"""Get all cookies found for a domain across all scans."""
	try:
		domain = Domain.objects.get(id=domain_id, user=request.user)
	except Domain.DoesNotExist:
		return Response({"error": "Domain not found"}, status=404)

	# Get unique cookies from the most recent scan
	latest_scan = domain.scan_results.first()
	if not latest_scan:
		return Response({"cookies": [], "total": 0})

	cookies = latest_scan.cookies.all()
	cookies_data = []
	for cookie in cookies:
		cookies_data.append({
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
		})

	return Response({
		"cookies": cookies_data,
		"total": len(cookies_data),
		"scan_id": str(latest_scan.id),
		"scanned_at": latest_scan.scanned_at.isoformat(),
	})


@extend_schema(
	request={"application/json": {"type": "object", "properties": {
		"category": {"type": "string", "enum": ["necessary", "functional", "analytics", "marketing", "other"]},
		"description": {"type": "string"}
	}, "required": ["category"]}},
	responses={200: {"type": "object", "properties": {"success": {"type": "boolean"}}}},
	description="Classify a cookie - sets user override and contributes to crowdsourced database",
	tags=["Cookies"]
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, NotBlocked])
def classify_cookie(request, cookie_id):
	"""
	Classify a cookie for a user's domain.
	Also contributes to the crowdsourced cookie database.
	"""
	try:
		cookie = Cookie.objects.select_related('scan__domain', 'definition').get(id=cookie_id)
	except Cookie.DoesNotExist:
		return Response({"error": "Cookie not found"}, status=404)

	# Verify ownership
	if cookie.scan.domain and cookie.scan.domain.user != request.user:
		return Response({"error": "Not authorized"}, status=403)

	category = request.data.get("category")
	description = request.data.get("description", "")

	if category not in ["necessary", "functional", "analytics", "marketing", "other"]:
		return Response({"error": "Invalid category"}, status=400)

	# Set user override
	cookie.user_category = category
	cookie.user_description = description
	cookie.save()

	# Contribute to crowdsourced database
	if cookie.definition:
		# Add vote to existing definition
		cookie.definition.add_classification_vote(category)
	else:
		# Create new definition and vote for it
		definition, created = CookieDefinition.get_or_create_from_cookie(
			cookie.name,
			cookie.domain
		)
		definition.add_classification_vote(category)
		# Link cookie to the new definition
		cookie.definition = definition
		cookie.save(update_fields=['definition'])

	return Response({
		"success": True,
		"cookie_id": cookie.id,
		"category": category,
		"contributed_to_database": True,
	})


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def serve_screenshot(request, filename):
	"""Serve screenshot from Redis (public, no auth needed)."""
	from scanner.scan import get_screenshot_from_redis
	from django.http import HttpResponse

	# Security: only allow UUID format, no path traversal
	if '/' in filename or '\\' in filename:
		raise Http404("Screenshot not found")

	# Remove .jpg extension if present
	screenshot_id = filename.replace('.jpg', '')

	screenshot_bytes = get_screenshot_from_redis(screenshot_id)
	if not screenshot_bytes:
		raise Http404("Screenshot not found or expired")

	return HttpResponse(
		screenshot_bytes,
		content_type='image/jpeg',
		headers={
			'Cache-Control': 'public, max-age=300',  # Cache for 5 minutes
		}
	)


@extend_schema(
	responses={200: {"type": "object", "properties": {
		"definitions": {"type": "array"},
		"total": {"type": "integer"}
	}}},
	description="Get known cookie definitions from the shared database",
	tags=["Cookies"]
)
@api_view(["GET"])
@permission_classes([AllowAny])
def cookie_definitions(request):
	"""
	Public endpoint to browse the cookie database.
	Useful for showing users what cookies are known/classified.
	"""
	search = request.query_params.get("search", "")
	category = request.query_params.get("category", "")
	page = int(request.query_params.get("page", 1))
	per_page = int(request.query_params.get("per_page", 50))

	queryset = CookieDefinition.objects.all()

	if search:
		queryset = queryset.filter(name__icontains=search)
	if category:
		queryset = queryset.filter(category=category)

	# Only show definitions with some confidence or that are verified
	queryset = queryset.filter(
		models.Q(classification_confidence__gte=0.5) |
		models.Q(is_verified=True) |
		models.Q(times_seen__gte=3)
	)

	total = queryset.count()
	start = (page - 1) * per_page
	definitions = queryset[start:start + per_page]

	data = []
	for d in definitions:
		data.append({
			"id": d.id,
			"name": d.name,
			"domain_pattern": d.domain_pattern,
			"category": d.category,
			"description": d.description,
			"provider": d.provider,
			"times_seen": d.times_seen,
			"confidence": round(d.classification_confidence, 2),
			"is_verified": d.is_verified,
		})

	return Response({
		"definitions": data,
		"total": total,
		"page": page,
		"per_page": per_page,
	})
