from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse, urljoin
from tldextract import extract
import traceback, time, logging, re

from scanner.browser_pool import get_context

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
	# best-effort "Accept all" click; extend as needed
	selectors = [
		'text="Accept all"', 'text="Accept All"', 'text="I accept"', 'text="Agree"',
		'[data-testid*="accept"]', '[aria-label*="accept"]', 'button:has-text("Accept")',
		'[id*="accept"]', '[class*="accept"]'
	]
	for sel in selectors:
		try:
			btn = await page.wait_for_selector(sel, timeout=1000)
			if btn:
				await btn.click()
				await page.wait_for_load_state("networkidle", timeout=4000)
				break
		except Exception:
			pass


async def crawl_site(
		url: str,
		max_pages: int = 20,
		max_depth: int = 2,
		include_subdomains: bool = False,
		dual_pass: bool = False,
		pause_ms_between_pages: int = 400
):
	"""Crawl limited pages, aggregate cookies on one context."""
	return await crawl_site_with_progress(
		url=url,
		max_pages=max_pages,
		max_depth=max_depth,
		include_subdomains=include_subdomains,
		dual_pass=dual_pass,
		pause_ms_between_pages=pause_ms_between_pages,
		progress_callback=None,
	)


async def crawl_site_with_progress(
		url: str,
		max_pages: int = 20,
		max_depth: int = 2,
		include_subdomains: bool = False,
		dual_pass: bool = False,
		pause_ms_between_pages: int = 400,
		progress_callback=None,
):
	"""Crawl limited pages, aggregate cookies on one context. Supports progress callbacks."""
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

	def report_progress(stage, pct, msg, details=None):
		if progress_callback:
			try:
				progress_callback(stage, pct, msg, details or {})
			except Exception:
				pass

	report_progress('init', 5, 'Initializing browser...')

	# Get a context from the shared browser pool
	context = await get_context()

	try:
		page = await context.new_page()
		report_progress('crawling', 10, 'Browser ready, starting crawl...')

		# ---- BFS crawl (single pass) ------------------------------------
		queue = [(url, 0)]
		visited = set()
		any_banner = False

		while queue and len(result["pagesScanned"]) < max_pages:
			current, depth = queue.pop(0)
			if current in visited or depth > max_depth:
				continue
			visited.add(current)

			pages_done = len(result["pagesScanned"])
			progress_pct = 10 + int((pages_done / max_pages) * 80)  # 10-90%
			report_progress(
				'crawling',
				progress_pct,
				f'Scanning page {pages_done + 1}/{max_pages}...',
				{'current_url': current, 'pages_scanned': pages_done, 'max_pages': max_pages}
			)

			try:
				await page.add_init_script('Object.defineProperty(navigator,"webdriver",{get:()=>undefined})')
				await page.goto(current, timeout=25000, wait_until="domcontentloaded")
				await page.wait_for_load_state("networkidle", timeout=12000)
				await page.wait_for_timeout(800)  # let tags settle a bit

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

		report_progress('analyzing', 90, 'Analyzing cookies...')

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
			report_progress('dual_pass', 95, 'Testing consent flow...')
			try:
				# pick a representative page (homepage or last good page)
				rep = result["pagesScanned"][0]["url"] if result["pagesScanned"] else url
				await page.goto(rep, timeout=25000, wait_until="domcontentloaded")
				await click_accept_if_present(page)
				await page.wait_for_timeout(1000)
				after_cookies = await context.cookies()
				result["preConsent"] = {
					"counts": {"first": first, "third": third, "tracker": track, "unclassified": uncls}
				}
				after_rows, after_first, after_third, after_track, after_uncls = counts(after_cookies)
				result["postConsent"] = {
					"counts": {"first": after_first, "third": after_third, "tracker": after_track, "unclassified": after_uncls}
				}
			except Exception:
				# dual pass is best-effort; ignore failures
				pass

		report_progress('complete', 100, 'Scan complete!')

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
		# Close context but keep browser alive for next scan
		await context.close()

	result["duration"] = round(time.perf_counter() - t0, 2)
	return result
