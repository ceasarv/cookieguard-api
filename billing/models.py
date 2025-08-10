from django.conf import settings
from django.db import models


class BillingProfile(models.Model):
	class SubStatus(models.TextChoices):
		INACTIVE = 'inactive', 'Inactive'
		TRIALING = 'trialing', 'Trialing'
		ACTIVE = 'active', 'Active'
		PAST_DUE = 'past_due', 'Past due'
		CANCELED = 'canceled', 'Canceled'
		UNPAID = 'unpaid', 'Unpaid'

	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='billing')
	stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)
	subscription_id = models.CharField(max_length=255, blank=True, null=True)
	subscription_status = models.CharField(max_length=20, choices=SubStatus.choices, default=SubStatus.INACTIVE)
	price_lookup_key = models.CharField(max_length=255, blank=True,
										null=True)  # "cg_starter_monthly" | "cg_pro_monthly"
	current_period_end = models.DateTimeField(blank=True, null=True)

	def __str__(self):
		return f'BillingProfile<{self.user_id}>'
