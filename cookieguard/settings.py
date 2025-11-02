from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")  # load once

ENV = os.getenv("DJANGO_ENV", "development").lower()  # "development" | "production" | "staging"
DEBUG_ENV = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

# Force DEBUG off if ENV=production (even if someone sets DEBUG=true by accident)
DEBUG = False if ENV == "production" else DEBUG_ENV

DJANGO_ENV = ENV

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

if not SECRET_KEY and not DEBUG:
	raise ValueError("DJANGO_SECRET_KEY must be set in production")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

AUTH_USER_MODEL = 'users.User'

INSTALLED_APPS = [
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'corsheaders',
	'rest_framework',
	'users',
	'scanner',
	'billing',
	'domains',
	'banners',
	'consents',
	'support'
]

MIDDLEWARE = [
	"corsheaders.middleware.CorsMiddleware",
	"django.middleware.security.SecurityMiddleware",
	"whitenoise.middleware.WhiteNoiseMiddleware",
	"django.contrib.sessions.middleware.SessionMiddleware",
	"django.middleware.common.CommonMiddleware",
	"django.middleware.csrf.CsrfViewMiddleware",
	"django.contrib.auth.middleware.AuthenticationMiddleware",
	"django.contrib.messages.middleware.MessageMiddleware",
	"django.middleware.clickjacking.XFrameOptionsMiddleware",
	"billing.middleware.BillingAccessMiddleware",
]

# Allow all origins since banners are embedded on external domains
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Optional — restrict methods and headers if you want minimal exposure
CORS_ALLOW_METHODS = [
	"GET",
	"POST",
	"PUT",
	"OPTIONS",
]

CORS_ALLOW_HEADERS = [
	"content-type",
	"authorization",
]

ALLOWED_HOSTS = [
	"localhost",
	"127.0.0.1",
	"cookieguard-api.onrender.com",
	"api.cookieguard.app"
]

REST_FRAMEWORK = {
	'DEFAULT_AUTHENTICATION_CLASSES': (
		'rest_framework_simplejwt.authentication.JWTAuthentication',
	),
	"DEFAULT_PERMISSION_CLASSES": (
		"rest_framework.permissions.IsAuthenticated",
	),
	"DEFAULT_RENDERER_CLASSES": (
		"rest_framework.renderers.JSONRenderer",
	)
}

ROOT_URLCONF = 'cookieguard.urls'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [],
		'APP_DIRS': True,
		'OPTIONS': {
			'context_processors': [
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
			],
		},
	},
]

WSGI_APPLICATION = 'cookieguard.wsgi.application'

# Database
if ENV == "production":
	DATABASES = {
		"default": dj_database_url.config(
			default=os.getenv("DATABASE_URL"),
			conn_max_age=600,
			ssl_require=True
		)
	}
else:
	DATABASES = {
		"default": {
			"ENGINE": "django.db.backends.sqlite3",
			"NAME": BASE_DIR / "db.sqlite3",
		}
	}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
	{
		'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
	},
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
# CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# --- Stripe base ---
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Your existing envs
ESSENTIAL_PRICE_ID = os.getenv("ESSENTIAL_PRICE_ID")
ESSENTIAL_LOOKUP_ID = os.getenv("ESSENTIAL_LOOKUP_ID")
ULTIMATE_PRICE_ID = os.getenv("ULTIMATE_PRICE_ID")
ULTIMATE_LOOKUP_ID = os.getenv("ULTIMATE_LOOKUP_ID")

# Plan selectors (lookup keys)
STRIPE_LOOKUP_STARTER = os.getenv("STRIPE_LOOKUP_STARTER") or ESSENTIAL_LOOKUP_ID or "cg_essential_monthly"
STRIPE_LOOKUP_PRO = os.getenv("STRIPE_LOOKUP_PRO") or ULTIMATE_LOOKUP_ID or "cg_ultimate_monthly"

# Optional: direct price IDs (lets the app skip lookup entirely)
STRIPE_PRICE_STARTER = os.getenv("STRIPE_PRICE_STARTER") or ESSENTIAL_PRICE_ID
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO") or ULTIMATE_PRICE_ID

# Frontend return URLs
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL") or f"{FRONTEND_BASE_URL}/billing/success"
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL") or f"{FRONTEND_BASE_URL}/billing/cancel"
STRIPE_BILLING_PORTAL_RETURN_URL = (
		os.getenv("STRIPE_BILLING_PORTAL_RETURN_URL") or f"{FRONTEND_BASE_URL}/billing/account"
)

# Dev default: Stripe Tax off (enable later once origin address is set in Stripe Test Mode)
STRIPE_AUTOMATIC_TAX = bool(int(os.getenv("STRIPE_AUTOMATIC_TAX", "0")))
