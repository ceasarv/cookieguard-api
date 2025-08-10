from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse, urljoin
from tldextract import extract
import traceback, time, logging, re

logger = logging.getLogger("scanner")

TRACKING_PATTERNS = ["_ga", "_gid", "_fbp", "ajs_", "__hstc", "intercom", "_gcl_", "hubspot", "clarity"]


def classify_cookie(name: str) -> str:
	return "Tracker" if any(p in name for p in TRACKING_PATTERNS) else "Unclassified"


def base_domain(host: str) -> str:
	parts = extract(host or "")
	return f"{parts.domain}.{parts.suffix}" if parts.suffix else parts.domain


def same_site(host: str, start_host: str, include_subdomains: bool = False) -> bool:
	if not host or not start_host: return False
	if include_subdomains:
		return base_domain(host) == base_domain(start_host)
	return host == start_host


def normalize_links(hrefs: list[str], base_url: str) -> list[str]:
	out = []
	for href in hrefs or []:
		if not href:
			continue
		if href.startswith(("mailto:", "tel:", "javascript:", "#")):
			continue
		absu = urljoin(base_url, href)
		# strip fragments
		absu = re.sub(r"#.*$", "", absu)
		out.append(absu)
	return list(dict.fromkeys(out))  # de-dupe, preserve order


async def click_accept_if_present(page):
	# best-effort “Accept all” click; extend as needed
	selectors = [
		'text="Accept all"', 'text="Accept All"', 'text="I accept"', 'text="Agree"',
		'[data-testid*="accept"]', '[aria-label*="accept"]', 'button:has-text("Accept")',
		'[id*="accept"]', '[class*="accept"]'
	]
	for sel in selectors:
		try:
			btn = await page.wait_for_selector(sel, timeout=1500)
			if btn:
				await btn.click()
				await page.wait_for_load_state("networkidle", timeout=5000)
				break
		except Exception:
			pass


async def crawl_site(
		url: str,
		max_pages: int = 20,
		max_depth: int = 2,
		include_subdomains: bool = False,
		dual_pass: bool = False,
		pause_ms_between_pages: int = 600
):
	"""Crawl limited pages, aggregate cookies on one context."""
	t0 = time.perf_counter()
	start_host = urlparse(url).hostname or ""
	result = {
		"url": url,
		"pagesScanned": [],
		"cookies": [],
		"firstPartyCount": 0,
		"thirdPartyCount": 0,
		"trackerCount": 0,
		"unclassifiedCount": 0,
		"hasConsentBanner": False,  # any page
		"complianceScore": 100,
		"issues": [],
		"duration": None,
		"preConsent": None,  # filled if dual_pass
		"postConsent": None  # filled if dual_pass
	}

	async with async_playwright() as p:
		browser = await p.chromium.launch(
			headless=True,
			args=[
				"--disable-blink-features=AutomationControlled",
				"--disable-web-security",
				"--disable-features=IsolateOrigins,site-per-process",
				"--disable-http2",
				"--disable-features=NetworkService,PrefetchPrivacyChanges",
				"--no-sandbox", "--disable-dev-shm-usage", "--disable-setuid-sandbox"
			]
		)
		context = await browser.new_context(
			user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
						"AppleWebKit/537.36 (KHTML, like Gecko) "
						"Chrome/114.0.0.0 Safari/537.36"),
			viewport={"width": 1280, "height": 720}
		)
		page = await context.new_page()

		try:
			# ---- BFS crawl (single pass) ------------------------------------
			queue = [(url, 0)]
			visited = set()
			any_banner = False

			while queue and len(result["pagesScanned"]) < max_pages:
				current, depth = queue.pop(0)
				if current in visited or depth > max_depth:
					continue
				visited.add(current)

				try:
					await page.add_init_script('Object.defineProperty(navigator,"webdriver",{get:()=>undefined})')
					await page.goto(current, timeout=30000, wait_until="domcontentloaded")
					await page.wait_for_load_state("networkidle", timeout=15000)
					await page.wait_for_timeout(1200)  # let tags settle a bit

					html = await page.content()
					has_banner = any(k in html.lower() for k in ["cookie", "consent", "gdpr", "manage preferences"])
					any_banner = any_banner or has_banner

					result["pagesScanned"].append({"url": current, "hasConsentBanner": has_banner})

					# gather links for BFS
					try:
						hrefs = await page.eval_on_selector_all("a[href]",
																"els => els.map(a => a.getAttribute('href'))")
						for link in normalize_links(hrefs, current):
							host = urlparse(link).hostname
							if same_site(host, start_host, include_subdomains):
								queue.append((link, depth + 1))
					except Exception:
						pass

					# politeness
					if pause_ms_between_pages:
						await page.wait_for_timeout(pause_ms_between_pages)

				except PlaywrightTimeoutError:
					result["pagesScanned"].append({"url": current, "error": "timeout"})
				except Exception as e:
					result["pagesScanned"].append({"url": current, "error": str(e)})

			# aggregate cookies after crawl
			cookies = await context.cookies()
			result["hasConsentBanner"] = any_banner

			# classify
			def counts(cookies_list):
				first, third, track, uncls = 0, 0, 0, 0
				cookie_rows = []
				for c in cookies_list:
					classification = classify_cookie(c["name"])
					is_third = base_domain(c["domain"]) != base_domain(start_host)
					ctype = "Third-party" if is_third else "First-party"
					row = {
						"name": c["name"], "domain": c["domain"], "path": c.get("path", "/"),
						"expires": "Session" if c.get("expires", -1) == -1 else c.get("expires"),
						"type": ctype, "classification": classification
					}
					cookie_rows.append(row)
					first += (ctype == "First-party")
					third += (ctype == "Third-party")
					track += (classification == "Tracker")
					uncls += (classification != "Tracker")
				return cookie_rows, first, third, track, uncls

			cookie_rows, first, third, track, uncls = counts(cookies)
			result.update({
				"cookies": cookie_rows,
				"firstPartyCount": first,
				"thirdPartyCount": third,
				"trackerCount": track,
				"unclassifiedCount": uncls
			})

			# compliance heuristics
			issues = []
			if not any_banner:
				issues.append("No visible consent banner detected.")
			if track and not any_banner:
				issues.append("Tracking cookies set before obtaining consent.")
			score = 100
			if issues:
				score = 70 if any("Tracking" in i or "tracking" in i.lower() for i in issues) else 85
			result["issues"] = issues
			result["complianceScore"] = score

			# ---- Optional dual pass (click Accept then re-check) ------------
			if dual_pass:
				try:
					# pick a representative page (homepage or last good page)
					rep = result["pagesScanned"][0]["url"] if result["pagesScanned"] else url
					await page.goto(rep, timeout=30000, wait_until="domcontentloaded")
					await click_accept_if_present(page)
					await page.wait_for_timeout(1500)
					after_cookies = await context.cookies()
					pre = {k: v for k, v in result.items()}  # shallow snapshot
					pre["cookies"] = cookie_rows
					result["preConsent"] = {
						"counts": {"first": first, "third": third, "tracker": track, "unclassified": uncls}
					}
					ar, af, at, au = counts(after_cookies)
					result["postConsent"] = {
						"counts": {"first": af, "third": at, "tracker": au, "unclassified": len(ar) - au}
					}
				except Exception:
					# dual pass is best-effort; ignore failures
					pass

		except Exception as e:
			msg = str(e)
			if "ERR_HTTP2_PROTOCOL_ERROR" in msg:
				msg = "Site may be blocking headless browsers or using strict HTTP/2 settings."
			elif "Timeout" in msg:
				msg = "Page load timed out. Site may be blocking automated tools or is slow to respond."
			logger.error("[crawl][ERROR]: %s", msg)
			traceback.print_exc()
			result = {"error": msg}
		finally:
			await browser.close()

	result["duration"] = round(time.perf_counter() - t0, 2)
	return result
