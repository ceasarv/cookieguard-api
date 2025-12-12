from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import sync_and_async_middleware
from scanner.scan import scan_site
from scanner.tasks import run_scan_task
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from billing.permissions import HasPaidPlan
from celery.result import AsyncResult
import json, os, resend

from users.permissions import NotBlocked


@sync_and_async_middleware
@csrf_exempt
async def scan_view(request):
	if request.method != 'POST':
		return JsonResponse({'error': 'POST required'}, status=405)

	try:
		body = json.loads(request.body)
		url = body.get("url")
		if not url:
			return JsonResponse({'error': 'Missing URL'}, status=400)

		# 🕵️‍♂️ Send an email right away when a scan starts (before or after running)
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
			print("[Scan Email Error ❌]", email_err)

		# 🚀 Proceed with scan
		result = await scan_site(url)
		return JsonResponse(result, safe=False)

	except Exception as e:
		error_message = str(e)
		print("[SCAN ERROR]", error_message)

		# 💌 Still send an email for failed scan
		try:
			resend.api_key = os.environ.get("RESEND_API_KEY")
			sender_email = "support@resend.dev"
			receiver_email = os.environ.get("EMAIL_RECEIVER")

			subject = f"[Scan Failed] {url}"
			html_body = f"""
				<h2>Scan Failed</h2>
				<p><strong>URL:</strong> {url}</p>
				<p><strong>Error:</strong> {error_message}</p>
			"""

			resend.Emails.send({
				"from": sender_email,
				"to": receiver_email,
				"subject": subject,
				"html": html_body,
			})

			print(f"[Scan Error Email Sent] for {url}")

		except Exception as email_err:
			print("[Scan Error Email Error ❌]", email_err)

		return JsonResponse({'error': error_message}, status=500)


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

	opts = {
		"max_pages": int(data.get("max_pages", 20)),
		"max_depth": int(data.get("max_depth", 2)),
		"include_subdomains": bool(data.get("include_subdomains", False)),
		"dual_pass": bool(data.get("dual_pass", False)),
	}
	task = run_scan_task.delay(url, **opts)
	return Response({"task_id": task.id})


@api_view(["GET"])
def scan_status(request, task_id):
	result = AsyncResult(task_id)
	return Response({
		"status": result.status,
		"result": result.result if result.ready() else None
	})
