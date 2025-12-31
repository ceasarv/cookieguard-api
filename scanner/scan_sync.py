# scanner/scan_sync.py
"""
Synchronous scanner for Celery workers.
Uses sync_playwright which works better with Celery on Windows.
"""
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse
from tldextract import extract
import traceback
import time
import logging

from scanner.browser_pool_sync import get_context

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


def scan_site_sync(url: str, progress_callback=None):
    """Synchronous single-page scan."""
    logger.info("[scan_site_sync] Starting scan for: %s", url)

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed_host = urlparse(url).hostname or ""
    result = {}
    start_time = time.perf_counter()

    def report_progress(stage, pct, msg, details=None):
        if progress_callback:
            try:
                progress_callback(stage, pct, msg, details or {})
            except Exception:
                pass

    report_progress('init', 5, 'Initializing browser...')

    context = get_context()

    try:
        page = context.new_page()
        report_progress('scanning', 10, 'Loading page...')

        logger.info("[scan_site_sync] Injecting evasion script...")
        page.add_init_script(
            """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""
        )

        max_retries = 2
        for attempt in range(max_retries):
            try:
                logger.info("[scan_site_sync] Navigating to %s (Attempt %d)...", url, attempt + 1)
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=20000)
                break
            except PlaywrightTimeoutError:
                if attempt == max_retries - 1:
                    raise
                page.wait_for_timeout(1500)

        report_progress('analyzing', 70, 'Analyzing cookies...')

        logger.info("[scan_site_sync] Page loaded and network idle.")
        html = page.content()

        logger.info("[scan_site_sync] Getting cookies...")
        cookies = page.context.cookies()
        logger.info("[scan_site_sync] Found %d cookies.", len(cookies))

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

        logger.info("[scan_site_sync] Checking for consent banner...")
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

        report_progress('complete', 100, 'Scan complete!')

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

        logger.info("[scan_site_sync] Scan complete.")

    except Exception as e:
        error_message = str(e)
        if "ERR_HTTP2_PROTOCOL_ERROR" in error_message:
            error_message = "Site may be blocking headless browsers or using strict HTTP/2 settings."
        elif "Timeout" in error_message:
            error_message = "Page load timed out. Site may be blocking automated tools or is slow to respond."
        logger.error("[scan_site_sync][ERROR]: %s", error_message)
        traceback.print_exc()
        result = {"error": error_message, "duration": round(time.perf_counter() - start_time, 2)}

    finally:
        logger.info("[scan_site_sync] Closing context...")
        context.close()

    logger.info("[scan_site_sync] Returning result.")
    return result
