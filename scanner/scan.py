from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse
from tldextract import extract
import traceback
import time
import logging
import uuid
import os
import base64
from pathlib import Path
from django.conf import settings

from scanner.browser_pool import get_context
from scanner.models import CookieDefinition

logger = logging.getLogger("scanner")

# Ensure screenshot directory exists
SCREENSHOT_DIR = getattr(settings, 'SCREENSHOT_DIR', Path(settings.BASE_DIR) / 'media' / 'screenshots')
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Known tracking cookie patterns (fallback if not in database)
TRACKING_PATTERNS = [
	"_ga", "_gid", "_fbp", "ajs_", "__hstc", "intercom", "_gcl_", "hubspot", "clarity",
	"_uetsid", "_uetvid", "_ttp", "TDID", "IDE", "uuid2", "demdex", "criteo", "adnxs"
]

# Category display names
CATEGORY_DISPLAY = {
	'necessary': 'Necessary',
	'functional': 'Functional',
	'analytics': 'Analytics',
	'marketing': 'Marketing',
	'other': 'Unclassified',
}


def classify_cookie(name: str, domain: str) -> tuple[str, str, str]:
	"""
	Classify a cookie using the database first, then fallback to patterns.
	Returns (classification, category, provider)
	"""
	# Try database lookup
	definition = CookieDefinition.find_match(name, domain)
	if definition:
		category = CATEGORY_DISPLAY.get(definition.category, 'Unclassified')
		return (category, definition.category, definition.provider or '')

	# Fallback to pattern matching
	for pattern in TRACKING_PATTERNS:
		if pattern in name.lower():
			return ('Tracker', 'marketing', '')

	return ('Unclassified', 'other', '')


def get_base_domain(host):
	if not host:
		return ""
	# Strip leading dots from cookie domains (e.g., ".example.com" -> "example.com")
	host = host.lstrip(".")
	if not host:
		return ""
	parts = extract(host)
	return f"{parts.domain}.{parts.suffix}" if parts.suffix else parts.domain


def cleanup_old_screenshots(max_keep: int = 5):
	"""Delete oldest screenshots if there are more than max_keep in the folder."""
	try:
		screenshots = [
			f for f in SCREENSHOT_DIR.iterdir()
			if f.is_file() and f.suffix.lower() == '.png'
		]
		if len(screenshots) <= max_keep:
			return

		# Sort by modification time (oldest first)
		screenshots.sort(key=lambda f: f.stat().st_mtime)

		# Delete oldest ones, keeping only max_keep
		to_delete = screenshots[:-max_keep]
		for f in to_delete:
			try:
				f.unlink()
				logger.debug("[cleanup] Deleted old screenshot: %s", f.name)
			except Exception:
				pass
	except Exception as e:
		logger.debug("[cleanup] Screenshot cleanup error: %s", e)


async def scan_site(url: str):
	logger.info("[scan_site] Starting scan for: %s", url)

	# Normalize URL — ensure it has protocol
	if not url.startswith(("http://", "https://")):
		url = "https://" + url

	parsed_host = urlparse(url).hostname or ""
	result = {}
	start_time = time.perf_counter()

	# Get a context from the shared browser pool
	context = await get_context()

	try:
		page = await context.new_page()

		logger.info("[scan_site] Injecting evasion script...")
		await page.add_init_script(
			"""Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""
		)

		max_retries = 2
		for attempt in range(max_retries):
			try:
				logger.info("[scan_site] Navigating to %s (Attempt %d)...", url, attempt + 1)
				await page.goto(url, timeout=30000, wait_until="domcontentloaded")
				await page.wait_for_load_state("networkidle", timeout=20000)
				break
			except PlaywrightTimeoutError:
				if attempt == max_retries - 1:
					raise
				await page.wait_for_timeout(1500)

		logger.info("[scan_site] Page loaded and network idle.")

		# Capture screenshot as base64 (JPEG, 70% quality, ~50-100KB)
		screenshot_base64 = None
		try:
			screenshot_bytes = await page.screenshot(
				full_page=False,
				type='jpeg',
				quality=70,
				scale='css',  # Use CSS pixels, not device pixels
			)
			screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
			logger.info("[scan_site] Screenshot captured (%d KB)", len(screenshot_bytes) // 1024)
		except Exception as ss_error:
			logger.warning("[scan_site] Screenshot failed: %s", ss_error)
			screenshot_base64 = None

		html = await page.content()

		logger.info("[scan_site] Getting cookies...")
		cookies = await page.context.cookies()
		logger.info("[scan_site] Found %d cookies.", len(cookies))

		cookie_results = []
		tracking_cookies = []
		unclassified_cookies = []
		first_party = []
		third_party = []

		for c in cookies:
			classification, category, provider = classify_cookie(c["name"], c["domain"])
			is_third_party = get_base_domain(c["domain"]) != get_base_domain(parsed_host)
			ctype = "Third-party" if is_third_party else "First-party"

			cookie_info = {
				"name": c["name"],
				"domain": c["domain"],
				"path": c["path"],
				"expires": "Session" if c["expires"] == -1 else c["expires"],
				"type": ctype,
				"classification": classification,
				"category": category,
			}
			if provider:
				cookie_info["provider"] = provider

			cookie_results.append(cookie_info)

			if ctype == "First-party":
				first_party.append(cookie_info)
			else:
				third_party.append(cookie_info)

			if classification in ("Tracker", "Marketing", "Analytics"):
				tracking_cookies.append(cookie_info)
			elif classification == "Unclassified":
				unclassified_cookies.append(cookie_info)

		logger.info("[scan_site] Checking for consent banner...")
		has_consent_banner = any(
			k in html.lower() for k in ["cookie", "consent", "gdpr", "manage preferences"]
		)

		issues = []
		if not has_consent_banner:
			issues.append("No visible consent banner detected.")
		if tracking_cookies and not has_consent_banner:
			issues.append("Tracking cookies set before obtaining consent.")

		score = 100
		if issues:
			score = 70 if "tracking" in str(issues).lower() else 85

		result = {
			"url": url,
			"cookies": cookie_results,
			"firstPartyCount": len(first_party),
			"thirdPartyCount": len(third_party),
			"trackerCount": len(tracking_cookies),
			"unclassifiedCount": len(unclassified_cookies),
			"hasConsentBanner": has_consent_banner,
			"complianceScore": score,
			"issues": issues,
			"duration": round(time.perf_counter() - start_time, 2),
			"screenshot": screenshot_base64,  # Base64 encoded PNG
		}

		logger.info("[scan_site] Scan complete.")

	except Exception as e:
		error_message = str(e)
		if "ERR_HTTP2_PROTOCOL_ERROR" in error_message:
			error_message = "Site may be blocking headless browsers or using strict HTTP/2 settings."
		elif "Timeout" in error_message:
			error_message = "Page load timed out. Site may be blocking automated tools or is slow to respond."
		logger.error("[scan_site][ERROR]: %s", error_message)
		traceback.print_exc()
		result = {"error": error_message}

	finally:
		# Close context but keep browser alive for next scan
		logger.info("[scan_site] Closing context...")
		try:
			await context.close()
		except Exception as close_error:
			# Context may already be closed, that's okay
			logger.debug("[scan_site] Context close error (safe to ignore): %s", close_error)

	logger.info("[scan_site] Returning result.")
	return result
