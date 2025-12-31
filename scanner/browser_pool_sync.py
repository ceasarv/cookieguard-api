# scanner/browser_pool_sync.py
"""
Synchronous browser pool for Celery workers.
Uses sync_playwright which works better with Celery on Windows.
"""
import logging
import threading
from playwright.sync_api import sync_playwright, Browser, Playwright

logger = logging.getLogger("scanner")

# Singleton state
_playwright: Playwright | None = None
_browser: Browser | None = None
_lock = threading.Lock()

# Memory-optimized Chrome args
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
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-http2",
    "--disable-features=NetworkService,PrefetchPrivacyChanges",
    "--single-process",
    "--memory-pressure-off",
    "--js-flags=--max-old-space-size=128",
]

VIEWPORT = {"width": 1024, "height": 576}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)

# Heavy domains to block
BLOCKED_DOMAINS = [
    "googletagmanager.com", "google-analytics.com", "doubleclick.net",
    "googlesyndication.com", "googleadservices.com", "facebook.net",
    "facebook.com/tr", "connect.facebook.net", "analytics.tiktok.com",
    "snap.licdn.com", "ads.linkedin.com", "bat.bing.com", "clarity.ms",
    "hotjar.com", "fullstory.com", "heapanalytics.com", "segment.io",
    "segment.com", "mixpanel.com", "amplitude.com", "intercom.io",
    "intercomcdn.com", "drift.com", "crisp.chat", "zendesk.com",
    "zopim.com", "tawk.to", "livechatinc.com", "youtube.com",
    "youtube-nocookie.com", "vimeo.com", "wistia.com", "vidyard.com",
    "player.vimeo.com", "sentry.io", "bugsnag.com", "logrocket.com",
    "newrelic.com", "nr-data.net", "optimizely.com", "abtasty.com",
    "crazyegg.com", "mouseflow.com", "trustpilot.com", "recaptcha.net",
    "gstatic.com/recaptcha", "hcaptcha.com",
]


def get_browser() -> Browser:
    """Get or create the shared browser instance."""
    global _playwright, _browser

    with _lock:
        # Check if browser is still alive
        if _browser is not None and _browser.is_connected():
            return _browser

        # Clean up old instance if disconnected
        if _browser is not None:
            try:
                _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright is not None:
            try:
                _playwright.stop()
            except Exception:
                pass
            _playwright = None

        # Launch new browser
        logger.info("[browser_pool_sync] Launching new browser instance...")
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(
            headless=True,
            args=BROWSER_ARGS,
        )
        logger.info("[browser_pool_sync] Browser launched successfully")
        return _browser


def get_context():
    """
    Get a new browser context from the shared browser.
    Caller is responsible for closing the context when done.
    """
    browser = get_browser()
    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport=VIEWPORT,
        bypass_csp=True,
    )

    # Block images, fonts, media, and other heavy resources
    context.route(
        "**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,eot,mp4,webm,mp3,wav,ogg,avi,mov,pdf}",
        lambda route: route.abort()
    )

    # Block heavy third-party domains
    def block_heavy_domains(route):
        url = route.request.url.lower()
        for domain in BLOCKED_DOMAINS:
            if domain in url:
                route.abort()
                return
        route.continue_()

    context.route("**/*", block_heavy_domains)

    return context


def close_browser():
    """Explicitly close the browser (for shutdown)."""
    global _playwright, _browser

    with _lock:
        if _browser is not None:
            try:
                _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright is not None:
            try:
                _playwright.stop()
            except Exception:
                pass
            _playwright = None

        logger.info("[browser_pool_sync] Browser closed")
