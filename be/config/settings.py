"""Environment-driven Django settings for local-staging and live-staging."""

from pathlib import Path

from compass.common.config import env, env_bool, env_csv, env_float, env_int, required_env

BASE_DIR = Path(__file__).resolve().parent.parent

APP_ENV = env("APP_ENV", "local-staging")
if APP_ENV not in {"local-staging", "live-staging"}:
    raise ValueError("APP_ENV must be either local-staging or live-staging")

IS_LOCAL_STAGING = APP_ENV == "local-staging"
DEBUG = env_bool("DEBUG", IS_LOCAL_STAGING)
if not IS_LOCAL_STAGING and DEBUG:
    raise ValueError("DEBUG must be false in live-staging")

SECRET_KEY = required_env("SECRET_KEY")
ALLOWED_HOSTS = env_csv(
    "ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "[::1]"] if IS_LOCAL_STAGING else [],
)
if not IS_LOCAL_STAGING and not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS is required in live-staging")

CSRF_TRUSTED_ORIGINS = env_csv(
    "CSRF_TRUSTED_ORIGINS",
    ["http://localhost:8080", "http://127.0.0.1:8080"] if IS_LOCAL_STAGING else [],
)
CORS_ALLOWED_ORIGINS = env_csv("CORS_ALLOWED_ORIGINS", [])
TRUSTED_PROXY_CIDRS = env_csv(
    "TRUSTED_PROXY_CIDRS",
    [
        "127.0.0.1/32",
        "::1/128",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ],
)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "compass.accounts",
    "compass.audit",
    "compass.authentication",
    "compass.organization",
    "compass.service_catalog",
    "compass.availability",
    "compass.appointments",
    "compass.counseling",
]

AUTH_USER_MODEL = "accounts.User"

# Passwords are user-chosen credentials, including for the self-service initial setup and
# recovery flow. Django's built-in validators provide length and common-password screening
# without brittle composition rules. Fifteen characters follows current guidance for passwords
# that may be used as a single factor; MFA remains an additional account policy rather than a
# reason to weaken the shared baseline.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 15},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

MIDDLEWARE = [
    "compass.common.middleware.RequestContextMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    }
]

POSTGRES_DB = env("POSTGRES_DB", "compass")
POSTGRES_USER = env("POSTGRES_USER", "compass")
POSTGRES_PASSWORD = required_env("POSTGRES_PASSWORD")
POSTGRES_HOST = env("POSTGRES_HOST", "postgres")
POSTGRES_PORT = env_int("POSTGRES_PORT", 5432)
DB_CONN_MAX_AGE = env_int("DB_CONN_MAX_AGE", 60)
DB_CONNECT_TIMEOUT = env_int("DB_CONNECT_TIMEOUT", 5)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": POSTGRES_DB,
        "USER": POSTGRES_USER,
        "PASSWORD": POSTGRES_PASSWORD,
        "HOST": POSTGRES_HOST,
        "PORT": POSTGRES_PORT,
        "CONN_MAX_AGE": DB_CONN_MAX_AGE,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": DB_CONNECT_TIMEOUT},
    }
}

REDIS_URL = required_env("REDIS_URL")
REDIS_CACHE_URL = required_env("REDIS_CACHE_URL")
REDIS_RATE_LIMIT_URL = required_env("REDIS_RATE_LIMIT_URL")
REDIS_IDEMPOTENCY_URL = required_env("REDIS_IDEMPOTENCY_URL")
REDIS_SOCKET_TIMEOUT = env_float("REDIS_SOCKET_TIMEOUT", 2.0)
RATE_LIMITER_FAIL_OPEN = env_bool("RATE_LIMITER_FAIL_OPEN", False)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "KEY_PREFIX": "compass",
        "TIMEOUT": 300,
    }
}

S3_BUCKET_NAME = required_env("S3_BUCKET_NAME")
S3_ACCESS_KEY_ID = required_env("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = required_env("S3_SECRET_ACCESS_KEY")
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", "http://minio:9000" if IS_LOCAL_STAGING else None)
S3_REGION_NAME = env("S3_REGION_NAME", "us-east-1")
S3_ADDRESSING_STYLE = env("S3_ADDRESSING_STYLE", "path" if IS_LOCAL_STAGING else "virtual")
if S3_ADDRESSING_STYLE not in {"path", "virtual"}:
    raise ValueError("S3_ADDRESSING_STYLE must be path or virtual")
S3_VERIFY = env_bool("S3_VERIFY", True)
S3_COMMON_OPTIONS = {
    "bucket_name": S3_BUCKET_NAME,
    "access_key": S3_ACCESS_KEY_ID,
    "secret_key": S3_SECRET_ACCESS_KEY,
    "endpoint_url": S3_ENDPOINT_URL,
    "region_name": S3_REGION_NAME,
    "addressing_style": S3_ADDRESSING_STYLE,
    "default_acl": None,
    "querystring_auth": True,
    "file_overwrite": False,
    "signature_version": "s3v4",
    "verify": S3_VERIFY,
}
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {**S3_COMMON_OPTIONS, "location": "media"},
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {**S3_COMMON_OPTIONS, "location": "static"},
    },
}
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "media"
