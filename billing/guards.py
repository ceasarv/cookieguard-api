# billing/guards.py
from __future__ import annotations
from typing import Optional
from django.utils import timezone
from .models import BillingProfile


def has_billing_access(user) -> bool:
	if not user or not user.is_authenticated:
		return False
	try:
		# Corrected access from .billing_profiles to .billing_profile
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
