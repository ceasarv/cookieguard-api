import os
import stripe
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import BillingProfile
import logging

log = logging.getLogger(__name__)

# --- Stripe config -----------------------------------------------------------
stripe.api_key = settings.STRIPE_SECRET_KEY
if getattr(settings, "STRIPE_API_VERSION", None):
	stripe.api_version = settings.STRIPE_API_VERSION


# --- Helpers ----------------------------------------------------------------
def _ensure_customer(user) -> str:
	"""Create or return a Stripe customer for this user."""
	profile, _ = BillingProfile.objects.get_or_create(user=user)
	if profile.stripe_customer_id:
		return profile.stripe_customer_id
	customer = stripe.Customer.create(email=getattr(user, "email", None))
	profile.stripe_customer_id = customer.id
	profile.save(update_fields=["stripe_customer_id"])
	return customer.id


def _resolve_price_id(value: str) -> str:
	"""
	Accepts either a Stripe price ID (e.g., 'price_123') or a lookup key
	(e.g., 'cg_essential_monthly'). Returns a price ID.
	"""
	if not value:
		raise ValueError("Price identifier is required")
	if value.startswith("price_"):
		return value
	prices = stripe.Price.list(lookup_keys=[value], active=True, limit=1)
	if not prices.data:
		raise ValueError(f"Price not found for '{value}'")
	return prices.data[0].id


def _get_urls_or_503():
	success = getattr(settings, "STRIPE_SUCCESS_URL", None)
	cancel = getattr(settings, "STRIPE_CANCEL_URL", None)
	if not success or not cancel:
		return None, None, Response(
			{
				"error": "Server misconfigured: STRIPE_SUCCESS_URL / STRIPE_CANCEL_URL missing.",
			},
			status=status.HTTP_503_SERVICE_UNAVAILABLE,
		)
	return success, cancel, None


# --- API: Create Checkout Session -------------------------------------------
@api_view(["POST"])
def create_checkout_session(request):
	"""
	Body: { "plan": "starter" | "pro" }
	Creates a Stripe Checkout Session for a subscription (optional trial).
	"""
	plan = (request.data.get("plan") or "").strip().lower()
	if plan not in ("starter", "pro"):
		return Response({"error": "Invalid plan"}, status=400)

	# Resolve price by plan
	if plan == "starter":
		price_selector = (
				getattr(settings, "STRIPE_PRICE_STARTER", None)
				or getattr(settings, "STRIPE_LOOKUP_STARTER", None)
		)
	else:
		price_selector = (
				getattr(settings, "STRIPE_PRICE_PRO", None)
				or getattr(settings, "STRIPE_LOOKUP_PRO", None)
		)

	if not price_selector:
		return Response(
			{"error": "Server misconfigured: missing STRIPE_* for selected plan."},
			status=status.HTTP_503_SERVICE_UNAVAILABLE,
		)

	try:
		price_id = _resolve_price_id(price_selector)
	except Exception as e:
		return Response({"error": str(e)}, status=400)

	# Success/Cancel URLs
	success_url, cancel_url, error_resp = _get_urls_or_503()
	if error_resp:
		return error_resp

	profile, _ = BillingProfile.objects.get_or_create(user=request.user)
	customer_id = _ensure_customer(request.user)
	trial_days = int(getattr(settings, "TRIAL_DAYS", os.getenv("TRIAL_DAYS", 14)))
	auto_tax = bool(getattr(settings, "STRIPE_AUTOMATIC_TAX", False))

	subscription_data = {
		"metadata": {
			"user_id": str(request.user.id),
			"plan": plan,
			"selector": price_selector,
		}
	}
	if not profile.trial_used:
		subscription_data["trial_period_days"] = trial_days

	try:
		session = stripe.checkout.Session.create(
			mode="subscription",
			customer=customer_id,
			line_items=[{"price": price_id, "quantity": 1}],
			success_url=f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
			cancel_url=cancel_url,
			allow_promotion_codes=True,
			automatic_tax={"enabled": auto_tax},
			subscription_data=subscription_data,
			customer_update={"name": "auto"},
			payment_method_types=["card"],
		)
	except stripe.error.InvalidRequestError as e:
		return Response({"error": str(e)}, status=400)

	# Store intended selector
	profile.price_lookup_key = (
		price_selector if not price_selector.startswith("price_") else None
	)
	profile.save(update_fields=["price_lookup_key"])

	return Response({"url": session.url})


# --- API: Billing Portal -----------------------------------------------------
@api_view(["POST"])
def create_billing_portal_session(request):
	"""Creates a Stripe Billing Portal session so users can manage payment methods/cancel."""
	try:
		profile = BillingProfile.objects.get(user=request.user)
	except BillingProfile.DoesNotExist:
		# Ensure a profile exists (and a customer) then continue
		_ensure_customer(request.user)
		profile = BillingProfile.objects.get(user=request.user)

	customer_id = profile.stripe_customer_id or _ensure_customer(request.user)

	return_url = getattr(settings, "STRIPE_BILLING_PORTAL_RETURN_URL", None)
	if not return_url:
		return Response(
			{"error": "Server misconfigured: STRIPE_BILLING_PORTAL_RETURN_URL missing."},
			status=status.HTTP_503_SERVICE_UNAVAILABLE,
		)

	try:
		portal = stripe.billing_portal.Session.create(
			customer=customer_id,
			return_url=return_url,
		)
	except stripe.error.InvalidRequestError as e:
		return Response({"error": str(e)}, status=400)

	return Response({"url": portal.url})


# --- Webhook ----------------------------------------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def stripe_webhook(request):
	payload = request.body
	sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
	wh_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

	try:
		event = stripe.Webhook.construct_event(
			payload=payload, sig_header=sig_header, secret=wh_secret
		)
	except stripe.error.SignatureVerificationError as e:
		log.error("❌ Stripe signature error: %s", e)
		return Response(status=400)
	except ValueError as e:
		log.error("❌ Invalid payload: %s", e)
		return Response(status=400)

	try:
		type_ = event["type"]
		data = event["data"]["object"]
		log.info(f"⚡ Received Stripe event: {type_}")

		def _update_profile_from_sub(subscription):
			log.info("🧩 Updating profile for sub: %s", subscription.get("id"))
			customer_id = subscription["customer"]
			from billing.models import BillingProfile
			try:
				profile = BillingProfile.objects.get(stripe_customer_id=customer_id)
			except BillingProfile.DoesNotExist:
				log.warning("⚠️ No BillingProfile found for customer %s", customer_id)
				return

			profile.subscription_id = subscription["id"]
			profile.subscription_status = subscription["status"]

			end_ts = subscription.get("trial_end") or subscription.get("current_period_end")
			if end_ts:
				from datetime import datetime, timezone as dt_timezone
				profile.current_period_end = datetime.fromtimestamp(end_ts, tz=dt_timezone.utc)
			else:
				profile.current_period_end = None

			profile.cancel_at_period_end = bool(subscription.get("cancel_at_period_end", False))

			items = subscription.get("items", {}).get("data", [])
			if items and items[0].get("price", {}).get("lookup_key"):
				profile.price_lookup_key = items[0]["price"]["lookup_key"]
			if subscription.get("trial_end"):
				profile.trial_used = True

			profile.save()
			log.info("✅ Saved BillingProfile for %s", customer_id)

			# Toggle banners
			from banners.models import Banner
			subscription_status = subscription.get("status", "").lower()
			end_ts = subscription.get("current_period_end") or subscription.get("trial_end")
			has_time_left = (
					end_ts and datetime.fromtimestamp(end_ts, tz=dt_timezone.utc) > timezone.now()
			)

			user = profile.user
			if subscription_status in ("canceled", "unpaid", "inactive") and not has_time_left:
				Banner.objects.filter(domains__user=user, is_active=True).update(is_active=False)
				log.info("⏸️ Paused banners for user %s", user.email)
			elif subscription_status in ("active", "trialing") and has_time_left:
				Banner.objects.filter(domains__user=user, is_active=False).update(is_active=True)
				log.info("▶️ Re-enabled banners for user %s", user.email)

		# -- Event routing --
		if type_ == "checkout.session.completed":
			session = stripe.checkout.Session.retrieve(data["id"], expand=["subscription"])
			sub = session.get("subscription")
			if isinstance(sub, dict):
				_update_profile_from_sub(sub)

		elif type_ in (
				"customer.subscription.created",
				"customer.subscription.updated",
				"customer.subscription.deleted",
		):
			_update_profile_from_sub(data)

		elif type_ == "invoice.payment_failed":
			sub = data.get("subscription")
			if sub:
				sub_obj = stripe.Subscription.retrieve(sub)
				_update_profile_from_sub(sub_obj)

	except Exception as e:
		log.exception("🔥 Stripe webhook failed: %s", e)
		return Response(status=500)

	return Response(status=200)


# --- Public Pricing ----------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def public_pricing(request):
	starter = getattr(settings, "STRIPE_LOOKUP_STARTER", None)
	pro = getattr(settings, "STRIPE_LOOKUP_PRO", None)
	if not starter or not pro:
		return Response(
			{
				"error": "Server misconfigured: STRIPE_LOOKUP_STARTER / STRIPE_LOOKUP_PRO missing."
			},
			status=status.HTTP_503_SERVICE_UNAVAILABLE,
		)

	prices = stripe.Price.list(
		lookup_keys=[starter, pro], active=True, expand=["data.product"]
	)
	out = []
	for p in prices.data:
		out.append(
			{
				"lookup_key": p.lookup_key,
				"unit_amount": p.unit_amount,  # cents
				"currency": p.currency,  # "usd"
				"interval": p.recurring["interval"] if p.recurring else None,  # "month"
				"product_name": p.product["name"] if isinstance(p.product, dict) else p.product,
				"price_id": p.id,
			}
		)
	return Response(out)


@api_view(["GET"])
def my_billing(request):
	try:
		profile = BillingProfile.objects.get(user=request.user)
	except BillingProfile.DoesNotExist:
		_ensure_customer(request.user)
		return Response({
			"has_profile": False, "plan": None, "status": "inactive",
			"on_trial": False, "trial_days_remaining": 0,
			"current_period_end": None, "cancel_at_period_end": False,
		})

	# Need data? pull the subscription
	need_fetch = (
			profile.stripe_customer_id and
			(not profile.subscription_id or not profile.current_period_end) and
			profile.subscription_status in ("trialing", "active")
	)
	if need_fetch:
		try:
			if profile.subscription_id:
				sub = stripe.Subscription.retrieve(profile.subscription_id)
			else:
				subs = stripe.Subscription.list(customer=profile.stripe_customer_id, status="all", limit=3)
				sub = (subs.data or [None])[0]

			if sub:
				profile.subscription_id = sub["id"]
				profile.subscription_status = sub.get("status", profile.subscription_status)
				# 👇 prefer trial_end
				end_ts = sub.get("trial_end") or sub.get("current_period_end")
				profile.current_period_end = (
					datetime.fromtimestamp(end_ts, tz=dt_timezone.utc) if end_ts else None
				)
				profile.cancel_at_period_end = bool(sub.get("cancel_at_period_end", False))
				items = sub.get("items", {}).get("data", [])
				if items and items[0].get("price", {}).get("lookup_key"):
					profile.price_lookup_key = items[0]["price"]["lookup_key"]
				profile.save()
		except Exception:
			pass  # don’t break the UI in dev

	# compute strictly-boolean on_trial + ceil days
	on_trial = (
			profile.subscription_status == BillingProfile.SubStatus.TRIALING
			and bool(profile.current_period_end and profile.current_period_end > timezone.now())
	)

	cpe_iso = profile.current_period_end.isoformat() if profile.current_period_end else None
	trial_days_remaining = 0
	if on_trial and profile.current_period_end:
		delta = profile.current_period_end - timezone.now()
		seconds = max(0, int(delta.total_seconds()))
		trial_days_remaining = (seconds + 86400 - 1) // 86400  # ceil

	return Response({
		"has_profile": True,
		"plan": profile.price_lookup_key,
		"status": profile.subscription_status,
		"on_trial": on_trial,
		"trial_days_remaining": trial_days_remaining,
		"current_period_end": cpe_iso,
		"cancel_at_period_end": profile.cancel_at_period_end,
	})


@api_view(["POST"])
def cancel_subscription(request):
	"""
	Cancels at period end (works for trials & active subs).
	If not subscribed, returns 400.
	"""
	try:
		profile = BillingProfile.objects.get(user=request.user)
	except BillingProfile.DoesNotExist:
		return Response({"error": "No billing profile"}, status=400)

	if not profile.subscription_id:
		return Response({"error": "No active subscription"}, status=400)

	try:
		sub = stripe.Subscription.modify(
			profile.subscription_id,
			cancel_at_period_end=True,
		)
		# reflect locally
		profile.cancel_at_period_end = True
		end_ts = sub.get("current_period_end")
		profile.current_period_end = (
			datetime.fromtimestamp(end_ts, tz=dt_timezone.utc)
			if end_ts else profile.current_period_end
		)
		profile.subscription_status = sub.get("status", profile.subscription_status)
		# lookup key may be in items
		items = sub.get("items", {}).get("data", [])
		if items and items[0].get("price", {}).get("lookup_key"):
			profile.price_lookup_key = items[0]["price"]["lookup_key"]
		profile.save()
	except stripe.error.InvalidRequestError as e:
		return Response({"error": str(e)}, status=400)

	return Response({"ok": True})
