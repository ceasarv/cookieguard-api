from django.urls import path
from . import views

app_name = 'testing'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # API endpoints - Users
    path('api/users/create/', views.create_test_user, name='create-test-user'),
    path('api/users/list/', views.list_test_users, name='list-test-users'),
    path('api/users/all/', views.list_all_users, name='list-all-users'),
    path('api/users/<str:user_id>/', views.user_detail, name='user-detail'),
    path('api/users/delete/', views.delete_test_user, name='delete-test-user'),
    path('api/users/update-plan/', views.update_user_plan, name='update-user-plan'),

    # API endpoints - Domains
    path('api/domains/create/', views.create_test_domain, name='create-test-domain'),
    path('api/domains/delete/', views.delete_domain, name='delete-domain'),

    # API endpoints - Banners
    path('api/banners/create/', views.create_test_banner, name='create-test-banner'),
    path('api/banners/delete/', views.delete_banner, name='delete-banner'),

    # API endpoints - Scanning
    path('api/scan/trigger/', views.trigger_test_scan, name='trigger-test-scan'),
    path('api/scan/status/<str:task_id>/', views.scan_status, name='scan-status'),
    path('api/scan/history/<str:domain_id>/', views.list_domain_scans, name='list-domain-scans'),
    path('api/scan/detail/<str:scan_id>/', views.get_scan_detail, name='get-scan-detail'),

    # API endpoints - Quick actions
    path('api/quick-setup/', views.quick_setup, name='quick-setup'),
    path('api/cleanup/', views.cleanup_test_data, name='cleanup'),

    # Cookie Database
    path('cookies/', views.cookie_database, name='cookie-database'),
    path('api/cookies/', views.list_cookie_definitions, name='list-cookie-definitions'),
    path('api/cookies/<int:definition_id>/', views.get_cookie_definition, name='get-cookie-definition'),
    path('api/cookies/<int:definition_id>/update/', views.update_cookie_definition, name='update-cookie-definition'),
    path('api/cookies/create/', views.create_cookie_definition, name='create-cookie-definition'),
    path('api/cookies/<int:definition_id>/delete/', views.delete_cookie_definition, name='delete-cookie-definition'),
]
