from django.core.management.base import BaseCommand
from scanner.models import CookieDefinition


# Well-known cookies with their classifications
KNOWN_COOKIES = [
	# Google Analytics
	{"name": "_ga", "domain_pattern": ".google-analytics.com", "category": "analytics", "provider": "Google Analytics", "description": "Used to distinguish users. Expires after 2 years."},
	{"name": "_ga", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics", "description": "Used to distinguish users. Set on the website domain."},
	{"name": "_gid", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics", "description": "Used to distinguish users. Expires after 24 hours."},
	{"name": "_gat", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics", "description": "Used to throttle request rate. Expires after 1 minute."},
	{"name": "_gac_", "domain_pattern": "", "category": "marketing", "provider": "Google Analytics", "description": "Contains campaign related information for the user."},
	{"name": "__utma", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics (Classic)", "description": "Used to distinguish users and sessions."},
	{"name": "__utmb", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics (Classic)", "description": "Used to determine new sessions/visits."},
	{"name": "__utmc", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics (Classic)", "description": "Interoperates with urchin.js."},
	{"name": "__utmz", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics (Classic)", "description": "Stores the traffic source or campaign."},
	{"name": "__utmv", "domain_pattern": "", "category": "analytics", "provider": "Google Analytics (Classic)", "description": "Used to store visitor-level custom variable data."},

	# Google Ads
	{"name": "_gcl_au", "domain_pattern": "", "category": "marketing", "provider": "Google Ads", "description": "Used to store and track conversions."},
	{"name": "_gcl_aw", "domain_pattern": "", "category": "marketing", "provider": "Google Ads", "description": "Stores click information from Google Ads."},
	{"name": "_gcl_dc", "domain_pattern": "", "category": "marketing", "provider": "Google Ads", "description": "Used to track conversions from Display ads."},

	# Facebook
	{"name": "_fbp", "domain_pattern": "", "category": "marketing", "provider": "Facebook Pixel", "description": "Used to deliver advertising when users are on Facebook or a digital platform powered by Facebook."},
	{"name": "_fbc", "domain_pattern": "", "category": "marketing", "provider": "Facebook Pixel", "description": "Stores click identifier for conversion tracking."},
	{"name": "fr", "domain_pattern": ".facebook.com", "category": "marketing", "provider": "Facebook", "description": "Used by Facebook for advertising and tracking."},

	# Hotjar
	{"name": "_hjid", "domain_pattern": "", "category": "analytics", "provider": "Hotjar", "description": "Set when a user first lands on a page. Persists Hotjar User ID."},
	{"name": "_hjSessionUser_", "domain_pattern": "", "category": "analytics", "provider": "Hotjar", "description": "Set when a user first lands on a page. Persists Hotjar User ID."},
	{"name": "_hjSession_", "domain_pattern": "", "category": "analytics", "provider": "Hotjar", "description": "Holds current session data."},
	{"name": "_hjIncludedInSessionSample", "domain_pattern": "", "category": "analytics", "provider": "Hotjar", "description": "Set to determine if a user is included in the session sample."},
	{"name": "_hjAbsoluteSessionInProgress", "domain_pattern": "", "category": "analytics", "provider": "Hotjar", "description": "Used to detect the first pageview session of a user."},
	{"name": "_hjFirstSeen", "domain_pattern": "", "category": "analytics", "provider": "Hotjar", "description": "Identifies a new user's first session."},

	# Microsoft Clarity
	{"name": "_clck", "domain_pattern": "", "category": "analytics", "provider": "Microsoft Clarity", "description": "Persists the Clarity User ID and preferences."},
	{"name": "_clsk", "domain_pattern": "", "category": "analytics", "provider": "Microsoft Clarity", "description": "Connects multiple page views by a user into a single session."},
	{"name": "CLID", "domain_pattern": ".clarity.ms", "category": "analytics", "provider": "Microsoft Clarity", "description": "Identifies the first-time Clarity saw this user."},

	# HubSpot
	{"name": "__hssc", "domain_pattern": "", "category": "analytics", "provider": "HubSpot", "description": "Keeps track of sessions."},
	{"name": "__hssrc", "domain_pattern": "", "category": "analytics", "provider": "HubSpot", "description": "Used to determine if the user has restarted their browser."},
	{"name": "__hstc", "domain_pattern": "", "category": "analytics", "provider": "HubSpot", "description": "Tracks visitors. Contains domain, utk, initial timestamp, last timestamp, current timestamp, and session number."},
	{"name": "hubspotutk", "domain_pattern": "", "category": "analytics", "provider": "HubSpot", "description": "Keeps track of a visitor's identity. Passed to HubSpot on form submission."},

	# LinkedIn
	{"name": "li_gc", "domain_pattern": ".linkedin.com", "category": "marketing", "provider": "LinkedIn", "description": "Used to store guest consent to use cookies for non-essential purposes."},
	{"name": "li_sugr", "domain_pattern": ".linkedin.com", "category": "marketing", "provider": "LinkedIn", "description": "Used for tracking in LinkedIn Insight Tag."},
	{"name": "lidc", "domain_pattern": ".linkedin.com", "category": "functional", "provider": "LinkedIn", "description": "Used for routing and data center selection."},
	{"name": "bcookie", "domain_pattern": ".linkedin.com", "category": "functional", "provider": "LinkedIn", "description": "Browser identifier cookie."},
	{"name": "UserMatchHistory", "domain_pattern": ".linkedin.com", "category": "marketing", "provider": "LinkedIn", "description": "Used to track visitors for ad targeting."},

	# Intercom
	{"name": "intercom-id-", "domain_pattern": "", "category": "functional", "provider": "Intercom", "description": "Identifies the user for Intercom chat."},
	{"name": "intercom-session-", "domain_pattern": "", "category": "functional", "provider": "Intercom", "description": "Keeps track of sessions for Intercom chat."},

	# Stripe
	{"name": "__stripe_mid", "domain_pattern": "", "category": "necessary", "provider": "Stripe", "description": "Fraud prevention and detection."},
	{"name": "__stripe_sid", "domain_pattern": "", "category": "necessary", "provider": "Stripe", "description": "Fraud prevention and detection."},

	# Segment
	{"name": "ajs_user_id", "domain_pattern": "", "category": "analytics", "provider": "Segment", "description": "Stores user ID set with identify calls."},
	{"name": "ajs_anonymous_id", "domain_pattern": "", "category": "analytics", "provider": "Segment", "description": "Anonymous ID for users who haven't been identified."},

	# Mixpanel
	{"name": "mp_", "domain_pattern": "", "category": "analytics", "provider": "Mixpanel", "description": "Used to track user interactions."},

	# Amplitude
	{"name": "amplitude_id_", "domain_pattern": "", "category": "analytics", "provider": "Amplitude", "description": "Stores unique user identifier."},

	# TikTok
	{"name": "_ttp", "domain_pattern": "", "category": "marketing", "provider": "TikTok Pixel", "description": "Used to track visitors for TikTok advertising."},
	{"name": "tt_webid", "domain_pattern": "", "category": "marketing", "provider": "TikTok", "description": "Used to track visitors for TikTok advertising."},

	# Twitter/X
	{"name": "muc_ads", "domain_pattern": ".twitter.com", "category": "marketing", "provider": "Twitter/X", "description": "Used for advertising."},
	{"name": "personalization_id", "domain_pattern": ".twitter.com", "category": "marketing", "provider": "Twitter/X", "description": "Used for advertising."},

	# Cloudflare
	{"name": "__cf_bm", "domain_pattern": "", "category": "necessary", "provider": "Cloudflare", "description": "Bot management cookie to identify bots."},
	{"name": "_cfuvid", "domain_pattern": "", "category": "necessary", "provider": "Cloudflare", "description": "Rate limiting and session identification."},
	{"name": "cf_clearance", "domain_pattern": "", "category": "necessary", "provider": "Cloudflare", "description": "Stored when a user passes a Cloudflare challenge."},

	# Common session/auth cookies
	{"name": "sessionid", "domain_pattern": "", "category": "necessary", "provider": "Django", "description": "Session identifier for Django applications."},
	{"name": "csrftoken", "domain_pattern": "", "category": "necessary", "provider": "Django", "description": "CSRF protection token for Django applications."},
	{"name": "PHPSESSID", "domain_pattern": "", "category": "necessary", "provider": "PHP", "description": "Session identifier for PHP applications."},
	{"name": "JSESSIONID", "domain_pattern": "", "category": "necessary", "provider": "Java", "description": "Session identifier for Java applications."},
	{"name": "ASP.NET_SessionId", "domain_pattern": "", "category": "necessary", "provider": "ASP.NET", "description": "Session identifier for ASP.NET applications."},

	# Common functional cookies
	{"name": "lang", "domain_pattern": "", "category": "functional", "provider": "Generic", "description": "Stores user language preference."},
	{"name": "locale", "domain_pattern": "", "category": "functional", "provider": "Generic", "description": "Stores user locale preference."},
	{"name": "currency", "domain_pattern": "", "category": "functional", "provider": "Generic", "description": "Stores user currency preference."},
	{"name": "timezone", "domain_pattern": "", "category": "functional", "provider": "Generic", "description": "Stores user timezone preference."},

	# Consent management
	{"name": "cookieconsent_status", "domain_pattern": "", "category": "necessary", "provider": "Cookie Consent", "description": "Stores user's cookie consent decision."},
	{"name": "CookieConsent", "domain_pattern": "", "category": "necessary", "provider": "Cookiebot", "description": "Stores user's cookie consent decision."},
	{"name": "OptanonConsent", "domain_pattern": "", "category": "necessary", "provider": "OneTrust", "description": "Stores user's cookie consent decision."},
	{"name": "OptanonAlertBoxClosed", "domain_pattern": "", "category": "necessary", "provider": "OneTrust", "description": "Stores whether the cookie banner was closed."},

	# Zendesk
	{"name": "__zlcmid", "domain_pattern": "", "category": "functional", "provider": "Zendesk", "description": "Used to store a unique ID for Zendesk live chat."},

	# Drift
	{"name": "driftt_aid", "domain_pattern": "", "category": "functional", "provider": "Drift", "description": "Anonymous visitor identifier for Drift chat."},
	{"name": "drift_aid", "domain_pattern": "", "category": "functional", "provider": "Drift", "description": "Anonymous visitor identifier for Drift chat."},

	# Pinterest
	{"name": "_pinterest_sess", "domain_pattern": ".pinterest.com", "category": "marketing", "provider": "Pinterest", "description": "Login and authentication cookie."},
	{"name": "_pin_unauth", "domain_pattern": "", "category": "marketing", "provider": "Pinterest", "description": "Used for Pinterest tracking."},

	# Reddit
	{"name": "_rdt_uuid", "domain_pattern": "", "category": "marketing", "provider": "Reddit Pixel", "description": "Used for Reddit advertising conversion tracking."},

	# Snapchat
	{"name": "_scid", "domain_pattern": "", "category": "marketing", "provider": "Snapchat Pixel", "description": "Used for Snapchat advertising."},
	{"name": "sc_at", "domain_pattern": "", "category": "marketing", "provider": "Snapchat Pixel", "description": "Used for Snapchat conversion tracking."},

	# Heap Analytics
	{"name": "_hp2_id.", "domain_pattern": "", "category": "analytics", "provider": "Heap Analytics", "description": "Stores user ID for Heap Analytics."},
	{"name": "_hp2_ses_props.", "domain_pattern": "", "category": "analytics", "provider": "Heap Analytics", "description": "Stores session properties for Heap Analytics."},

	# Sentry
	{"name": "sentry-sc", "domain_pattern": "", "category": "necessary", "provider": "Sentry", "description": "Error tracking and performance monitoring."},

	# New Relic
	{"name": "JSESSIONID", "domain_pattern": ".newrelic.com", "category": "analytics", "provider": "New Relic", "description": "Session identifier for New Relic."},

	# Optimizely
	{"name": "optimizelyEndUserId", "domain_pattern": "", "category": "analytics", "provider": "Optimizely", "description": "Stores unique visitor identifier."},
	{"name": "optimizelySegments", "domain_pattern": "", "category": "analytics", "provider": "Optimizely", "description": "Stores information about segments the user belongs to."},

	# VWO
	{"name": "_vwo_uuid", "domain_pattern": "", "category": "analytics", "provider": "VWO", "description": "Used for A/B testing and personalization."},
	{"name": "_vis_opt_s", "domain_pattern": "", "category": "analytics", "provider": "VWO", "description": "Detects the first session of the user."},

	# Crazy Egg
	{"name": "ceg.s", "domain_pattern": "", "category": "analytics", "provider": "Crazy Egg", "description": "Session tracking for Crazy Egg heatmaps."},
	{"name": "ceg.u", "domain_pattern": "", "category": "analytics", "provider": "Crazy Egg", "description": "User tracking for Crazy Egg heatmaps."},

	# FullStory
	{"name": "fs_uid", "domain_pattern": "", "category": "analytics", "provider": "FullStory", "description": "Stores unique user identifier for session replay."},

	# Bing Ads
	{"name": "_uetsid", "domain_pattern": "", "category": "marketing", "provider": "Microsoft Advertising", "description": "Stores visitor ID for Bing Ads."},
	{"name": "_uetvid", "domain_pattern": "", "category": "marketing", "provider": "Microsoft Advertising", "description": "Stores unique visitor ID across sessions for Bing Ads."},
	{"name": "MUID", "domain_pattern": ".bing.com", "category": "marketing", "provider": "Microsoft", "description": "Microsoft user identifier for advertising."},

	# Yahoo
	{"name": "A3", "domain_pattern": ".yahoo.com", "category": "marketing", "provider": "Yahoo", "description": "Used for Yahoo advertising."},

	# Adroll
	{"name": "__adroll", "domain_pattern": "", "category": "marketing", "provider": "AdRoll", "description": "Used for retargeting advertisements."},
	{"name": "__adroll_fpc", "domain_pattern": "", "category": "marketing", "provider": "AdRoll", "description": "Used for retargeting advertisements."},

	# Criteo
	{"name": "cto_bundle", "domain_pattern": "", "category": "marketing", "provider": "Criteo", "description": "Used for retargeting advertisements."},

	# Taboola
	{"name": "t_gid", "domain_pattern": "", "category": "marketing", "provider": "Taboola", "description": "Used for Taboola content recommendations and advertising."},

	# Outbrain
	{"name": "obuid", "domain_pattern": "", "category": "marketing", "provider": "Outbrain", "description": "Used for Outbrain content recommendations."},
]


class Command(BaseCommand):
	help = 'Seed the database with well-known cookie definitions'

	def add_arguments(self, parser):
		parser.add_argument(
			'--clear',
			action='store_true',
			help='Clear existing definitions before seeding',
		)

	def handle(self, *args, **options):
		if options['clear']:
			deleted_count = CookieDefinition.objects.filter(is_verified=True).delete()[0]
			self.stdout.write(f"Cleared {deleted_count} verified definitions")

		created_count = 0
		updated_count = 0

		for cookie_data in KNOWN_COOKIES:
			definition, created = CookieDefinition.objects.update_or_create(
				name=cookie_data['name'],
				domain_pattern=cookie_data['domain_pattern'],
				defaults={
					'category': cookie_data['category'],
					'provider': cookie_data['provider'],
					'description': cookie_data['description'],
					'is_verified': True,
					'classification_confidence': 1.0,  # Verified cookies have 100% confidence
				}
			)
			if created:
				created_count += 1
			else:
				updated_count += 1

		self.stdout.write(
			self.style.SUCCESS(
				f"Seeded {created_count} new cookie definitions, updated {updated_count} existing"
			)
		)
		self.stdout.write(f"Total definitions in database: {CookieDefinition.objects.count()}")
