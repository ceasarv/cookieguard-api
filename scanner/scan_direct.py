# scanner/scan_direct.py
"""
Direct scanner that launches a fresh browser per scan.
No browser pool - designed for subprocess isolation.
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse
from tldextract import extract
import traceback
import time
import logging
import uuid
import redis
from django.conf import settings

from scanner.models import CookieDefinition

logger = logging.getLogger("scanner")

# Redis connection for screenshot storage
redis_client = redis.from_url(settings.CELERY_BROKER_URL)
SCREENSHOT_TTL = 600  # 10 minutes

# Browser args
BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-setuid-sandbox",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-translate",
    "--disable-default-apps",
    "--no-first-run",
    "--disable-blink-features=AutomationControlled",
]

VIEWPORT = {"width": 1440, "height": 900}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Known tracking cookie patterns (fallback if not in database)
TRACKING_PATTERNS = [
    "_ga", "_gid", "_fbp", "ajs_", "__hstc", "intercom", "_gcl_", "hubspot", "clarity",
    "_uetsid", "_uetvid", "_ttp", "TDID", "IDE", "uuid2", "demdex", "criteo", "adnxs"
]

CATEGORY_DISPLAY = {
    'necessary': 'Necessary',
    'functional': 'Functional',
    'analytics': 'Analytics',
    'marketing': 'Marketing',
    'other': 'Unclassified',
}


def save_screenshot_to_redis(screenshot_bytes: bytes) -> str:
    """Save screenshot to Redis and return the key."""
    screenshot_id = str(uuid.uuid4())
    key = f"screenshot:{screenshot_id}"
    redis_client.setex(key, SCREENSHOT_TTL, screenshot_bytes)
    return screenshot_id


def classify_cookie(name: str, domain: str) -> tuple[str, str, str]:
    """Classify a cookie using DB first, then fallback to patterns."""
    try:
        definition = CookieDefinition.find_match(name, domain)
        if definition:
            category = CATEGORY_DISPLAY.get(definition.category, 'Unclassified')
            return (category, definition.category, definition.provider or '')
    except Exception:
        pass

    for pattern in TRACKING_PATTERNS:
        if pattern in name.lower():
            return ('Tracker', 'marketing', '')

    return ('Unclassified', 'other', '')


def get_base_domain(host):
    if not host:
        return ""
    host = host.lstrip(".")
    if not host:
        return ""
    parts = extract(host)
    return f"{parts.domain}.{parts.suffix}" if parts.suffix else parts.domain


def scan_site_direct(url: str) -> dict:
    """
    Direct scan that launches a fresh browser.
    No singleton, no pool - just a clean scan.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed_host = urlparse(url).hostname or ""
    start_time = time.perf_counter()

    playwright = None
    browser = None
    context = None

    try:
        # Launch fresh browser
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=True,
            args=BROWSER_ARGS,
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
            bypass_csp=True,
        )

        # Block heavy resources
        context.route(
            "**/*.{woff,woff2,ttf,eot,mp4,webm,mp3,wav,ogg,avi,mov,pdf}",
            lambda route: route.abort()
        )

        page = context.new_page()

        # Evasion
        page.add_init_script(
            """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""
        )

        # Navigate with retry
        max_retries = 2
        for attempt in range(max_retries):
            try:
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=20000)
                break
            except PlaywrightTimeoutError:
                if attempt == max_retries - 1:
                    raise
                page.wait_for_timeout(1500)

        # Screenshot
        screenshot_url = None
        try:
            screenshot_bytes = page.screenshot(
                full_page=False,
                type='jpeg',
                quality=50,
                scale='css',
            )
            screenshot_id = save_screenshot_to_redis(screenshot_bytes)
            screenshot_url = f"/api/screenshots/{screenshot_id}"
        except Exception:
            pass

        html = page.content()
        cookies = context.cookies()

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

        return {
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
            "screenshot": screenshot_url,
        }

    except Exception as e:
        error_message = str(e)
        if "ERR_HTTP2_PROTOCOL_ERROR" in error_message:
            error_message = "Site may be blocking headless browsers or using strict HTTP/2 settings."
        elif "Timeout" in error_message:
            error_message = "Page load timed out. Site may be blocking automated tools or is slow to respond."
        traceback.print_exc()
        return {"error": error_message, "duration": round(time.perf_counter() - start_time, 2)}

    finally:
        # Clean shutdown
        if context:
            try:
                context.close()
            except Exception:
                pass
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass
