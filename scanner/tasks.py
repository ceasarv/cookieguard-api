# scanner/tasks.py
from celery import shared_task
import asyncio
import logging
from django.utils import timezone
from scanner.scan import scan_site  # single-page scan
from scanner.crawler import crawl_site  # multi-page crawl

log = logging.getLogger(__name__)


def _run_async(coro):
	"""
	Safely run an async coroutine from a Celery (sync) worker thread.
	Handles missing/closed event loops (common on Windows).
	"""
	try:
		loop = asyncio.get_event_loop()
		if loop.is_closed():
			raise RuntimeError("Event loop is closed")
	except RuntimeError:
		loop = asyncio.new_event_loop()
		asyncio.set_event_loop(loop)
	return loop.run_until_complete(coro)


@shared_task(
	bind=True,
	autoretry_for=(Exception,),
	retry_kwargs={"max_retries": 2, "countdown": 5},
)
def run_scan_task(
		self,
		url: str,
		mode: str = "single",  # "single" or "crawl"
		max_pages: int = 20,
		max_depth: int = 2,
		include_subdomains: bool = False,
		dual_pass: bool = False,
		pause_ms_between_pages: int = 400,
):
	"""
	Celery entrypoint for scans.

	mode="single"  -> scanner.scan.scan_site(url)
	mode="crawl"   -> scanner.crawler.crawl_site(url, ...)

	Returns a JSON-serializable dict suitable for sending to the frontend.
	"""
	if not url:
		return {"error": "URL required"}

	if not url.startswith(("http://", "https://")):
		url = f"https://{url}"

	if mode == "crawl":
		return _run_async(
			crawl_site(
				url=url,
				max_pages=max_pages,
				max_depth=max_depth,
				include_subdomains=include_subdomains,
				dual_pass=dual_pass,
				pause_ms_between_pages=pause_ms_between_pages,
			)
		)
	else:
		# default: single-page scan
		return _run_async(scan_site(url))


@shared_task
def run_scheduled_scans(frequency: str):
	"""
	Run auto-scans for users whose plan includes this scan frequency.

	Args:
		frequency: "daily" for Agency plan, "weekly" for Pro plan
	"""
	from billing.plans import PLAN_LIMITS
	from domains.models import Domain

	# Find plans that have this scan frequency
	eligible_plans = [
		plan for plan, limits in PLAN_LIMITS.items()
		if limits.get("auto_scan") == frequency
	]

	if not eligible_plans:
		log.info(f"No plans with auto_scan={frequency}")
		return {"scanned": 0}

	# Get all domains for users on those plans with active subscriptions
	domains = Domain.objects.filter(
		user__billing_profile__plan_tier__in=eligible_plans,
		user__billing_profile__subscription_status__in=["active", "trialing"]
	).select_related("user")

	scanned_count = 0
	for domain in domains:
		try:
			# Queue scan for this domain
			run_scan_task.delay(domain.url)
			domain.last_scan_at = timezone.now()
			domain.save(update_fields=["last_scan_at"])
			scanned_count += 1
			log.info(f"Queued auto-scan for {domain.url} (user: {domain.user.email})")
		except Exception as e:
			log.error(f"Failed to queue scan for {domain.url}: {e}")

	log.info(f"Scheduled {scanned_count} {frequency} scans for {eligible_plans} plans")
	return {"scanned": scanned_count, "frequency": frequency, "plans": eligible_plans}
