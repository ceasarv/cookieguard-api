from django.urls import path
from .views import register, login, me, google_login, onboarding_next

urlpatterns = [
	path("register/", register, name="register"),
	path("login/", login, name="login"),
	path("me/", me, name="me"),
	path("google/", google_login, name="google_login"),
	path("onboarding/next/", onboarding_next, name="onboarding_next"),
]
