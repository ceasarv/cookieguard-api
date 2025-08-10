# scanner/tasks.py
from celery import shared_task
import asyncio
from scanner.scan import scan_site  # single-page scan
from scanner.crawler import crawl_site  # multi-page crawl


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
		pause_ms_between_pages: int = 600,
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
