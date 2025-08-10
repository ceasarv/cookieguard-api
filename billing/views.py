import os
import stripe
from datetime import datetime, timezone

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import BillingProfile

stripe.api_key = settings.STRIPE_SECRET_KEY
if getattr(settings, 'STRIPE_API_VERSION', None):
	stripe.api_version = settings.STRIPE_API_VERSION


def _ensure_customer(user) -> str:
	"""Create or return a Stripe customer for this user."""
	profile, _ = BillingProfile.objects.get_or_create(user=user)
	if profile.stripe_customer_id:
		return profile.stripe_customer_id
	customer = stripe.Customer.create(email=getattr(user, 'email', None))
	profile.stripe_customer_id = customer.id
	profile.save(update_fields=['stripe_customer_id'])
	return customer.id


def _resolve_price_id(lookup_key: str) -> str:
	prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
	if not prices.data:
		raise ValueError(f'Price not found for lookup_key={lookup_key}')
	return prices.data[0].id


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
	"""
	Body: { "plan": "starter" | "pro" }
	Creates a Stripe Checkout Session for a subscription with optional trial.
	"""
	plan = (request.data.get('plan') or '').strip().lower()
	if plan not in ('starter', 'pro'):
		return Response({'error': 'Invalid plan'}, status=400)

	lookup = settings.STRIPE_LOOKUP_STARTER if plan == 'starter' else settings.STRIPE_LOOKUP_PRO
	try:
		price_id = _resolve_price_id(lookup)
	except Exception as e:
		return Response({'error': str(e)}, status=400)

	customer_id = _ensure_customer(request.user)
	trial_days = int(getattr(settings, 'TRIAL_DAYS', os.getenv('TRIAL_DAYS', 14)))

	session = stripe.checkout.Session.create(
		mode='subscription',
		customer=customer_id,
		line_items=[{'price': price_id, 'quantity': 1}],
		success_url=f"{settings.STRIPE_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
		cancel_url=settings.STRIPE_CANCEL_URL,
		allow_promotion_codes=True,
		automatic_tax={'enabled': True},
		subscription_data={
			'trial_period_days': trial_days,
			# Optional: attach metadata
			'metadata': {'user_id': str(request.user.id), 'plan': plan, 'lookup_key': lookup},
		},
		# To prefill email if no customer:
		customer_update={'name': 'auto'},
	)

	# Store intended lookup key so webhook can set it on profile
	BillingProfile.objects.filter(user=request.user).update(price_lookup_key=lookup)

	return Response({'url': session.url})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_billing_portal_session(request):
	"""Creates a Stripe Billing Portal session so users can manage payment methods/cancel."""
	profile = BillingProfile.objects.get(user=request.user)
	if not profile.stripe_customer_id:
		# Ensure there is a customer to open a portal for
		customer_id = _ensure_customer(request.user)
	else:
		customer_id = profile.stripe_customer_id

	portal = stripe.billing_portal.Session.create(
		customer=customer_id,
		return_url=settings.STRIPE_BILLING_PORTAL_RETURN_URL,
	)
	return Response({'url': portal.url})


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):
	payload = request.body
	sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
	wh_secret = settings.STRIPE_WEBHOOK_SECRET

	try:
		event = stripe.Webhook.construct_event(
			payload=payload, sig_header=sig_header, secret=wh_secret
		)
	except stripe.error.SignatureVerificationError:
		return Response(status=400)
	except ValueError:
		return Response(status=400)

	# Handle events
	type_ = event['type']
	data = event['data']['object']

	# Helper to update profile by subscription
	def _update_profile_from_sub(subscription):
		customer_id = subscription['customer']
		try:
			profile = BillingProfile.objects.get(stripe_customer_id=customer_id)
		except BillingProfile.DoesNotExist:
			return
		profile.subscription_id = subscription['id']
		profile.subscription_status = subscription['status']
		end_ts = subscription.get('current_period_end')
		profile.current_period_end = (
			datetime.fromtimestamp(end_ts, tz=timezone.utc) if end_ts else None
		)
		# price lookup key if present
		items = subscription.get('items', {}).get('data', [])
		if items and items[0].get('price', {}).get('lookup_key'):
			profile.price_lookup_key = items[0]['price']['lookup_key']
		profile.save()

	if type_ == 'checkout.session.completed':
		# Expand to get subscription details
		session = stripe.checkout.Session.retrieve(data['id'], expand=['subscription'])
		subscription = session.get('subscription')
		if isinstance(subscription, dict):
			_update_profile_from_sub(subscription)

	elif type_ in ('customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted'):
		_update_profile_from_sub(data)

	elif type_ == 'invoice.payment_failed':
		# Optional: mark as past_due
		sub = data.get('subscription')
		if sub:
			sub_obj = stripe.Subscription.retrieve(sub)
			_update_profile_from_sub(sub_obj)

	return Response(status=200)


# Optional: public pricing API so your UI can read prices dynamically (cached externally e.g., via CDN)
@api_view(['GET'])
@permission_classes([AllowAny])
def public_pricing(request):
	lookup_keys = [settings.STRIPE_LOOKUP_STARTER, settings.STRIPE_LOOKUP_PRO]
	prices = stripe.Price.list(lookup_keys=lookup_keys, active=True, expand=['data.product'])
	out = []
	for p in prices.data:
		out.append({
			'lookup_key': p.lookup_key,
			'unit_amount': p.unit_amount,  # cents
			'currency': p.currency,  # "usd"
			'interval': p.recurring['interval'] if p.recurring else None,  # "month"
			'product_name': p.product['name'] if isinstance(p.product, dict) else p.product,
			'price_id': p.id,
		})
	return Response(out)
