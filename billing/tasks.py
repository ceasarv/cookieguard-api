# billing/tasks.py
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging
import os
import resend

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
def send_welcome_email(user_id):
	"""
	Send welcome email to new users after registration.
	Called asynchronously via Celery after user creation.
	"""
	from django.contrib.auth import get_user_model
	User = get_user_model()

	try:
		user = User.objects.get(id=user_id)

		resend.api_key = os.environ.get("RESEND_API_KEY")
		sender_email = os.environ.get("EMAIL_SENDER", "CookieGuard <noreply@cookieguard.app>")

		subject = "Welcome to CookieGuard!"
		html_body = f"""
		<div style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
			<div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center;">
				<h1 style="color: white; margin: 0; font-size: 28px;">Welcome to CookieGuard!</h1>
			</div>
			<div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px;">
				<p style="color: #374151; font-size: 16px; line-height: 1.6; margin-top: 0;">
					Thanks for signing up! You're now ready to make your website GDPR and CCPA compliant with our easy-to-use cookie consent solution.
				</p>

				<div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 24px 0;">
					<h3 style="margin-top: 0; color: #111827;">Get started in 3 steps:</h3>
					<ol style="color: #374151; padding-left: 20px; margin-bottom: 0;">
						<li style="margin-bottom: 12px;"><strong>Add your website</strong> - Enter your domain to scan for cookies</li>
						<li style="margin-bottom: 12px;"><strong>Customize your banner</strong> - Match it to your brand</li>
						<li style="margin-bottom: 0;"><strong>Install the script</strong> - One line of code and you're compliant</li>
					</ol>
				</div>

				<div style="text-align: center; margin: 24px 0;">
					<a href="https://app.cookieguard.app/dashboard"
					   style="display: inline-block; background: #14b8a6; color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
						Go to Dashboard
					</a>
				</div>

				<div style="background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 8px; padding: 16px; margin-top: 24px;">
					<p style="color: #0f766e; margin: 0; font-size: 14px;">
						<strong>Free plan includes:</strong> 250 pageviews/month, 1 domain, full banner customization, and cookie scanning.
					</p>
				</div>

				<p style="color: #9ca3af; font-size: 14px; margin-top: 30px; margin-bottom: 0;">
					Questions? Just reply to this email - we're here to help!
				</p>
			</div>
		</div>
		"""

		resend.Emails.send({
			"from": sender_email,
			"to": user.email,
			"subject": subject,
			"html": html_body,
		})

		log.info(f"[Email Sent] Welcome email to {user.email}")
		return {"to": user.email, "type": "welcome"}

	except User.DoesNotExist:
		log.error(f"User {user_id} not found for welcome email")
		return None
	except Exception as e:
		log.error(f"[Email Error] Failed to send welcome email to user {user_id}: {e}")
		return None


@shared_task
def send_pageview_limit_warning(user_id, current_pageviews, limit, threshold_type="reached"):
	"""
	Send warning email when user approaches or reaches their pageview limit.

	Args:
		user_id: User's ID
		current_pageviews: Current pageview count
		limit: Base pageview limit for the plan
		threshold_type: One of "early_warning" (70%), "approaching" (80%), "reached" (100%), or "blocked" (115%)
	"""
	from django.contrib.auth import get_user_model
	from billing.guards import get_user_plan
	User = get_user_model()

	messages = {
		"early_warning": {
			"subject": "You've used 70% of your pageviews",
			"emoji": "📊",
			"color": "#3b82f6",
			"message": "You've used 70% of your monthly pageview limit on the Free plan. Upgrade to Pro for 10,000 pageviews per month and never worry about limits again.",
		},
		"approaching": {
			"subject": "You're approaching your pageview limit",
			"emoji": "⚠️",
			"color": "#f59e0b",
			"message": "You've used 80% of your monthly pageview limit. Consider upgrading to avoid interruptions.",
		},
		"reached": {
			"subject": "You've reached your pageview limit",
			"emoji": "🚨",
			"color": "#ef4444",
			"message": "You've reached your monthly pageview limit. You're now in a 15% grace period. Upgrade to continue tracking.",
		},
		"blocked": {
			"subject": "Pageview tracking paused",
			"emoji": "⛔",
			"color": "#dc2626",
			"message": "You've exceeded your grace period. Pageview tracking is paused until next month or until you upgrade.",
		},
	}

	msg = messages.get(threshold_type, messages["reached"])

	try:
		user = User.objects.get(id=user_id)
		percent_used = round((current_pageviews / limit) * 100, 1) if limit > 0 else 0
		plan = get_user_plan(user)

		# Send email via Resend
		try:
			resend.api_key = os.environ.get("RESEND_API_KEY")
			sender_email = os.environ.get("EMAIL_SENDER", "CookieGuard <noreply@cookieguard.app>")

			subject = f"{msg['emoji']} {msg['subject']}"
			html_body = f"""
			<div style="font-family: system-ui, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
				<div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%); padding: 20px; border-radius: 8px 8px 0 0;">
					<h1 style="color: white; margin: 0; font-size: 24px;">CookieGuard</h1>
				</div>
				<div style="background: #f9fafb; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
					<h2 style="color: {msg['color']}; margin-top: 0;">{msg['emoji']} {msg['subject']}</h2>
					<p style="color: #374151; font-size: 16px; line-height: 1.6;">{msg['message']}</p>

					<div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin: 20px 0;">
						<h3 style="margin-top: 0; color: #111827;">Usage Summary</h3>
						<p style="margin: 8px 0; color: #6b7280;">
							<strong>Plan:</strong> {plan.capitalize()}
						</p>
						<p style="margin: 8px 0; color: #6b7280;">
							<strong>Pageviews:</strong> {current_pageviews:,} / {limit:,} ({percent_used}%)
						</p>
						<div style="background: #e5e7eb; border-radius: 4px; height: 8px; margin-top: 12px;">
							<div style="background: {msg['color']}; border-radius: 4px; height: 8px; width: {min(percent_used, 100)}%;"></div>
						</div>
					</div>

					<a href="https://app.cookieguard.app/billing"
					   style="display: inline-block; background: #2563eb; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">
						Upgrade Your Plan
					</a>

					<p style="color: #9ca3af; font-size: 14px; margin-top: 30px;">
						If you have questions, reply to this email or contact support@cookieguard.app
					</p>
				</div>
			</div>
			"""

			resend.Emails.send({
				"from": sender_email,
				"to": user.email,
				"subject": subject,
				"html": html_body,
			})

			log.info(
				f"[Email Sent] Pageview limit warning ({threshold_type}) for {user.email}: "
				f"{current_pageviews}/{limit} ({percent_used}%)"
			)

		except Exception as email_err:
			log.error(f"[Email Error] Failed to send pageview warning to {user.email}: {email_err}")

		return {
			"to": user.email,
			"threshold_type": threshold_type,
			"current_pageviews": current_pageviews,
			"limit": limit,
			"percent_used": percent_used,
		}

	except User.DoesNotExist:
		log.error(f"User {user_id} not found for pageview warning")
		return None
