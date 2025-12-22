# billing/guards.py
from __future__ import annotations
from typing import Optional
from django.utils import timezone
from .models import BillingProfile


def has_billing_access(user) -> bool:
	"""Check if user has an active paid subscription."""
	if not user or not user.is_authenticated:
		return False
	try:
		bp: Optional[BillingProfile] = user.billing_profile
		if not bp:
			return False
	except BillingProfile.DoesNotExist:
		return False

	now = timezone.now()

	status = (bp.subscription_status or "").lower()
	cpe = bp.current_period_end

	# Block these always
	if status in ("inactive", "canceled", "past_due", "unpaid", "incomplete", "incomplete_expired"):
		return False

	# Trial logic
	if status == "trialing":
		# If they canceled during trial -> immediate block
		if bp.cancel_at_period_end:
			return False
		# Otherwise, allow while trial end is in the future
		return bool(cpe and cpe > now)

	# Active logic
	if status == "active":
		# If they scheduled cancel, allow until current period end
		if bp.cancel_at_period_end:
			return bool(cpe and cpe > now)
		return True

	# Any unknown status -> be safe, block
	return False


def get_user_plan(user) -> str:
	"""
	Get the user's current effective plan tier.
	Returns 'free' if user is not authenticated or has no active subscription.
	"""
	if not user or not user.is_authenticated:
		return "free"
	try:
		bp: Optional[BillingProfile] = user.billing_profile
		if not bp:
			return "free"
	except BillingProfile.DoesNotExist:
		return "free"

	return bp.effective_plan_tier


def get_plan_limits(user) -> dict:
	"""Get the plan limits for the user's current tier."""
	from billing.plans import get_plan_config
	return get_plan_config(get_user_plan(user))


def can_use_feature(user, feature: str) -> bool:
	"""Check if the user's plan allows a specific feature."""
	from billing.plans import has_feature
	return has_feature(get_user_plan(user), feature)


def get_domain_limit(user) -> int:
	"""Get the maximum number of domains allowed for the user's plan."""
	from billing.plans import get_plan_limit
	return get_plan_limit(get_user_plan(user), "domains")


def get_pageview_limit(user) -> int:
	"""Get the monthly pageview limit for the user's plan."""
	from billing.plans import get_plan_limit
	return get_plan_limit(get_user_plan(user), "pageviews_per_month")


def get_effective_pageview_limit(user) -> int:
	"""Get the pageview limit including 15% grace period."""
	from billing.plans import get_effective_pageview_limit as _get_effective
	return _get_effective(get_user_plan(user))
