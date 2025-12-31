"""
Seed test data for development.

Usage:
    python manage.py seed_test_data
    python manage.py seed_test_data --users 5 --consents 500
    python manage.py seed_test_data --clear  # Remove seeded data first
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed test users, domains, banners, consents, and usage data'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=3, help='Number of test users to create')
        parser.add_argument('--consents', type=int, default=100, help='Consents per user')
        parser.add_argument('--clear', action='store_true', help='Clear existing test data first')

    def handle(self, *args, **options):
        from domains.models import Domain
        from banners.models import Banner
        from consents.models import ConsentLog
        from billing.models import BillingProfile, UsageRecord

        num_users = options['users']
        num_consents = options['consents']

        if options['clear']:
            self.stdout.write('Clearing existing test data...')
            User.objects.filter(email__endswith='@test.cookieguard.app').delete()
            self.stdout.write(self.style.SUCCESS('Cleared test data'))

        self.stdout.write(f'Creating {num_users} test users with {num_consents} consents each...')

        test_domains = [
            'https://acme-corp.com',
            'https://techstartup.io',
            'https://myblog.dev',
            'https://ecommerce-shop.com',
            'https://portfolio-site.net',
            'https://saas-app.co',
            'https://news-site.org',
            'https://community-forum.com',
        ]

        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
            'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]

        choices = ['accept', 'reject', 'prefs']
        choice_weights = [0.65, 0.25, 0.10]  # 65% accept, 25% reject, 10% prefs

        for i in range(num_users):
            email = f'testuser{i+1}@test.cookieguard.app'

            # Create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'is_active': True}
            )
            if created:
                user.set_password('testpass123')
                user.save()
                self.stdout.write(f'  Created user: {email}')
            else:
                self.stdout.write(f'  User exists: {email}')

            # Ensure billing profile
            BillingProfile.objects.get_or_create(user=user)

            # Create domain
            domain_url = test_domains[i % len(test_domains)]
            domain, _ = Domain.objects.get_or_create(
                url=domain_url,
                user=user,
                defaults={'created_by': user, 'is_ready': True}
            )

            # Create banner
            banner, _ = Banner.objects.get_or_create(
                name=f'Cookie Banner - {domain_url}',
                defaults={
                    'is_active': True,
                    'title': 'We use cookies',
                    'description': 'This website uses cookies to enhance your experience.',
                    'accept_text': 'Accept All',
                    'reject_text': 'Reject All',
                    'prefs_text': 'Preferences',
                    'background_color': '#ffffff',
                    'text_color': '#111827',
                    'accept_bg_color': '#2563eb',
                    'accept_text_color': '#ffffff',
                }
            )
            banner.domains.add(domain)

            # Create usage record for current month
            today = timezone.now().date()
            month_start = today.replace(day=1)
            pageviews = random.randint(50, 900)  # Random usage under free limit

            usage, _ = UsageRecord.objects.update_or_create(
                user=user,
                month=month_start,
                defaults={
                    'pageviews': pageviews,
                    'scans_used': random.randint(0, 3),
                }
            )

            # Create consents spread over last 30 days
            existing_consents = ConsentLog.objects.filter(domain=domain).count()
            consents_to_create = max(0, num_consents - existing_consents)

            consent_objects = []
            for j in range(consents_to_create):
                days_ago = random.randint(0, 30)
                hours_ago = random.randint(0, 23)
                created_at = timezone.now() - timedelta(days=days_ago, hours=hours_ago)

                choice = random.choices(choices, weights=choice_weights)[0]

                # Generate categories based on choice
                if choice == 'accept':
                    categories = {
                        'necessary': True,
                        'analytics': True,
                        'marketing': True,
                        'preferences': True,
                    }
                elif choice == 'reject':
                    categories = {
                        'necessary': True,
                        'analytics': False,
                        'marketing': False,
                        'preferences': False,
                    }
                else:  # prefs
                    categories = {
                        'necessary': True,
                        'analytics': random.choice([True, False]),
                        'marketing': random.choice([True, False]),
                        'preferences': random.choice([True, False]),
                    }

                # Generate fake truncated IP
                truncated_ip = f'{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.0'

                consent_objects.append(ConsentLog(
                    banner=banner,
                    domain=domain,
                    banner_version=1,
                    choice=choice,
                    categories=categories,
                    truncated_ip=truncated_ip,
                    user_agent=random.choice(user_agents),
                    created_at=created_at,
                ))

            if consent_objects:
                ConsentLog.objects.bulk_create(consent_objects)

            self.stdout.write(
                f'  {email}: {domain_url}, {pageviews} pageviews, '
                f'{consents_to_create} new consents'
            )

        self.stdout.write(self.style.SUCCESS(f'\nDone! Created {num_users} test users.'))
        self.stdout.write('Login with any test email and password: testpass123')
