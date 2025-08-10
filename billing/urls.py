from django.urls import path
from . import views

urlpatterns = [
	path('checkout-session/', views.create_checkout_session, name='billing_checkout_session'),
	path('portal-session/', views.create_billing_portal_session, name='billing_portal_session'),
	path('webhook/', views.stripe_webhook, name='stripe_webhook'),
	path('public/pricing/', views.public_pricing, name='public_pricing'),
]
