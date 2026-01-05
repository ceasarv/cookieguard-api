from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url
from corsheaders.defaults import default_headers

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
	'drf_spectacular',
	'users',
	'scanner',
	'billing',
	'domains',
	'banners',
	'consents',
	'support',
	'analytics',
	'testing',
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
	"PATCH",
	"DELETE",
	"OPTIONS",
]

CORS_ALLOW_HEADERS = list(default_headers) + [
	"authorization",
]

ALLOWED_HOSTS = [
	"localhost",
	"127.0.0.1",
	"cookieguard-api.onrender.com",
	"api.cookieguard.app",
	".ngrok-free.app",
]

# Production security settings
if ENV == "production":
	SECURE_SSL_REDIRECT = True
	SECURE_HSTS_SECONDS = 31536000  # 1 year
	SECURE_HSTS_INCLUDE_SUBDOMAINS = True
	SECURE_HSTS_PRELOAD = True
	SESSION_COOKIE_SECURE = True
	CSRF_COOKIE_SECURE = True
	SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

REST_FRAMEWORK = {
	'DEFAULT_AUTHENTICATION_CLASSES': (
		'rest_framework_simplejwt.authentication.JWTAuthentication',
	),
	"DEFAULT_PERMISSION_CLASSES": (
		"rest_framework.permissions.IsAuthenticated",
		"users.permissions.NotBlocked",
	),
	"DEFAULT_RENDERER_CLASSES": (
		"rest_framework.renderers.JSONRenderer",
	),
	'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

def preprocessing_filter_spec(endpoints):
	"""Filter out non-API endpoints and normalize tags."""
	filtered = []
	for (path, path_regex, method, callback) in endpoints:
		# Skip non-API paths
		if not path.startswith('/api/'):
			continue
		filtered.append((path, path_regex, method, callback))
	return filtered


def postprocessing_hook(result, generator, request, public):
	"""Normalize all tags to title case and sort alphabetically."""
	# Tag name mapping (lowercase -> proper case)
	tag_map = {
		'auth': 'Auth',
		'users': 'Users',
		'billing': 'Billing',
		'domains': 'Domains',
		'banners': 'Banners',
		'consents': 'Consents',
		'scanner': 'Scanner',
		'analytics': 'Analytics',
		'support': 'Support',
	}

	# Normalize tags in all paths
	for path_data in result.get('paths', {}).values():
		for method_data in path_data.values():
			if isinstance(method_data, dict) and 'tags' in method_data:
				method_data['tags'] = [
					tag_map.get(tag.lower(), tag.title()) for tag in method_data['tags']
				]

	# Sort the tags list alphabetically
	if 'tags' in result:
		result['tags'] = sorted(result['tags'], key=lambda x: x['name'])

	return result


SPECTACULAR_SETTINGS = {
	'TITLE': 'CookieGuard API',
	'DESCRIPTION': 'GDPR-compliant cookie consent management platform with automatic script blocking and granular consent controls.',
	'VERSION': '1.0.0',
	'SERVE_INCLUDE_SCHEMA': False,
	'COMPONENT_SPLIT_REQUEST': True,
	'SCHEMA_PATH_PREFIX': '/api/',
	'SWAGGER_UI_SETTINGS': {
		'deepLinking': True,
		'persistAuthorization': True,
		'displayOperationId': False,
		'tagsSorter': 'alpha',
	},
	'SECURITY': [{'Bearer': []}],
	'TAGS': [
		{'name': 'Analytics', 'description': 'Usage analytics'},
		{'name': 'Auth', 'description': 'Authentication and user management'},
		{'name': 'Banners', 'description': 'Cookie banner configuration'},
		{'name': 'Billing', 'description': 'Subscription and payment management'},
		{'name': 'Consents', 'description': 'Consent logging and analytics'},
		{'name': 'Domains', 'description': 'Domain management'},
		{'name': 'Scanner', 'description': 'Cookie scanning'},
		{'name': 'Support', 'description': 'Support tickets'},
		{'name': 'Users', 'description': 'User administration (staff only)'},
	],
	'PREPROCESSING_HOOKS': ['cookieguard.settings.preprocessing_filter_spec'],
	'POSTPROCESSING_HOOKS': ['cookieguard.settings.postprocessing_hook'],
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

STATICFILES_DIRS = [
	os.path.join(BASE_DIR, 'static'),
]

# Media files (user uploads, screenshots, etc.)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Screenshot settings
SCREENSHOT_DIR = MEDIA_ROOT / "screenshots"
SCREENSHOT_TTL_MINUTES = 10  # Auto-delete after 10 minutes

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Worker settings for 2GB RAM worker
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50  # Restart after 50 tasks to prevent memory leaks
CELERY_WORKER_CONCURRENCY = 2  # 2 concurrent scans (~500MB each = 1GB, leaves 1GB headroom)
CELERY_TASK_TIME_LIMIT = 180  # Hard kill after 3 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 150  # Soft limit to allow cleanup

# --- Stripe base ---
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Pro plan (Essential tier)
PRO_PRICE_ID = os.getenv("PRO_PRICE_ID") or os.getenv("ESSENTIAL_PRICE_ID")
PRO_LOOKUP_ID = os.getenv("PRO_LOOKUP_ID") or os.getenv("ESSENTIAL_LOOKUP_ID")

# Multi-Site plan (Ultimate tier)
MULTI_SITE_PRICE_ID = os.getenv("MULTI_SITE_PRICE_ID") or os.getenv("ULTIMATE_PRICE_ID")
MULTI_SITE_LOOKUP_ID = os.getenv("MULTI_SITE_LOOKUP_ID") or os.getenv("ULTIMATE_LOOKUP_ID")

# Plan selectors (lookup keys)
STRIPE_LOOKUP_PRO = os.getenv("STRIPE_LOOKUP_PRO") or PRO_LOOKUP_ID or "cg_pro_monthly"
STRIPE_LOOKUP_MULTI_SITE = os.getenv("STRIPE_LOOKUP_MULTI_SITE") or MULTI_SITE_LOOKUP_ID or "cg_multi_site_monthly"

# Optional: direct price IDs (lets the app skip lookup entirely)
STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO") or PRO_PRICE_ID
STRIPE_PRICE_MULTI_SITE = os.getenv("STRIPE_PRICE_MULTI_SITE") or MULTI_SITE_PRICE_ID

# Frontend return URLs
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL") or f"{FRONTEND_BASE_URL}/billing/success"
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL") or f"{FRONTEND_BASE_URL}/billing/cancel"
STRIPE_BILLING_PORTAL_RETURN_URL = (
		os.getenv("STRIPE_BILLING_PORTAL_RETURN_URL") or f"{FRONTEND_BASE_URL}/billing/account"
)

# Dev default: Stripe Tax off (enable later once origin address is set in Stripe Test Mode)
STRIPE_AUTOMATIC_TAX = bool(int(os.getenv("STRIPE_AUTOMATIC_TAX", "0")))
