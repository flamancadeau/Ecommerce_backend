"""
Django settings for ecommerce project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


try:
    import environ

    env = environ.Env()
    environ.Env.read_env(os.path.join(BASE_DIR, ".env"))
except Exception:

    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))

    class SimpleEnv:
        def __call__(self, key, default=None):
            return os.getenv(key, default)

        def bool(self, key, default=False):
            val = os.getenv(key)
            if val is None:
                return default
            return str(val).lower() in ("1", "true", "yes", "on")

        def list(self, key, default=None):
            val = os.getenv(key)
            if val is None:
                return default or []
            return [i.strip() for i in val.split(",") if i.strip()]

    env = SimpleEnv()


SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-this-in-production")


DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "django_filters",
    "django_celery_beat",
    "safedelete",
    "timezone_field",
    "drf_yasg",
    "corsheaders",
    "django_extensions",
    # Local apps
    "apps.catalog",
    "apps.inventory",
    "apps.pricing",
    "apps.promotions",
    "apps.orders",
    "apps.audit",
    "apps.scheduler",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.audit.middleware.AuditLogMiddleware",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ecommerce.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ecommerce.wsgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="ecommerce"),
        "USER": env("DB_USER", default="ecommerce_user"),
        "PASSWORD": env("DB_PASSWORD", default="ecommerce_pass"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

# Redis
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

# Cache
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Africa/Kigali")
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.coreapi.AutoSchema",
    "EXCEPTION_HANDLER": "utils.exceptions.custom_exception_handler",
}


# settings.py
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Django Celery Beat
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Periodic Task Schedule
CELERY_BEAT_SCHEDULE = {
    "expire-reservations-every-minute": {
        "task": "apps.orders.tasks.auto_expire_system",
        "schedule": 60.0,
    },
}

# Safe Delete
SAFE_DELETE_INTERPRET_UNDELETED_OBJECTS_AS_CREATED = True

# Audit
AUDIT_LOG_ENABLED = True
AUDIT_LOG_EVENTS = [
    "create",
    "update",
    "delete",
    "price_change",
    "inventory_change",
]

# Swagger settings
SWAGGER_SETTINGS = {
    "SECURITY_DEFINITIONS": {"Basic": {"type": "basic"}},
    "USE_SESSION_AUTH": True,
    "JSON_EDITOR": True,
}
