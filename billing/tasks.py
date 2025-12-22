# billing/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

log = logging.getLogger(__name__)


@shared_task
def send_monthly_reports():
	"""
	Send monthly summary emails to Pro and Agency users.
	Runs on the 1st of each month via Celery Beat.
	"""
	from django.contrib.auth import get_user_model
	from billing.plans import PLAN_LIMITS
	from billing.models import UsageRecord
	from domains.models import Domain
	from consents.models import ConsentLog

	User = get_user_model()

	# Find plans with email_reports enabled
	eligible_plans = [
		plan for plan, limits in PLAN_LIMITS.items()
		if limits.get("email_reports")
	]

	if not eligible_plans:
		log.info("No plans with email_reports enabled")
		return {"sent": 0}

	# Get users on eligible plans with active subscriptions
	users = User.objects.filter(
		billing_profile__plan_tier__in=eligible_plans,
		billing_profile__subscription_status__in=["active", "trialing"]
	)

	# Calculate last month's date range
	today = timezone.now().date()
	last_month_end = today.replace(day=1) - timedelta(days=1)
	last_month_start = last_month_end.replace(day=1)

	sent_count = 0
	for user in users:
		try:
			report_data = generate_user_report(user, last_month_start, last_month_end)
			# TODO: Actually send email via Resend or other email service
			# send_report_email(user.email, report_data)
			log.info(f"Generated monthly report for {user.email}: {report_data['totals']}")
			sent_count += 1
		except Exception as e:
			log.error(f"Failed to generate report for {user.email}: {e}")

	log.info(f"Sent {sent_count} monthly reports")
	return {"sent": sent_count, "period": f"{last_month_start} to {last_month_end}"}


def generate_user_report(user, month_start, month_end):
	"""Generate comprehensive monthly report data for a user."""
	from domains.models import Domain
	from consents.models import ConsentLog
	from billing.models import UsageRecord
	from billing.guards import get_user_plan, get_pageview_limit

	domains = Domain.objects.filter(user=user)

	# Get all consents for the month
	consents = ConsentLog.objects.filter(
		domain__in=domains,
		created_at__date__gte=month_start,
		created_at__date__lte=month_end
	)

	# Aggregate totals
	total_consents = consents.count()
	accepts = consents.filter(choice="accept").count()
	rejects = consents.filter(choice="reject").count()
	prefs = consents.filter(choice="prefs").count()

	accept_rate = (accepts / total_consents * 100) if total_consents > 0 else 0
	reject_rate = (rejects / total_consents * 100) if total_consents > 0 else 0

	# Get pageview usage
	usage = UsageRecord.objects.filter(
		user=user,
		month=month_start
	).first()
	pageviews = usage.pageviews if usage else 0

	# Per-domain breakdown
	domain_stats = []
	for domain in domains:
		domain_consents = consents.filter(domain=domain)
		domain_total = domain_consents.count()
		domain_accepts = domain_consents.filter(choice="accept").count()

		domain_stats.append({
			"url": domain.url,
			"total_consents": domain_total,
			"accepts": domain_accepts,
			"accept_rate": (domain_accepts / domain_total * 100) if domain_total > 0 else 0,
			"last_scan": domain.last_scan_at.isoformat() if domain.last_scan_at else None,
		})

	# Plan info
	plan = get_user_plan(user)
	pageview_limit = get_pageview_limit(user)

	return {
		"user_email": user.email,
		"plan": plan,
		"period": {
			"start": month_start.isoformat(),
			"end": month_end.isoformat(),
		},
		"totals": {
			"consents": total_consents,
			"accepts": accepts,
			"rejects": rejects,
			"prefs": prefs,
			"accept_rate": round(accept_rate, 1),
			"reject_rate": round(reject_rate, 1),
			"pageviews": pageviews,
			"pageview_limit": pageview_limit,
			"pageview_usage_percent": round((pageviews / pageview_limit * 100), 1) if pageview_limit > 0 else 0,
		},
		"domains": domain_stats,
		"domain_count": len(domain_stats),
	}


@shared_task
def send_pageview_limit_warning(user_id, current_pageviews, limit):
	"""
	Send warning email when user reaches their pageview limit.
	"""
	from django.contrib.auth import get_user_model
	User = get_user_model()

	try:
		user = User.objects.get(id=user_id)
		# TODO: Send email via Resend
		log.info(f"Pageview limit warning for {user.email}: {current_pageviews}/{limit}")
	except User.DoesNotExist:
		log.error(f"User {user_id} not found for pageview warning")
