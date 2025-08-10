from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import sync_and_async_middleware
from scanner.scan import scan_site
from scanner.tasks import run_scan_task
from rest_framework.decorators import api_view
from rest_framework.response import Response
from celery.result import AsyncResult
import json


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

		result = await scan_site(url)
		return JsonResponse(result, safe=False)

	except Exception as e:
		return JsonResponse({'error': str(e)}, status=500)


@api_view(["POST"])
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
