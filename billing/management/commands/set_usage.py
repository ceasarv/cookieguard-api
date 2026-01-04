"""
Set usage data for a specific user.

Usage:
    python manage.py set_usage --email user@example.com --pageviews 7500
    python manage.py set_usage --user-id ed66fcbd-f26e-4952-b848-1d7cba0eab7b --pageviews 7500
    python manage.py set_usage --email user@example.com --percent 75  # 75% of their plan limit
    python manage.py set_usage --email user@example.com --percent 75 --reset-warnings  # Reset warning flags
    python manage.py set_usage --email user@example.com --percent 75 --send-warning  # Trigger warning email
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Set pageview usage for a specific user'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--email', type=str, help='User email')
        group.add_argument('--user-id', type=str, help='User UUID')

        usage_group = parser.add_mutually_exclusive_group(required=True)
        usage_group.add_argument('--pageviews', type=int, help='Exact pageview count')
        usage_group.add_argument('--percent', type=int, help='Percentage of plan limit (0-100+)')

        parser.add_argument('--scans', type=int, default=None, help='Scans used (optional)')
        parser.add_argument('--reset-warnings', action='store_true', help='Reset all warning flags (70%, 80%, 100%, hard limit)')
        parser.add_argument('--send-warning', action='store_true', help='Trigger appropriate warning email based on usage level')

    def handle(self, *args, **options):
        from billing.models import UsageRecord
        from billing.guards import get_plan_limits, get_user_plan

        # Find user
        if options['email']:
            try:
                user = User.objects.get(email=options['email'])
            except User.DoesNotExist:
                raise CommandError(f"User not found: {options['email']}")
        else:
            try:
                user = User.objects.get(id=options['user_id'])
            except User.DoesNotExist:
                raise CommandError(f"User not found: {options['user_id']}")

        # Calculate pageviews
        limits = get_plan_limits(user)
        plan_limit = limits.get('pageviews_per_month', 250)

        if options['pageviews'] is not None:
            pageviews = options['pageviews']
        else:
            pageviews = int(plan_limit * options['percent'] / 100)

        # Get or create usage record for current month
        today = timezone.now().date()
        month_start = today.replace(day=1)

        defaults = {'pageviews': pageviews}

        # Reset warning flags if requested
        if options['reset_warnings']:
            defaults.update({
                'warning_70_sent': False,
                'warning_80_sent': False,
                'warning_100_sent': False,
                'warning_hard_limit_sent': False,
            })

        usage, created = UsageRecord.objects.update_or_create(
            user=user,
            month=month_start,
            defaults=defaults
        )

        if options['scans'] is not None:
            usage.scans_used = options['scans']
            usage.save(update_fields=['scans_used'])

        percent_used = round((pageviews / plan_limit) * 100, 1) if plan_limit > 0 else 0
        user_plan = get_user_plan(user)

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f"{action} usage for {user.email}:\n"
            f"  Plan: {user_plan}\n"
            f"  Pageviews: {pageviews:,} / {plan_limit:,} ({percent_used}%)\n"
            f"  Month: {month_start.strftime('%B %Y')}"
        ))

        if options['reset_warnings']:
            self.stdout.write(self.style.WARNING("  Warning flags reset to False"))

        # Send warning email if requested
        if options['send_warning']:
            from billing.tasks import send_pageview_limit_warning

            # Determine which warning to send based on usage level
            threshold_type = None
            if percent_used >= 115:
                threshold_type = "blocked"
            elif percent_used >= 100:
                threshold_type = "reached"
            elif percent_used >= 80:
                threshold_type = "approaching"
            elif percent_used >= 70 and user_plan == "free":
                threshold_type = "early_warning"

            if threshold_type:
                # Call synchronously for immediate feedback (not .delay())
                result = send_pageview_limit_warning(user.id, pageviews, plan_limit, threshold_type)
                if result:
                    self.stdout.write(self.style.SUCCESS(
                        f"  Sent '{threshold_type}' warning email to {user.email}"
                    ))
                else:
                    self.stdout.write(self.style.ERROR("  Failed to send warning email"))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  No warning triggered at {percent_used}% (need 70%+ for free, 80%+ for paid)"
                ))
