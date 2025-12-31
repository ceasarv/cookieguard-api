from django.conf import settings
from django.db import models
from django.utils import timezone


class BillingProfile(models.Model):
	class SubStatus(models.TextChoices):
		INACTIVE = 'inactive', 'Inactive'
		TRIALING = 'trialing', 'Trialing'
		ACTIVE = 'active', 'Active'
		PAST_DUE = 'past_due', 'Past due'
		CANCELED = 'canceled', 'Canceled'
		UNPAID = 'unpaid', 'Unpaid'

	class PlanTier(models.TextChoices):
		FREE = 'free', 'Free'
		PRO = 'pro', 'Pro'
		AGENCY = 'agency', 'Agency'

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='billing_profile',
	)

	stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
	subscription_id = models.CharField(max_length=255, blank=True, null=True)
	subscription_status = models.CharField(
		max_length=20, choices=SubStatus.choices, default=SubStatus.INACTIVE
	)
	plan_tier = models.CharField(
		max_length=20, choices=PlanTier.choices, default=PlanTier.FREE
	)
	price_lookup_key = models.CharField(max_length=255, blank=True, null=True)
	cancel_at_period_end = models.BooleanField(default=False)
	current_period_end = models.DateTimeField(blank=True, null=True)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	trial_used = models.BooleanField(default=False)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=['stripe_customer_id'],
				name='uniq_stripe_customer_when_set',
				condition=~models.Q(stripe_customer_id__isnull=True),
			),
		]
		indexes = [
			models.Index(fields=['stripe_customer_id']),
			models.Index(fields=['subscription_id']),
		]
		permissions = [
			("manage_billing", "Can manage billing & subscriptions"),
		]

	def __str__(self):
		return f'BillingProfile<User={self.user_id}>'

	@property
	def is_active(self) -> bool:
		return self.subscription_status in {self.SubStatus.ACTIVE, self.SubStatus.TRIALING}

	@property
	def on_trial(self) -> bool:
		if self.subscription_status != self.SubStatus.TRIALING:
			return False
		if not self.current_period_end:
			return False
		return self.current_period_end > timezone.now()

	@property
	def plan_limits(self) -> dict:
		"""Get the limits/features for the current plan tier."""
		from billing.plans import get_plan_config
		return get_plan_config(self.plan_tier)

	@property
	def effective_plan_tier(self) -> str:
		"""
		Get the effective plan tier based on subscription status.
		Returns 'free' if subscription is not active.
		"""
		if self.subscription_status in {self.SubStatus.ACTIVE, self.SubStatus.TRIALING}:
			return self.plan_tier
		return self.PlanTier.FREE


class UsageRecord(models.Model):
	"""
	Track monthly usage metrics per user account.
	Pageviews are shared across all domains for an account.
	"""
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='usage_records',
	)
	month = models.DateField(help_text="First day of the month")
	pageviews = models.PositiveIntegerField(default=0)
	scans_used = models.PositiveIntegerField(default=0)

	# Threshold warning flags to avoid duplicate emails
	warning_80_sent = models.BooleanField(default=False)
	warning_100_sent = models.BooleanField(default=False)
	warning_hard_limit_sent = models.BooleanField(default=False)

	# Deprecated - keeping for backwards compatibility, use warning_100_sent instead
	limit_warning_sent = models.BooleanField(default=False)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ['user', 'month']
		indexes = [
			models.Index(fields=['user', 'month']),
		]

	def __str__(self):
		return f'UsageRecord<User={self.user_id}, Month={self.month}>'


class AuditLog(models.Model):
	"""
	Audit trail for Agency plan users.
	Tracks changes to domains, banners, and other resources.
	"""
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		related_name='audit_logs',
	)
	action = models.CharField(max_length=50)  # e.g., "banner.updated", "domain.created"
	target_type = models.CharField(max_length=50)  # e.g., "Banner", "Domain"
	target_id = models.CharField(max_length=255)  # UUID as string
	changes = models.JSONField(default=dict)  # {"field": {"old": x, "new": y}}
	ip_address = models.GenericIPAddressField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['user', 'created_at']),
			models.Index(fields=['target_type', 'target_id']),
		]

	def __str__(self):
		return f'AuditLog<{self.action} by User={self.user_id}>'
