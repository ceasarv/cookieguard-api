from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import BillingProfile


@admin.register(BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
	list_display = (
		"user_email",
		"plan_display",
		"status_badge",
		"on_trial_flag",
		"trial_days_remaining",
		"current_period_end",
		"cancel_at_period_end",
		"created_at",
	)
	list_filter = ("subscription_status", "cancel_at_period_end", "trial_used")
	search_fields = ("user__email", "stripe_customer_id", "subscription_id")
	ordering = ("-current_period_end",)
	readonly_fields = ("created_at", "updated_at")

	@admin.display(description="User Email")
	def user_email(self, obj):
		return getattr(obj.user, "email", "-")

	@admin.display(description="Plan")
	def plan_display(self, obj):
		return obj.price_lookup_key or "—"

	@admin.display(description="Status")
	def status_badge(self, obj):
		"""Color-coded badge for subscription status."""
		color_map = {
			BillingProfile.SubStatus.ACTIVE: "#4CAF50",  # green
			BillingProfile.SubStatus.TRIALING: "#2196F3",  # blue
			BillingProfile.SubStatus.PAST_DUE: "#FF9800",  # orange
			BillingProfile.SubStatus.CANCELED: "#9E9E9E",  # gray
			BillingProfile.SubStatus.UNPAID: "#E91E63",  # red
			BillingProfile.SubStatus.INACTIVE: "#757575",  # dark gray
		}
		color = color_map.get(obj.subscription_status, "#555")
		return format_html(
			'<span style="padding:3px 8px; border-radius:8px; color:white; background:{};">{}</span>',
			color,
			obj.get_subscription_status_display(),
		)

	@admin.display(boolean=True, description="On Trial")
	def on_trial_flag(self, obj):
		return obj.on_trial

	@admin.display(description="Trial Days Remaining")
	def trial_days_remaining(self, obj):
		if not obj.on_trial or not obj.current_period_end:
			return 0
		delta = obj.current_period_end - timezone.now()
		return max(0, delta.days)

	@admin.display(description="Stripe")
	def stripe_link(self, obj):
		if obj.stripe_customer_id:
			return format_html(
				'<a href="https://dashboard.stripe.com/customers/{}" target="_blank">View</a>',
				obj.stripe_customer_id,
			)
		return "-"
