from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import get_user_model
from django.utils import timezone
import secrets
import json

from django.db.models import Q

from domains.models import Domain, CookieCategory
from banners.models import Banner
from billing.models import BillingProfile, UsageRecord
from scanner.models import ScanResult, CookieDefinition
from scanner.tasks import run_scan_task
from celery.result import AsyncResult

User = get_user_model()


@staff_member_required
def dashboard(request):
    """Main testing dashboard view."""
    # Get recent test users (created in last 7 days with test_ prefix)
    recent_users = User.objects.filter(
        email__startswith='test_',
        date_joined__gte=timezone.now() - timezone.timedelta(days=7)
    ).order_by('-date_joined')[:10]

    # Get all domains for test users
    test_domains = Domain.objects.filter(
        user__email__startswith='test_'
    ).select_related('user').order_by('-created_at')[:20]

    # Stats
    stats = {
        'total_test_users': User.objects.filter(email__startswith='test_').count(),
        'total_test_domains': Domain.objects.filter(user__email__startswith='test_').count(),
        'total_banners': Banner.objects.filter(domains__user__email__startswith='test_').distinct().count(),
    }

    context = {
        'recent_users': recent_users,
        'test_domains': test_domains,
        'stats': stats,
    }
    return render(request, 'testing/dashboard.html', context)


@staff_member_required
@require_POST
@csrf_protect
def create_test_user(request):
    """Create a new test user with specified plan tier."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    plan_tier = data.get('plan_tier', 'free')

    # Generate unique email
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    random_suffix = secrets.token_hex(4)
    email = f"test_{timestamp}_{random_suffix}@cookieguard.test"
    password = secrets.token_urlsafe(16)

    # Create user
    user = User.objects.create_user(email=email, password=password)

    # Create billing profile
    profile = BillingProfile.objects.create(
        user=user,
        plan_tier=plan_tier,
        subscription_status='active' if plan_tier != 'free' else 'inactive',
    )

    return JsonResponse({
        'success': True,
        'user': {
            'id': str(user.id),
            'email': user.email,
            'password': password,  # Show password so tester can login
            'plan_tier': profile.plan_tier,
            'subscription_status': profile.subscription_status,
        }
    })


@staff_member_required
@require_POST
@csrf_protect
def create_test_domain(request):
    """Create a domain for a test user."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')
    url = data.get('url', 'https://example.com')

    if not user_id:
        return JsonResponse({'success': False, 'error': 'user_id required'}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'

    # Create domain
    domain = Domain.objects.create(
        url=url,
        user=user,
        created_by=request.user,
        is_ready=True,
    )

    return JsonResponse({
        'success': True,
        'domain': {
            'id': str(domain.id),
            'url': domain.url,
            'embed_key': domain.embed_key,
            'user_email': user.email,
        }
    })


@staff_member_required
@require_POST
@csrf_protect
def create_test_banner(request):
    """Create a banner for a domain."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    domain_id = data.get('domain_id')

    if not domain_id:
        return JsonResponse({'success': False, 'error': 'domain_id required'}, status=400)

    try:
        domain = Domain.objects.get(id=domain_id)
    except Domain.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Domain not found'}, status=404)

    # Create banner with defaults
    banner = Banner.objects.create(
        name=f"Test Banner {secrets.token_hex(4)}",
        title="Cookie Consent",
        description="We use cookies to improve your experience.",
        is_active=True,
    )
    banner.domains.add(domain)

    return JsonResponse({
        'success': True,
        'banner': {
            'id': banner.id,
            'name': banner.name,
            'domain_url': domain.url,
            'embed_key': domain.embed_key,
        }
    })


@staff_member_required
@require_POST
@csrf_protect
def trigger_test_scan(request):
    """Trigger a scan for a domain."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    domain_id = data.get('domain_id')
    url = data.get('url')
    save_result = data.get('save_result', True)  # Default to saving

    if not domain_id and not url:
        return JsonResponse({'success': False, 'error': 'domain_id or url required'}, status=400)

    if domain_id:
        try:
            domain = Domain.objects.get(id=domain_id)
            url = domain.url
        except Domain.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Domain not found'}, status=404)

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'

    # Queue scan with save_result option
    task = run_scan_task.delay(
        url,
        domain_id=domain_id,
        save_result=save_result,
    )

    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'url': url,
        'domain_id': domain_id,
    })


@staff_member_required
@require_GET
def scan_status(request, task_id):
    """Check the status of a scan task with progress info."""
    result = AsyncResult(task_id)

    response = {
        'task_id': task_id,
        'status': result.status,
        'ready': result.ready(),
    }

    # Include progress info for PROGRESS state
    if result.status == 'PROGRESS' and result.info:
        response['progress'] = result.info.get('progress', 0)
        response['stage'] = result.info.get('stage', '')
        response['message'] = result.info.get('message', '')
        response['details'] = result.info.get('details', {})

    if result.ready():
        if result.successful():
            response['result'] = result.result
            response['progress'] = 100
        else:
            response['error'] = str(result.result)

    return JsonResponse(response)


@staff_member_required
@require_POST
@csrf_protect
def quick_setup(request):
    """One-click setup: Create user, domain, banner, and trigger scan."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    plan_tier = data.get('plan_tier', 'free')
    url = data.get('url', 'https://example.com')
    trigger_scan = data.get('trigger_scan', False)

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'

    # 1. Create user
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    random_suffix = secrets.token_hex(4)
    email = f"test_{timestamp}_{random_suffix}@cookieguard.test"
    password = secrets.token_urlsafe(16)

    user = User.objects.create_user(email=email, password=password)

    # 2. Create billing profile
    profile = BillingProfile.objects.create(
        user=user,
        plan_tier=plan_tier,
        subscription_status='active' if plan_tier != 'free' else 'inactive',
    )

    # 3. Create domain
    domain = Domain.objects.create(
        url=url,
        user=user,
        created_by=request.user,
        is_ready=True,
    )

    # 4. Create banner
    banner = Banner.objects.create(
        name="Test Banner",
        title="Cookie Consent",
        description="We use cookies to improve your experience.",
        is_active=True,
    )
    banner.domains.add(domain)

    result = {
        'success': True,
        'user': {
            'id': str(user.id),
            'email': user.email,
            'password': password,
            'plan_tier': profile.plan_tier,
        },
        'domain': {
            'id': str(domain.id),
            'url': domain.url,
            'embed_key': domain.embed_key,
        },
        'banner': {
            'id': banner.id,
            'name': banner.name,
        },
    }

    # 5. Optionally trigger scan
    if trigger_scan:
        task = run_scan_task.delay(url)
        result['scan'] = {
            'task_id': task.id,
            'url': url,
        }

    return JsonResponse(result)


@staff_member_required
@require_POST
@csrf_protect
def delete_test_user(request):
    """Delete a test user and all their data."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')

    if not user_id:
        return JsonResponse({'success': False, 'error': 'user_id required'}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

    # Safety check: only delete test users
    if not user.email.startswith('test_'):
        return JsonResponse({
            'success': False,
            'error': 'Can only delete test users (email must start with test_)'
        }, status=403)

    email = user.email
    user.delete()

    return JsonResponse({
        'success': True,
        'deleted_email': email,
    })


@staff_member_required
@require_POST
@csrf_protect
def cleanup_test_data(request):
    """Delete all test users and their data."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}

    confirm = data.get('confirm', False)

    if not confirm:
        # Return count of what would be deleted
        test_users = User.objects.filter(email__startswith='test_')
        count = test_users.count()
        return JsonResponse({
            'success': False,
            'message': f'This will delete {count} test users. Pass confirm=true to proceed.',
            'count': count,
        })

    # Delete all test users (cascades to domains, banners, etc.)
    test_users = User.objects.filter(email__startswith='test_')
    count = test_users.count()
    test_users.delete()

    return JsonResponse({
        'success': True,
        'deleted_count': count,
    })


@staff_member_required
@require_GET
def list_test_users(request):
    """List all test users with their domains and plans."""
    test_users = User.objects.filter(email__startswith='test_').order_by('-date_joined')[:50]

    users_data = []
    for user in test_users:
        profile = getattr(user, 'billing_profile', None)
        domains = Domain.objects.filter(user=user)

        users_data.append({
            'id': str(user.id),
            'email': user.email,
            'date_joined': user.date_joined.isoformat(),
            'plan_tier': profile.plan_tier if profile else 'none',
            'subscription_status': profile.subscription_status if profile else 'none',
            'domain_count': domains.count(),
            'domains': [
                {'id': str(d.id), 'url': d.url, 'embed_key': d.embed_key}
                for d in domains[:5]
            ],
        })

    return JsonResponse({
        'success': True,
        'count': len(users_data),
        'users': users_data,
    })


@staff_member_required
@require_GET
def list_all_users(request):
    """List all users in the database with search and pagination."""
    search = request.GET.get('search', '').strip()
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 25))

    users = User.objects.all().order_by('-date_joined')

    if search:
        users = users.filter(email__icontains=search)

    total = users.count()
    start = (page - 1) * per_page
    end = start + per_page
    users = users[start:end]

    users_data = []
    for user in users:
        profile = getattr(user, 'billing_profile', None)
        domain_count = Domain.objects.filter(user=user).count()

        users_data.append({
            'id': str(user.id),
            'email': user.email,
            'is_staff': user.is_staff,
            'is_active': user.is_active,
            'is_blocked': user.is_blocked,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'plan_tier': profile.plan_tier if profile else 'none',
            'subscription_status': profile.subscription_status if profile else 'none',
            'domain_count': domain_count,
        })

    return JsonResponse({
        'success': True,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
        'users': users_data,
    })


@staff_member_required
@require_GET
def user_detail(request, user_id):
    """Get detailed info about a user including domains, banners, billing."""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

    profile = getattr(user, 'billing_profile', None)

    # Get domains with their banners
    domains = Domain.objects.filter(user=user).order_by('-created_at')
    domains_data = []
    for domain in domains:
        banners = Banner.objects.filter(domains=domain)
        domains_data.append({
            'id': str(domain.id),
            'url': domain.url,
            'embed_key': domain.embed_key,
            'is_ready': domain.is_ready,
            'created_at': domain.created_at.isoformat(),
            'last_scan_at': domain.last_scan_at.isoformat() if domain.last_scan_at else None,
            'banners': [
                {
                    'id': b.id,
                    'name': b.name,
                    'is_active': b.is_active,
                    'title': b.title,
                    'theme': b.theme,
                    'position': b.position,
                    'type': b.type,
                }
                for b in banners
            ],
            'cookie_categories': [
                {
                    'id': c.id,
                    'category': c.category,
                    'script_name': c.script_name,
                    'script_pattern': c.script_pattern,
                }
                for c in domain.cookie_categories.all()
            ],
        })

    # Get usage records
    usage_records = []
    if profile:
        records = UsageRecord.objects.filter(user=user).order_by('-month')[:6]
        usage_records = [
            {
                'month': r.month.isoformat(),
                'pageviews': r.pageviews,
                'scans_used': r.scans_used,
            }
            for r in records
        ]

    return JsonResponse({
        'success': True,
        'user': {
            'id': str(user.id),
            'email': user.email,
            'is_staff': user.is_staff,
            'is_active': user.is_active,
            'is_blocked': user.is_blocked,
            'date_joined': user.date_joined.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'on_boarding_step': user.on_boarding_step,
        },
        'billing': {
            'plan_tier': profile.plan_tier if profile else 'none',
            'subscription_status': profile.subscription_status if profile else 'none',
            'stripe_customer_id': profile.stripe_customer_id if profile else None,
            'subscription_id': profile.subscription_id if profile else None,
            'current_period_end': profile.current_period_end.isoformat() if profile and profile.current_period_end else None,
            'cancel_at_period_end': profile.cancel_at_period_end if profile else False,
            'trial_used': profile.trial_used if profile else False,
        } if profile else None,
        'domains': domains_data,
        'usage_records': usage_records,
        'stats': {
            'domain_count': len(domains_data),
            'banner_count': sum(len(d['banners']) for d in domains_data),
            'active_banners': sum(1 for d in domains_data for b in d['banners'] if b['is_active']),
        },
    })


@staff_member_required
@require_POST
@csrf_protect
def update_user_plan(request):
    """Update a user's plan tier (for testing purposes)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    user_id = data.get('user_id')
    plan_tier = data.get('plan_tier', 'free')
    subscription_status = data.get('subscription_status')

    if not user_id:
        return JsonResponse({'success': False, 'error': 'user_id required'}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

    profile, created = BillingProfile.objects.get_or_create(user=user)
    profile.plan_tier = plan_tier

    if subscription_status:
        profile.subscription_status = subscription_status
    elif plan_tier != 'free':
        profile.subscription_status = 'active'
    else:
        profile.subscription_status = 'inactive'

    profile.save()

    return JsonResponse({
        'success': True,
        'user_id': str(user.id),
        'plan_tier': profile.plan_tier,
        'subscription_status': profile.subscription_status,
    })


@staff_member_required
@require_POST
@csrf_protect
def delete_domain(request):
    """Delete a domain."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    domain_id = data.get('domain_id')

    if not domain_id:
        return JsonResponse({'success': False, 'error': 'domain_id required'}, status=400)

    try:
        domain = Domain.objects.get(id=domain_id)
    except Domain.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Domain not found'}, status=404)

    url = domain.url
    domain.delete()

    return JsonResponse({
        'success': True,
        'deleted_url': url,
    })


@staff_member_required
@require_POST
@csrf_protect
def delete_banner(request):
    """Delete a banner."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    banner_id = data.get('banner_id')

    if not banner_id:
        return JsonResponse({'success': False, 'error': 'banner_id required'}, status=400)

    try:
        banner = Banner.objects.get(id=banner_id)
    except Banner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Banner not found'}, status=404)

    name = banner.name
    banner.delete()

    return JsonResponse({
        'success': True,
        'deleted_name': name,
    })


@staff_member_required
@require_GET
def list_domain_scans(request, domain_id):
    """List scan history for a domain."""
    try:
        domain = Domain.objects.get(id=domain_id)
    except Domain.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Domain not found'}, status=404)

    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))

    scans = ScanResult.objects.filter(domain=domain).order_by('-scanned_at')
    total = scans.count()
    start = (page - 1) * per_page
    end = start + per_page
    scans = scans[start:end]

    scans_data = []
    for scan in scans:
        scans_data.append({
            'id': str(scan.id),
            'url': scan.url,
            'scanned_at': scan.scanned_at.isoformat(),
            'cookies_found': scan.cookies_found,
            'first_party_count': scan.first_party_count,
            'third_party_count': scan.third_party_count,
            'tracker_count': scan.tracker_count,
            'unclassified_count': scan.unclassified_count,
            'compliance_score': scan.compliance_score,
            'has_consent_banner': scan.has_consent_banner,
            'pages_scanned': scan.pages_scanned,
            'duration': scan.duration,
        })

    return JsonResponse({
        'success': True,
        'domain_id': str(domain.id),
        'domain_url': domain.url,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page if total > 0 else 0,
        'scans': scans_data,
    })


@staff_member_required
@require_GET
def get_scan_detail(request, scan_id):
    """Get detailed scan result including full result JSON."""
    try:
        scan = ScanResult.objects.get(id=scan_id)
    except ScanResult.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Scan not found'}, status=404)

    # Get cookies for this scan
    cookies = scan.cookies.all()
    cookies_data = [
        {
            'name': c.name,
            'domain': c.domain,
            'path': c.path,
            'expires': c.expires,
            'type': c.type,
            'classification': c.classification,
        }
        for c in cookies
    ]

    return JsonResponse({
        'success': True,
        'scan': {
            'id': str(scan.id),
            'domain_id': str(scan.domain.id) if scan.domain else None,
            'url': scan.url,
            'scanned_at': scan.scanned_at.isoformat(),
            'cookies_found': scan.cookies_found,
            'first_party_count': scan.first_party_count,
            'third_party_count': scan.third_party_count,
            'tracker_count': scan.tracker_count,
            'unclassified_count': scan.unclassified_count,
            'compliance_score': scan.compliance_score,
            'has_consent_banner': scan.has_consent_banner,
            'pages_scanned': scan.pages_scanned,
            'duration': scan.duration,
            'issues': scan.issues,
            'result': scan.result,  # Full scan result JSON
            'cookies': cookies_data,
        },
    })


# =============================================================================
# Cookie Database Views
# =============================================================================

@staff_member_required
def cookie_database(request):
    """Cookie database management page."""
    stats = {
        'total_definitions': CookieDefinition.objects.count(),
        'verified_count': CookieDefinition.objects.filter(is_verified=True).count(),
        'crowdsourced_count': CookieDefinition.objects.filter(is_verified=False, times_classified__gt=0).count(),
        'unclassified_count': CookieDefinition.objects.filter(times_classified=0, is_verified=False).count(),
        'category_counts': {
            'necessary': CookieDefinition.objects.filter(category='necessary').count(),
            'functional': CookieDefinition.objects.filter(category='functional').count(),
            'analytics': CookieDefinition.objects.filter(category='analytics').count(),
            'marketing': CookieDefinition.objects.filter(category='marketing').count(),
            'other': CookieDefinition.objects.filter(category='other').count(),
        }
    }
    return render(request, 'testing/cookie_database.html', {'stats': stats})


@staff_member_required
@require_GET
def list_cookie_definitions(request):
    """List cookie definitions with filtering and pagination."""
    search = request.GET.get('search', '').strip()
    category = request.GET.get('category', '')
    provider = request.GET.get('provider', '')
    verified_only = request.GET.get('verified', '') == 'true'
    unclassified_only = request.GET.get('unclassified', '') == 'true'
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 50))

    queryset = CookieDefinition.objects.all()

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search) |
            Q(domain_pattern__icontains=search) |
            Q(provider__icontains=search) |
            Q(description__icontains=search)
        )
    if category:
        queryset = queryset.filter(category=category)
    if provider:
        queryset = queryset.filter(provider__icontains=provider)
    if verified_only:
        queryset = queryset.filter(is_verified=True)
    if unclassified_only:
        queryset = queryset.filter(times_classified=0, is_verified=False)

    total = queryset.count()
    start = (page - 1) * per_page
    definitions = queryset.order_by('-times_seen')[start:start + per_page]

    data = []
    for d in definitions:
        data.append({
            'id': d.id,
            'name': d.name,
            'domain_pattern': d.domain_pattern,
            'category': d.category,
            'description': d.description,
            'provider': d.provider,
            'times_seen': d.times_seen,
            'times_classified': d.times_classified,
            'confidence': round(d.classification_confidence, 2),
            'is_verified': d.is_verified,
            'votes': {
                'necessary': d.votes_necessary,
                'functional': d.votes_functional,
                'analytics': d.votes_analytics,
                'marketing': d.votes_marketing,
                'other': d.votes_other,
            },
            'created_at': d.created_at.isoformat(),
            'updated_at': d.updated_at.isoformat(),
        })

    return JsonResponse({
        'success': True,
        'definitions': data,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page if total > 0 else 0,
    })


@staff_member_required
@require_GET
def get_cookie_definition(request, definition_id):
    """Get a single cookie definition."""
    try:
        d = CookieDefinition.objects.get(id=definition_id)
    except CookieDefinition.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Definition not found'}, status=404)

    return JsonResponse({
        'success': True,
        'definition': {
            'id': d.id,
            'name': d.name,
            'domain_pattern': d.domain_pattern,
            'category': d.category,
            'description': d.description,
            'provider': d.provider,
            'times_seen': d.times_seen,
            'times_classified': d.times_classified,
            'confidence': round(d.classification_confidence, 2),
            'is_verified': d.is_verified,
            'votes': {
                'necessary': d.votes_necessary,
                'functional': d.votes_functional,
                'analytics': d.votes_analytics,
                'marketing': d.votes_marketing,
                'other': d.votes_other,
            },
        }
    })


@staff_member_required
@require_POST
@csrf_protect
def update_cookie_definition(request, definition_id):
    """Update a cookie definition."""
    try:
        definition = CookieDefinition.objects.get(id=definition_id)
    except CookieDefinition.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Definition not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    # Update fields
    if 'category' in data:
        definition.category = data['category']
    if 'description' in data:
        definition.description = data['description']
    if 'provider' in data:
        definition.provider = data['provider']
    if 'is_verified' in data:
        definition.is_verified = data['is_verified']
        if data['is_verified']:
            definition.classification_confidence = 1.0

    definition.save()

    return JsonResponse({
        'success': True,
        'definition': {
            'id': definition.id,
            'name': definition.name,
            'category': definition.category,
            'is_verified': definition.is_verified,
        }
    })


@staff_member_required
@require_POST
@csrf_protect
def create_cookie_definition(request):
    """Create a new cookie definition."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    domain_pattern = data.get('domain_pattern', '').strip()

    if not name:
        return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

    # Check if already exists
    if CookieDefinition.objects.filter(name=name, domain_pattern=domain_pattern).exists():
        return JsonResponse({'success': False, 'error': 'Definition already exists'}, status=400)

    definition = CookieDefinition.objects.create(
        name=name,
        domain_pattern=domain_pattern,
        category=data.get('category', 'other'),
        description=data.get('description', ''),
        provider=data.get('provider', ''),
        is_verified=data.get('is_verified', True),
        classification_confidence=1.0 if data.get('is_verified', True) else 0,
    )

    return JsonResponse({
        'success': True,
        'definition': {
            'id': definition.id,
            'name': definition.name,
            'domain_pattern': definition.domain_pattern,
            'category': definition.category,
        }
    })


@staff_member_required
@require_POST
@csrf_protect
def delete_cookie_definition(request, definition_id):
    """Delete a cookie definition."""
    try:
        definition = CookieDefinition.objects.get(id=definition_id)
    except CookieDefinition.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Definition not found'}, status=404)

    name = definition.name
    definition.delete()

    return JsonResponse({
        'success': True,
        'deleted': name,
    })
