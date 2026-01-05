import uuid
from django.db import models


class CookieDefinition(models.Model):
	"""
	Shared cookie database - crowdsourced from user classifications.
	When users classify cookies, we aggregate the data here.
	"""
	CATEGORY_CHOICES = [
		('necessary', 'Strictly Necessary'),
		('functional', 'Functional'),
		('analytics', 'Analytics'),
		('marketing', 'Marketing/Advertising'),
		('other', 'Other'),
	]

	# Cookie identification - we match on name + domain pattern
	name = models.CharField(max_length=255, db_index=True)
	domain_pattern = models.CharField(
		max_length=255,
		db_index=True,
		help_text="Domain pattern, e.g., '.google.com' or 'facebook.com'"
	)

	# Classification
	category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
	description = models.TextField(blank=True, help_text="What this cookie does")
	provider = models.CharField(max_length=100, blank=True, help_text="e.g., Google Analytics, Facebook")

	# Crowdsourcing stats
	times_seen = models.PositiveIntegerField(default=1)
	times_classified = models.PositiveIntegerField(default=0)
	classification_confidence = models.FloatField(
		default=0,
		help_text="0-1 score based on agreement between user classifications"
	)

	# Track classification votes for crowdsourcing
	votes_necessary = models.PositiveIntegerField(default=0)
	votes_functional = models.PositiveIntegerField(default=0)
	votes_analytics = models.PositiveIntegerField(default=0)
	votes_marketing = models.PositiveIntegerField(default=0)
	votes_other = models.PositiveIntegerField(default=0)

	# Metadata
	is_verified = models.BooleanField(default=False, help_text="Manually verified by admin")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ['name', 'domain_pattern']
		ordering = ['-times_seen']
		indexes = [
			models.Index(fields=['name']),
			models.Index(fields=['domain_pattern']),
			models.Index(fields=['category']),
			models.Index(fields=['-times_seen']),
		]

	def __str__(self):
		return f"{self.name} ({self.domain_pattern}) - {self.category}"

	def add_classification_vote(self, category: str):
		"""Add a user's classification vote and recalculate consensus."""
		vote_field = f"votes_{category}"
		if hasattr(self, vote_field):
			setattr(self, vote_field, getattr(self, vote_field) + 1)
			self.times_classified += 1
			self._recalculate_category()
			self.save()

	def _recalculate_category(self):
		"""Set category to the one with most votes and calculate confidence."""
		votes = {
			'necessary': self.votes_necessary,
			'functional': self.votes_functional,
			'analytics': self.votes_analytics,
			'marketing': self.votes_marketing,
			'other': self.votes_other,
		}
		if self.times_classified > 0:
			max_category = max(votes, key=votes.get)
			max_votes = votes[max_category]
			self.category = max_category
			self.classification_confidence = max_votes / self.times_classified

	@classmethod
	def find_match(cls, cookie_name: str, cookie_domain: str):
		"""Find a matching definition for a cookie."""
		# Try exact match first
		match = cls.objects.filter(
			name=cookie_name,
			domain_pattern=cookie_domain
		).first()
		if match:
			return match

		# Try matching base domain (e.g., .google.com matches analytics.google.com)
		base_domain = cookie_domain.lstrip('.')
		match = cls.objects.filter(
			name=cookie_name,
			domain_pattern__icontains=base_domain
		).first()
		if match:
			return match

		# Try name-only match for well-known cookies (high confidence ones)
		match = cls.objects.filter(
			name=cookie_name,
			classification_confidence__gte=0.8
		).first()
		return match

	@classmethod
	def get_or_create_from_cookie(cls, cookie_name: str, cookie_domain: str):
		"""Get existing definition or create a new unclassified one."""
		definition, created = cls.objects.get_or_create(
			name=cookie_name,
			domain_pattern=cookie_domain,
			defaults={'category': 'other'}
		)
		if not created:
			definition.times_seen += 1
			definition.save(update_fields=['times_seen'])
		return definition, created


class ScanResult(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	domain = models.ForeignKey(
		'domains.Domain',
		on_delete=models.CASCADE,
		related_name='scan_results',
		null=True,
		blank=True,
	)
	url = models.URLField()
	result = models.JSONField(default=dict, help_text="Full scan result JSON")
	cookies_found = models.PositiveIntegerField(default=0)
	has_consent_banner = models.BooleanField(default=False)
	compliance_score = models.IntegerField(default=0)
	first_party_count = models.PositiveIntegerField(default=0)
	third_party_count = models.PositiveIntegerField(default=0)
	tracker_count = models.PositiveIntegerField(default=0)
	unclassified_count = models.PositiveIntegerField(default=0)
	issues = models.JSONField(default=list)
	pages_scanned = models.PositiveIntegerField(default=1)
	duration = models.FloatField(default=0, help_text="Duration in seconds")
	scanned_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-scanned_at']
		indexes = [
			models.Index(fields=['domain', '-scanned_at']),
			models.Index(fields=['-scanned_at']),
		]

	def __str__(self):
		return f"Scan for {self.url} at {self.scanned_at.strftime('%Y-%m-%d %H:%M')}"


class Cookie(models.Model):
	"""Individual cookie found in a scan, linked to the shared definition database."""
	CATEGORY_CHOICES = CookieDefinition.CATEGORY_CHOICES

	# Well-known cookie patterns for auto-classification
	KNOWN_PATTERNS = {
		'analytics': [
			# Google Analytics
			'_ga', '_gid', '_gat', '__utma', '__utmb', '__utmc', '__utmt', '__utmz', '_gac_',
			# Adobe Analytics
			's_cc', 's_sq', 's_vi', 's_fid', 'AMCV_', 'AMCVS_', 's_ecid',
			# Hotjar
			'_hjid', '_hjSession', '_hjSessionUser', '_hjIncludedInSample', '_hjAbsoluteSessionInProgress',
			# Microsoft Clarity
			'_clck', '_clsk', 'CLID', 'ANONCHK', 'MR', 'MUID', 'SM',
			# Mixpanel
			'mp_', 'mixpanel',
			# Heap
			'_hp2_', '_heapid',
			# Piwik/Matomo
			'_pk_id', '_pk_ses', '_pk_ref', 'pk_vid',
			# Plausible (privacy-friendly)
			'plausible',
			# Other analytics
			'amplitude_', '_vis_opt', '_vwo_',
		],
		'marketing': [
			# Meta/Facebook
			'_fbp', '_fbc', 'fr', 'datr', 'sb', 'wd', 'xs', 'c_user',
			# Google Ads
			'_gcl_', 'gclid', '_gads', '__gads', 'IDE', 'DSID', 'FLC', 'AID', 'TAID',
			# LinkedIn
			'li_', 'bcookie', 'bscookie', 'lidc', 'UserMatchHistory', 'AnalyticsSyncHistory',
			# Twitter/X
			'twid', 'auth_token', 'personalization_id', 'guest_id',
			# TikTok
			'_ttp', 'tt_webid', 'ttwid',
			# Pinterest
			'_pinterest', '_pin_unauth',
			# Bing Ads
			'_uetsid', '_uetvid', 'MUIDB',
			# Criteo
			'cto_', 'criteo',
			# DoubleClick
			'__gfp_64b', 'test_cookie',
			# Taboola
			'taboola',
			# Outbrain
			'outbrain',
			# AdRoll
			'__adroll', '__ar_v4',
			# HubSpot
			'__hstc', '__hssc', '__hssrc', 'hubspotutk', 'messagesUtk',
		],
		'functional': [
			# Language/locale
			'lang', 'locale', 'language', 'i18n',
			# UI preferences
			'theme', 'dark_mode', 'darkmode', 'color_scheme',
			'font_size', 'layout', 'sidebar',
			# Session management (non-auth)
			'recently_viewed', 'comparison_list', 'wishlist',
			# Chat widgets
			'intercom', 'drift', 'crisp', 'tawk', 'zendesk', 'freshchat',
			# Video preferences
			'youtube_', 'vimeo_', 'player_',
		],
		'necessary': [
			# Security & auth
			'csrf', 'xsrf', '__csrf', 'csrftoken', '_csrf',
			'session', 'sessionid', 'PHPSESSID', 'JSESSIONID', 'ASP.NET_SessionId',
			'auth', 'jwt', 'token', 'refresh_token', 'access_token',
			# Cart & checkout
			'cart', 'basket', 'checkout',
			# Cookie consent
			'cookieconsent', 'cookie_consent', 'gdpr', 'cc_cookie', 'CookieConsent',
			'euconsent', 'OptanonConsent', 'OptanonAlertBoxClosed',
			# Load balancing
			'AWSALB', 'AWSALBCORS', '__cf_bm', 'cf_clearance',
			# Cloudflare
			'__cfduid', '__cfruid',
		],
	}

	scan = models.ForeignKey(ScanResult, on_delete=models.CASCADE, related_name="cookies")
	name = models.CharField(max_length=255)
	domain = models.CharField(max_length=255)
	path = models.CharField(max_length=255)
	expires = models.CharField(max_length=255)  # Session or timestamp string
	type = models.CharField(max_length=20, choices=[('First-party', 'First-party'), ('Third-party', 'Third-party')])

	# Link to shared definition (for auto-classification)
	definition = models.ForeignKey(
		CookieDefinition,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='cookie_instances'
	)

	# Classification - can be auto-filled from definition or manually set
	category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
	classification = models.CharField(max_length=50, default='Unclassified')  # Legacy field for tracker detection

	# User override - if user manually classifies this cookie for their domain
	user_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, null=True, blank=True)
	user_description = models.TextField(blank=True)

	def __str__(self):
		return f"{self.name} ({self.type})"

	def get_effective_category(self):
		"""Return user override if set, otherwise use definition or default."""
		if self.user_category:
			return self.user_category
		if self.definition:
			return self.definition.category
		return self.category

	@classmethod
	def guess_category_from_name(cls, cookie_name: str, cookie_domain: str = '') -> str:
		"""Guess cookie category based on known patterns."""
		name_lower = cookie_name.lower()
		domain_lower = cookie_domain.lower()

		# Check domain-based hints first
		if any(d in domain_lower for d in ['google-analytics', 'analytics.google', 'hotjar', 'clarity.ms', 'mixpanel', 'heap']):
			return 'analytics'
		if any(d in domain_lower for d in ['facebook', 'fb.com', 'doubleclick', 'googlesyndication', 'googleads', 'linkedin', 'twitter', 'tiktok', 'criteo', 'taboola']):
			return 'marketing'

		# Check name patterns
		for category, patterns in cls.KNOWN_PATTERNS.items():
			for pattern in patterns:
				pattern_lower = pattern.lower()
				if name_lower == pattern_lower or name_lower.startswith(pattern_lower):
					return category

		return 'other'

	def save(self, *args, **kwargs):
		# Auto-link to definition if not set
		if not self.definition and self.name and self.domain:
			self.definition = CookieDefinition.find_match(self.name, self.domain)
			if self.definition:
				self.category = self.definition.category

		# If still 'other', try pattern-based classification
		if self.category == 'other' and not self.user_category:
			guessed = self.guess_category_from_name(self.name, self.domain)
			if guessed != 'other':
				self.category = guessed

		super().save(*args, **kwargs)
