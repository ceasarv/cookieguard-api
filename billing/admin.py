from datetime import timedelta
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import BillingProfile
from .plans import PLAN_LIMITS, get_tier_from_lookup_key


@admin.register(BillingProfile)
class BillingProfileAdmin(admin.ModelAdmin):
	list_display = (
		"user_email",
		"plan_tier_badge",
		"status_badge",
		"on_trial_flag",
		"trial_days_remaining",
		"current_period_end",
		"cancel_at_period_end",
		"effective_tier_display",
		"created_at",
	)
	list_filter = ("subscription_status", "plan_tier", "cancel_at_period_end", "trial_used")
	search_fields = ("user__email", "stripe_customer_id", "subscription_id")
	ordering = ("-current_period_end",)
	readonly_fields = ("created_at", "updated_at", "effective_plan_info")
	fieldsets = (
		("User", {
			"fields": ("user",)
		}),
		("Subscription Status", {
			"fields": ("subscription_status", "plan_tier", "price_lookup_key", "effective_plan_info")
		}),
		("Stripe", {
			"fields": ("stripe_customer_id", "subscription_id")
		}),
		("Billing Period", {
			"fields": ("current_period_end", "cancel_at_period_end", "trial_used")
		}),
		("Timestamps", {
			"fields": ("created_at", "updated_at"),
			"classes": ("collapse",)
		}),
	)
	actions = [
		"set_pro_active_30_days",
		"set_pro_trialing_14_days",
		"set_multi_site_active_30_days",
		"set_free_plan",
		"simulate_expired_subscription",
		"simulate_canceled_subscription",
	]

	# ─────────────────────────────────────────────────────────────────────────
	# Display helpers
	# ─────────────────────────────────────────────────────────────────────────

	@admin.display(description="Effective Plan Info")
	def effective_plan_info(self, obj):
		"""Show what plan the user effectively has access to."""
		effective = obj.effective_plan_tier
		limits = PLAN_LIMITS.get(effective, PLAN_LIMITS["free"])
		return format_html(
			'<div style="background:#f5f5f5; padding:10px; border-radius:5px;">'
			'<strong>Effective Tier:</strong> {}<br>'
			'<strong>Domains:</strong> {}<br>'
			'<strong>Pageviews/mo:</strong> {:,}<br>'
			'<strong>Auto Scan:</strong> {}<br>'
			'<strong>Remove Branding:</strong> {}'
			'</div>',
			effective,
			limits.get("domains", 1),
			limits.get("pageviews_per_month", 0),
			limits.get("auto_scan") or "Manual",
			"Yes" if limits.get("remove_branding") else "No",
		)

	@admin.display(description="User Email")
	def user_email(self, obj):
		return getattr(obj.user, "email", "-")

	@admin.display(description="Plan Tier")
	def plan_tier_badge(self, obj):
		"""Color-coded badge for plan tier."""
		color_map = {
			"free": "#9E9E9E",
			"pro": "#2196F3",
			"multi_site": "#9C27B0",
		}
		color = color_map.get(obj.plan_tier, "#555")
		return format_html(
			'<span style="padding:3px 8px; border-radius:8px; color:white; background:{};">{}</span>',
			color,
			obj.get_plan_tier_display(),
		)

	@admin.display(description="Effective")
	def effective_tier_display(self, obj):
		"""Show the effective tier (what they actually get access to)."""
		effective = obj.effective_plan_tier
		color_map = {
			"free": "#9E9E9E",
			"pro": "#2196F3",
			"multi_site": "#9C27B0",
		}
		color = color_map.get(effective, "#555")
		return format_html(
			'<span style="padding:3px 8px; border-radius:8px; color:white; background:{};">{}</span>',
			color,
			effective.replace("_", " ").title(),
		)

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

	# ─────────────────────────────────────────────────────────────────────────
	# Admin Actions for Testing
	# ─────────────────────────────────────────────────────────────────────────

	@admin.action(description="🧪 Set Pro (Active, 30 days)")
	def set_pro_active_30_days(self, request, queryset):
		count = queryset.update(
			plan_tier="pro",
			price_lookup_key="cg_pro_monthly",
			subscription_status=BillingProfile.SubStatus.ACTIVE,
			current_period_end=timezone.now() + timedelta(days=30),
			cancel_at_period_end=False,
		)
		self.message_user(request, f"✅ Set {count} profile(s) to Pro (Active, 30 days)", messages.SUCCESS)

	@admin.action(description="🧪 Set Pro (Trialing, 14 days)")
	def set_pro_trialing_14_days(self, request, queryset):
		count = queryset.update(
			plan_tier="pro",
			price_lookup_key="cg_pro_monthly",
			subscription_status=BillingProfile.SubStatus.TRIALING,
			current_period_end=timezone.now() + timedelta(days=14),
			cancel_at_period_end=False,
			trial_used=True,
		)
		self.message_user(request, f"✅ Set {count} profile(s) to Pro (Trialing, 14 days)", messages.SUCCESS)

	@admin.action(description="🧪 Set Multi-Site (Active, 30 days)")
	def set_multi_site_active_30_days(self, request, queryset):
		count = queryset.update(
			plan_tier="multi_site",
			price_lookup_key="cg_multi_site_monthly",
			subscription_status=BillingProfile.SubStatus.ACTIVE,
			current_period_end=timezone.now() + timedelta(days=30),
			cancel_at_period_end=False,
		)
		self.message_user(request, f"✅ Set {count} profile(s) to Multi-Site (Active, 30 days)", messages.SUCCESS)

	@admin.action(description="🧪 Reset to Free Plan")
	def set_free_plan(self, request, queryset):
		count = queryset.update(
			plan_tier="free",
			price_lookup_key=None,
			subscription_status=BillingProfile.SubStatus.INACTIVE,
			current_period_end=None,
			cancel_at_period_end=False,
		)
		self.message_user(request, f"✅ Reset {count} profile(s) to Free plan", messages.SUCCESS)

	@admin.action(description="🧪 Simulate Expired Subscription")
	def simulate_expired_subscription(self, request, queryset):
		"""Set subscription to expired (period ended yesterday)."""
		count = queryset.update(
			subscription_status=BillingProfile.SubStatus.CANCELED,
			current_period_end=timezone.now() - timedelta(days=1),
			cancel_at_period_end=True,
		)
		self.message_user(request, f"⏰ Set {count} profile(s) to expired state", messages.WARNING)

	@admin.action(description="🧪 Simulate Canceled (still has time)")
	def simulate_canceled_subscription(self, request, queryset):
		"""Set subscription to canceled but still within period."""
		count = queryset.update(
			subscription_status=BillingProfile.SubStatus.ACTIVE,
			current_period_end=timezone.now() + timedelta(days=7),
			cancel_at_period_end=True,
		)
		self.message_user(request, f"🚫 Set {count} profile(s) to canceled (7 days remaining)", messages.WARNING)
