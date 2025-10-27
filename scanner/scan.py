from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse
from tldextract import extract
import traceback
import time
import logging

logger = logging.getLogger("scanner")

TRACKING_PATTERNS = [
	"_ga", "_gid", "_fbp", "ajs_", "__hstc", "intercom", "_gcl_", "hubspot", "clarity"
]


def classify_cookie(name):
	for pattern in TRACKING_PATTERNS:
		if pattern in name:
			return "Tracker"
	return "Unclassified"


def get_base_domain(host):
	parts = extract(host)
	return f"{parts.domain}.{parts.suffix}" if parts.suffix else parts.domain


async def scan_site(url: str):
	logger.info("[scan_site] Starting scan for: %s", url)

	# Normalize URL — ensure it has protocol
	if not url.startswith(("http://", "https://")):
		url = "https://" + url
		
	parsed_host = urlparse(url).hostname or ""
	result = {}
	start_time = time.perf_counter()

	async with async_playwright() as p:
		logger.info("[scan_site] Launching Chromium browser...")
		browser = await p.chromium.launch(
			headless=True,
			args=[
				"--disable-blink-features=AutomationControlled",
				"--disable-web-security",
				"--disable-features=IsolateOrigins,site-per-process",
				"--disable-http2",
				"--disable-features=NetworkService",
				"--disable-features=PrefetchPrivacyChanges",
				"--no-sandbox",
				"--disable-dev-shm-usage",
				"--disable-setuid-sandbox"
			]
		)

		context = await browser.new_context(
			user_agent=(
				"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
				"AppleWebKit/537.36 (KHTML, like Gecko) "
				"Chrome/114.0.0.0 Safari/537.36"
			),
			viewport={"width": 1280, "height": 720}
		)
		page = await context.new_page()

		try:
			logger.info("[scan_site] Injecting evasion script...")
			await page.add_init_script(
				"""Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""
			)

			max_retries = 2
			for attempt in range(max_retries):
				try:
					logger.info("[scan_site] Navigating to %s (Attempt %d)...", url, attempt + 1)
					await page.goto(url, timeout=30000, wait_until="domcontentloaded")
					await page.wait_for_load_state("networkidle", timeout=30000)
					break
				except PlaywrightTimeoutError:
					if attempt == max_retries - 1:
						raise
					await page.wait_for_timeout(2000)

			logger.info("[scan_site] Page loaded and network idle.")
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
				classification = classify_cookie(c["name"])
				is_third_party = get_base_domain(c["domain"]) != get_base_domain(parsed_host)
				ctype = "Third-party" if is_third_party else "First-party"

				cookie_info = {
					"name": c["name"],
					"domain": c["domain"],
					"path": c["path"],
					"expires": "Session" if c["expires"] == -1 else c["expires"],
					"type": ctype,
					"classification": classification
				}

				cookie_results.append(cookie_info)

				if ctype == "First-party":
					first_party.append(cookie_info)
				else:
					third_party.append(cookie_info)

				if classification == "Tracker":
					tracking_cookies.append(cookie_info)
				else:
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
				"duration": round(time.perf_counter() - start_time, 2)
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
			logger.info("[scan_site] Closing browser...")
			await browser.close()

	logger.info("[scan_site] Returning result.")
	return result
