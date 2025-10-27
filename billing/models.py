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
