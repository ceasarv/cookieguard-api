# scanner/tasks.py
from celery import shared_task
import logging
from django.utils import timezone
from scanner.scan_subprocess import run_scan_in_subprocess

log = logging.getLogger(__name__)


def update_progress(task, stage: str, progress: int, message: str, details: dict = None):
	"""Update Celery task state with progress info."""
	task.update_state(
		state='PROGRESS',
		meta={
			'stage': stage,
			'progress': progress,
			'message': message,
			'details': details or {},
		}
	)


@shared_task(bind=True)
def run_scan_task(
		self,
		url: str,
		mode: str = "single",  # "single" or "crawl"
		max_pages: int = 20,
		max_depth: int = 2,
		include_subdomains: bool = False,
		dual_pass: bool = False,
		pause_ms_between_pages: int = 400,
		domain_id: str = None,  # Optional: to save results to domain
		save_result: bool = False,  # Whether to save result to database
):
	"""
	Celery entrypoint for scans.

	Uses synchronous Playwright API which works with Celery on Windows.

	Returns a JSON-serializable dict suitable for sending to the frontend.
	"""
	if not url:
		return {"error": "URL required"}

	if not url.startswith(("http://", "https://")):
		url = f"https://{url}"

	# Update progress: starting
	update_progress(self, 'init', 10, f'Starting scan for {url}')

	# Run scan in subprocess to avoid asyncio/Celery conflicts on Windows
	update_progress(self, 'scanning', 30, 'Launching browser and loading page...')
	result = run_scan_in_subprocess(url)

	# Check for errors
	if result.get('error'):
		update_progress(self, 'error', 100, f'Scan failed: {result["error"]}')
	else:
		cookies_count = len(result.get('cookies', []))
		update_progress(self, 'complete', 100, f'Found {cookies_count} cookies')

	# Save result to database if requested
	if save_result and not result.get('error'):
		try:
			from scanner.models import ScanResult
			from domains.models import Domain

			domain = None
			if domain_id:
				try:
					domain = Domain.objects.get(id=domain_id)
				except Domain.DoesNotExist:
					pass

			scan_result = ScanResult.objects.create(
				domain=domain,
				url=url,
				result=result,
				cookies_found=len(result.get('cookies', [])),
				first_party_count=result.get('firstPartyCount', 0),
				third_party_count=result.get('thirdPartyCount', 0),
				tracker_count=result.get('trackerCount', 0),
				unclassified_count=result.get('unclassifiedCount', 0),
				compliance_score=result.get('complianceScore', 0),
				has_consent_banner=result.get('hasConsentBanner', False),
				pages_scanned=len(result.get('pagesScanned', [])) or 1,
				duration=result.get('duration', 0),
				issues=result.get('issues', []),
			)

			if domain:
				domain.last_scan_at = timezone.now()
				domain.save(update_fields=['last_scan_at'])

			# Add scan result ID to response
			result['scan_result_id'] = str(scan_result.id)

		except Exception as e:
			log.error(f"Failed to save scan result: {e}")

	return result


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
			# Queue scan for this domain with save_result=True
			run_scan_task.delay(
				domain.url,
				domain_id=str(domain.id),
				save_result=True,
			)
			domain.last_scan_at = timezone.now()
			domain.save(update_fields=["last_scan_at"])
			scanned_count += 1
			log.info(f"Queued auto-scan for {domain.url} (user: {domain.user.email})")
		except Exception as e:
			log.error(f"Failed to queue scan for {domain.url}: {e}")

	log.info(f"Scheduled {scanned_count} {frequency} scans for {eligible_plans} plans")
	return {"scanned": scanned_count, "frequency": frequency, "plans": eligible_plans}
