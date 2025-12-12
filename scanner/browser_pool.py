# scanner/browser_pool.py
"""
Reusable browser pool to avoid launching Chromium on every scan.
Keeps a single browser instance alive and reuses contexts.
"""
import asyncio
import logging
from playwright.async_api import async_playwright, Browser, Playwright

logger = logging.getLogger("scanner")

# Singleton state
_playwright: Playwright | None = None
_browser: Browser | None = None
_lock = asyncio.Lock()

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
    "--single-process",  # Reduces memory by running in single process
    "--memory-pressure-off",
    "--js-flags=--max-old-space-size=128",  # Limit JS heap
]

# Lighter viewport for cookie scanning (don't need full resolution)
VIEWPORT = {"width": 1024, "height": 576}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/114.0.0.0 Safari/537.36"
)


async def get_browser() -> Browser:
    """Get or create the shared browser instance."""
    global _playwright, _browser

    async with _lock:
        # Check if browser is still alive
        if _browser is not None and _browser.is_connected():
            return _browser

        # Clean up old instance if disconnected
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright is not None:
            try:
                await _playwright.stop()
            except Exception:
                pass
            _playwright = None

        # Launch new browser
        logger.info("[browser_pool] Launching new browser instance...")
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=BROWSER_ARGS,
        )
        logger.info("[browser_pool] Browser launched successfully")
        return _browser


# Heavy domains to block (ads, analytics, video, chat widgets - not needed for cookie scanning)
BLOCKED_DOMAINS = [
    "googletagmanager.com",
    "google-analytics.com",
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
    "facebook.net",
    "facebook.com/tr",
    "connect.facebook.net",
    "analytics.tiktok.com",
    "snap.licdn.com",
    "ads.linkedin.com",
    "bat.bing.com",
    "clarity.ms",
    "hotjar.com",
    "fullstory.com",
    "heapanalytics.com",
    "segment.io",
    "segment.com",
    "mixpanel.com",
    "amplitude.com",
    "intercom.io",
    "intercomcdn.com",
    "drift.com",
    "crisp.chat",
    "zendesk.com",
    "zopim.com",
    "tawk.to",
    "livechatinc.com",
    "youtube.com",
    "youtube-nocookie.com",
    "vimeo.com",
    "wistia.com",
    "vidyard.com",
    "player.vimeo.com",
    "sentry.io",
    "bugsnag.com",
    "logrocket.com",
    "newrelic.com",
    "nr-data.net",
    "optimizely.com",
    "abtasty.com",
    "crazyegg.com",
    "mouseflow.com",
    "trustpilot.com",
    "recaptcha.net",
    "gstatic.com/recaptcha",
    "hcaptcha.com",
]


async def get_context():
    """
    Get a new browser context from the shared browser.
    Caller is responsible for closing the context when done.
    """
    browser = await get_browser()
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport=VIEWPORT,
        bypass_csp=True,
    )

    # Block images, fonts, media, and other heavy resources
    await context.route(
        "**/*.{png,jpg,jpeg,gif,svg,webp,ico,woff,woff2,ttf,eot,mp4,webm,mp3,wav,ogg,avi,mov,pdf}",
        lambda route: route.abort()
    )

    # Block heavy third-party domains (ads, analytics, video, chat)
    async def block_heavy_domains(route):
        url = route.request.url.lower()
        for domain in BLOCKED_DOMAINS:
            if domain in url:
                await route.abort()
                return
        await route.continue_()

    await context.route("**/*", block_heavy_domains)

    return context


async def close_browser():
    """Explicitly close the browser (for shutdown)."""
    global _playwright, _browser

    async with _lock:
        if _browser is not None:
            try:
                await _browser.close()
            except Exception:
                pass
            _browser = None

        if _playwright is not None:
            try:
                await _playwright.stop()
            except Exception:
                pass
            _playwright = None

        logger.info("[browser_pool] Browser closed")
