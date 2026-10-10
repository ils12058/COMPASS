"""Environment-driven Django settings for local-staging and live-staging."""

import base64
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid

from compass.common.build_metadata import read_project_version, validate_runtime_build_identity
from compass.common.config import env, env_bool, env_csv, env_float, env_int, required_env
from compass.common.redis_config import redis_urls
from compass.confidential_data.crypto import keyring_reuses_secret, parse_fernet_keyring

BASE_DIR = Path(__file__).resolve().parent.parent

APP_ENV = env("APP_ENV", "local-staging")
if APP_ENV not in {"local-staging", "live-staging"}:
    raise ValueError("APP_ENV must be either local-staging or live-staging")

APPLICATION_VERSION = read_project_version(BASE_DIR / "pyproject.toml")
COMPASS_BUILD_ID, COMPASS_BUILD_TIME = validate_runtime_build_identity(
    app_env=APP_ENV,
    build_id=env("COMPASS_BUILD_ID", "local"),
    build_time=env("COMPASS_BUILD_TIME", ""),
)

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
    "django.contrib.postgres",
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
    "compass.guidance_messages",
    "compass.institutional_forms",
    "compass.documents",
    "compass.inventory",
    "compass.student_support",
    "compass.reports",
    "compass.good_moral",
    "compass.feedback",
    "compass.graduate_tracer",
    "compass.exit_interviews",
    "compass.routine_interviews",
    "compass.referrals",
    "compass.call_slips",
    "compass.notifications",
    "compass.announcements",
    "compass.resources",
    "compass.ecounseling",
    "compass.platform_ops",
    "compass.privacy_governance",
    "compass.demo_seed",
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
    "compass.platform_ops.middleware.MaintenanceModeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "ninja.compatibility.files.fix_request_files_middleware",
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
        # Shared transactional-email shells (compass/email/*) used by more than one app.
        "DIRS": [BASE_DIR / "compass" / "common" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.request",
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

_redis_urls = redis_urls(live_staging=not IS_LOCAL_STAGING)
REDIS_URL = _redis_urls["REDIS_URL"]
REDIS_CACHE_URL = _redis_urls["REDIS_CACHE_URL"]
REDIS_RATE_LIMIT_URL = _redis_urls["REDIS_RATE_LIMIT_URL"]
REDIS_IDEMPOTENCY_URL = _redis_urls["REDIS_IDEMPOTENCY_URL"]
REDIS_REALTIME_URL = _redis_urls["REDIS_REALTIME_URL"]
REDIS_SOCKET_TIMEOUT = env_float("REDIS_SOCKET_TIMEOUT", 2.0)
RATE_LIMITER_FAIL_OPEN = env_bool("RATE_LIMITER_FAIL_OPEN", False)

# Realtime transport (ADR-100). Off by default: when false, Django issues no realtime tickets and
# never contacts the realtime Redis database. Tickets authenticate one WebSocket each and expire
# quickly; a revoked AuthSession's marker outlives every ticket minted before the revocation.
REALTIME_ENABLED = env_bool("REALTIME_ENABLED", False)
REALTIME_TICKET_TTL_SECONDS = env_int("REALTIME_TICKET_TTL_SECONDS", 30)
REALTIME_REVOCATION_TTL_SECONDS = env_int("REALTIME_REVOCATION_TTL_SECONDS", 3600)
if not 5 <= REALTIME_TICKET_TTL_SECONDS <= 120:
    raise ValueError("REALTIME_TICKET_TTL_SECONDS must be between 5 and 120")
if not REALTIME_TICKET_TTL_SECONDS < REALTIME_REVOCATION_TTL_SECONDS <= 86_400:
    raise ValueError(
        "REALTIME_REVOCATION_TTL_SECONDS must exceed the ticket TTL and be at most 86400"
    )

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
    "ecounseling_media": {
        "BACKEND": "compass.integrations.sensitive_storage.SensitiveMediaStorage",
        "OPTIONS": {
            **S3_COMMON_OPTIONS,
            "bucket_name": env("ECOUNSELING_MEDIA_BUCKET_NAME", "") or S3_BUCKET_NAME,
            "location": "e-counseling",
        },
    },
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

SMTP_HOST = env("SMTP_HOST", "mailpit" if IS_LOCAL_STAGING else None)
if not SMTP_HOST:
    raise ValueError("SMTP_HOST is required in live-staging")
SMTP_PORT = env_int("SMTP_PORT", 1025 if IS_LOCAL_STAGING else 587)
SMTP_USERNAME = env("SMTP_USERNAME", "")
SMTP_PASSWORD = env("SMTP_PASSWORD", "")
SMTP_USE_TLS = env_bool("SMTP_USE_TLS", False)
SMTP_USE_SSL = env_bool("SMTP_USE_SSL", False)
if SMTP_USE_TLS and SMTP_USE_SSL:
    raise ValueError("SMTP_USE_TLS and SMTP_USE_SSL cannot both be true")
SMTP_TIMEOUT = env_int("EMAIL_TIMEOUT", 10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@localhost" if IS_LOCAL_STAGING else None)
if not DEFAULT_FROM_EMAIL:
    raise ValueError("DEFAULT_FROM_EMAIL is required in live-staging")
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": SMTP_HOST,
            "port": SMTP_PORT,
            "username": SMTP_USERNAME,
            "password": SMTP_PASSWORD,
            "use_tls": SMTP_USE_TLS,
            "use_ssl": SMTP_USE_SSL,
            "timeout": SMTP_TIMEOUT,
        },
    }
}

TURNSTILE_ENABLED = env_bool("TURNSTILE_ENABLED", not IS_LOCAL_STAGING)
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_URL = env(
    "TURNSTILE_VERIFY_URL",
    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
)
TURNSTILE_TIMEOUT_SECONDS = env_float("TURNSTILE_TIMEOUT_SECONDS", 5.0)
TURNSTILE_EXPECTED_HOSTNAMES = env_csv("TURNSTILE_EXPECTED_HOSTNAMES", [])
TURNSTILE_EXPECTED_ACTION = env("TURNSTILE_EXPECTED_ACTION", "")
if TURNSTILE_ENABLED and not TURNSTILE_SECRET_KEY:
    raise ValueError("TURNSTILE_SECRET_KEY is required when TURNSTILE_ENABLED is true")

# Daily is deployment-owned provider infrastructure. Disabled mode must leave the rest of
# COMPASS usable, while enabled deployments fail fast on missing credentials and invalid timing.
DAILY_ENABLED = env_bool("DAILY_ENABLED", False)
DAILY_API_KEY = env("DAILY_API_KEY", "")
DAILY_API_BASE_URL = env("DAILY_API_BASE_URL", "https://api.daily.co/v1")
DAILY_WEBHOOK_HMAC = env("DAILY_WEBHOOK_HMAC", "")
DAILY_HTTP_TIMEOUT_SECONDS = env_float("DAILY_HTTP_TIMEOUT_SECONDS", 5.0)
DAILY_MEETING_TOKEN_TTL_SECONDS = env_int("DAILY_MEETING_TOKEN_TTL_SECONDS", 300)
DAILY_WEBHOOK_MAX_AGE_SECONDS = env_int("DAILY_WEBHOOK_MAX_AGE_SECONDS", 300)
ECOUNSELING_JOIN_EARLY_SECONDS = env_int("ECOUNSELING_JOIN_EARLY_SECONDS", 600)
ECOUNSELING_REJOIN_GRACE_SECONDS = env_int("ECOUNSELING_REJOIN_GRACE_SECONDS", 900)
ECOUNSELING_MEDIA_ACCESS_URL_TTL_SECONDS = env_int("ECOUNSELING_MEDIA_ACCESS_URL_TTL_SECONDS", 300)
ECOUNSELING_MEDIA_MAX_BYTES = env_int("ECOUNSELING_MEDIA_MAX_BYTES", 10 * 1024**3)
if not 60 <= ECOUNSELING_MEDIA_ACCESS_URL_TTL_SECONDS <= 600:
    raise ValueError("ECOUNSELING_MEDIA_ACCESS_URL_TTL_SECONDS must be between 60 and 600")
if not 1024**2 <= ECOUNSELING_MEDIA_MAX_BYTES <= 100 * 1024**3:
    raise ValueError("ECOUNSELING_MEDIA_MAX_BYTES must be between 1 MiB and 100 GiB")
if DAILY_HTTP_TIMEOUT_SECONDS <= 0:
    raise ValueError("DAILY_HTTP_TIMEOUT_SECONDS must be positive")
if not 60 <= DAILY_MEETING_TOKEN_TTL_SECONDS <= 900:
    raise ValueError("DAILY_MEETING_TOKEN_TTL_SECONDS must be between 60 and 900")
if not 30 <= DAILY_WEBHOOK_MAX_AGE_SECONDS <= 900:
    raise ValueError("DAILY_WEBHOOK_MAX_AGE_SECONDS must be between 30 and 900")
if not 0 <= ECOUNSELING_JOIN_EARLY_SECONDS <= 3600:
    raise ValueError("ECOUNSELING_JOIN_EARLY_SECONDS must be between 0 and 3600")
if not 0 <= ECOUNSELING_REJOIN_GRACE_SECONDS <= 3600:
    raise ValueError("ECOUNSELING_REJOIN_GRACE_SECONDS must be between 0 and 3600")
if DAILY_ENABLED and not DAILY_API_KEY:
    raise ValueError("DAILY_API_KEY is required when DAILY_ENABLED is true")
if DAILY_ENABLED and not DAILY_WEBHOOK_HMAC:
    raise ValueError("DAILY_WEBHOOK_HMAC is required when DAILY_ENABLED is true")

# Official PSA Philippine Standard Geographic Code reference integration. Missing token/version
# must not prevent COMPASS startup; PSGC-dependent operations fail through controlled 503 errors.
PSGC_API_BASE_URL = env("PSGC_API_BASE_URL", "https://classification.psa.gov.ph/psgc")
PSGC_API_TOKEN = env("PSGC_API_TOKEN", "")
PSGC_VERSION = env("PSGC_VERSION", "")
PSGC_HTTP_TIMEOUT_SECONDS = env_float("PSGC_HTTP_TIMEOUT_SECONDS", 5.0)
PSGC_CACHE_TTL_SECONDS = env_int("PSGC_CACHE_TTL_SECONDS", 86_400)
if PSGC_HTTP_TIMEOUT_SECONDS <= 0:
    raise ValueError("PSGC_HTTP_TIMEOUT_SECONDS must be positive")
if PSGC_CACHE_TTL_SECONDS <= 0:
    raise ValueError("PSGC_CACHE_TTL_SECONDS must be positive")

# Authentication uses a separate server-managed opaque session rather than Django's signed
# session cookie. The credential-bearing cookies are scoped to the API and are never readable by
# browser JavaScript. A deployment may choose SameSite=None for a separately hosted SPA, but it
# must then also use Secure cookies.
AUTH_SESSION_COOKIE_NAME = env("AUTH_SESSION_COOKIE_NAME", "compass_session")
AUTH_SESSION_COOKIE_PATH = env("AUTH_SESSION_COOKIE_PATH", "/api/")
AUTH_SESSION_COOKIE_DOMAIN = env("AUTH_SESSION_COOKIE_DOMAIN", None)
AUTH_TRUSTED_COOKIE_NAME = env("AUTH_TRUSTED_COOKIE_NAME", "compass_trusted")
AUTH_TRUSTED_COOKIE_PATH = env("AUTH_TRUSTED_COOKIE_PATH", "/api/v1/auth")
AUTH_LOGIN_CHALLENGE_COOKIE_NAME = env(
    "AUTH_LOGIN_CHALLENGE_COOKIE_NAME", "compass_login_challenge"
)
AUTH_LOGIN_CHALLENGE_COOKIE_PATH = env("AUTH_LOGIN_CHALLENGE_COOKIE_PATH", "/api/v1/auth/mfa")
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", "Lax")
if AUTH_COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
    raise ValueError("AUTH_COOKIE_SAMESITE must be Lax, Strict, or None")
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", not IS_LOCAL_STAGING)
if not IS_LOCAL_STAGING and not AUTH_COOKIE_SECURE:
    raise ValueError("AUTH_COOKIE_SECURE must be true in live-staging")
if AUTH_COOKIE_SAMESITE == "None" and not AUTH_COOKIE_SECURE:
    raise ValueError("AUTH_COOKIE_SECURE must be true when AUTH_COOKIE_SAMESITE is None")

AUTH_SESSION_AGE_SECONDS = env_int("AUTH_SESSION_AGE_SECONDS", 14 * 24 * 60 * 60)
AUTH_TRUSTED_SESSION_AGE_SECONDS = env_int("AUTH_TRUSTED_SESSION_AGE_SECONDS", 30 * 24 * 60 * 60)
AUTH_LOGIN_CHALLENGE_AGE_SECONDS = env_int("AUTH_LOGIN_CHALLENGE_AGE_SECONDS", 5 * 60)
AUTH_SESSION_LAST_USED_WRITE_INTERVAL_SECONDS = env_int(
    "AUTH_SESSION_LAST_USED_WRITE_INTERVAL_SECONDS", 5 * 60
)
AUTH_RECENT_MFA_WINDOW_SECONDS = env_int("AUTH_RECENT_MFA_WINDOW_SECONDS", 10 * 60)
AUTH_MAX_SESSION_LIST_SIZE = env_int("AUTH_MAX_SESSION_LIST_SIZE", 100)

# MFA policy is deliberately separate from capabilities. An enrolled TOTP factor is an explicit
# user opt-in and requires MFA at login; role-specific mandatory MFA can be enabled later through
# this configuration without changing the authentication/session model.
AUTH_MFA_REQUIRED_ROLE_CODES = env_csv("AUTH_MFA_REQUIRED_ROLE_CODES", [])
AUTH_TOTP_ISSUER_NAME = env("AUTH_TOTP_ISSUER_NAME", "COMPASS")
AUTH_TOTP_INTERVAL_SECONDS = env_int("AUTH_TOTP_INTERVAL_SECONDS", 30)
AUTH_TOTP_VALID_WINDOW = env_int("AUTH_TOTP_VALID_WINDOW", 1)
AUTH_TOTP_DIGITS = env_int("AUTH_TOTP_DIGITS", 6)
if AUTH_TOTP_INTERVAL_SECONDS < 1 or AUTH_TOTP_VALID_WINDOW < 0 or AUTH_TOTP_DIGITS != 6:
    raise ValueError("TOTP interval/window must be valid and AUTH_TOTP_DIGITS must be 6")
AUTH_TOTP_ENCRYPTION_KEY = env("AUTH_TOTP_ENCRYPTION_KEY", "")
if not IS_LOCAL_STAGING and not AUTH_TOTP_ENCRYPTION_KEY:
    raise ValueError("AUTH_TOTP_ENCRYPTION_KEY is required in live-staging")

# Routine Interview content has its own ordered Fernet keyring (ADR-066): the first key encrypts,
# every listed key decrypts. PostgreSQL holds only ciphertext for that content, so the keyring is
# required in every environment and there is no fallback key.
ROUTINE_INTERVIEW_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("ROUTINE_INTERVIEW_ENCRYPTION_KEYS"),
    setting="ROUTINE_INTERVIEW_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(ROUTINE_INTERVIEW_ENCRYPTION_KEYS, SECRET_KEY, AUTH_TOTP_ENCRYPTION_KEY):
    raise ValueError(
        "ROUTINE_INTERVIEW_ENCRYPTION_KEYS must not reuse SECRET_KEY or AUTH_TOTP_ENCRYPTION_KEY"
    )

AUTH_EMAIL_OTP_TTL_SECONDS = env_int("AUTH_EMAIL_OTP_TTL_SECONDS", 10 * 60)
AUTH_EMAIL_OTP_MAX_ATTEMPTS = env_int("AUTH_EMAIL_OTP_MAX_ATTEMPTS", 5)
AUTH_EMAIL_OTP_RESEND_INTERVAL_SECONDS = env_int("AUTH_EMAIL_OTP_RESEND_INTERVAL_SECONDS", 60)
AUTH_EMAIL_OTP_MAX_SENDS = env_int("AUTH_EMAIL_OTP_MAX_SENDS", 5)
AUTH_EMAIL_OTP_CODE_LENGTH = env_int("AUTH_EMAIL_OTP_CODE_LENGTH", 6)
if (
    AUTH_EMAIL_OTP_TTL_SECONDS < 1
    or AUTH_EMAIL_OTP_MAX_ATTEMPTS < 1
    or AUTH_EMAIL_OTP_RESEND_INTERVAL_SECONDS < 1
    or AUTH_EMAIL_OTP_MAX_SENDS < 1
    or AUTH_EMAIL_OTP_CODE_LENGTH != 6
):
    raise ValueError("email OTP settings must be positive and use six-digit codes")

# Turnstile is enabled by default for anonymous high-abuse flows in live-staging. Local tests and
# local-staging remain usable with the explicit local default, while live deployments can opt out
# only by setting a documented security policy deliberately.
AUTH_TURNSTILE_LOGIN_REQUIRED = env_bool("AUTH_TURNSTILE_LOGIN_REQUIRED", not IS_LOCAL_STAGING)
AUTH_TURNSTILE_EMAIL_OTP_REQUIRED = env_bool(
    "AUTH_TURNSTILE_EMAIL_OTP_REQUIRED", not IS_LOCAL_STAGING
)

IDEMPOTENCY_TTL_SECONDS = env_int("IDEMPOTENCY_TTL_SECONDS", 86_400)
IDEMPOTENCY_MAX_RESPONSE_BYTES = env_int("IDEMPOTENCY_MAX_RESPONSE_BYTES", 1_048_576)

COUNSELING_CONTEXT_PRE_APPOINTMENT_HOURS = env_int("COUNSELING_CONTEXT_PRE_APPOINTMENT_HOURS", 24)
COUNSELING_CONTEXT_UNCOMPLETED_GRACE_HOURS = env_int(
    "COUNSELING_CONTEXT_UNCOMPLETED_GRACE_HOURS", 24
)
COUNSELING_CONTEXT_POST_ENCOUNTER_DAYS = env_int("COUNSELING_CONTEXT_POST_ENCOUNTER_DAYS", 7)
if not 0 <= COUNSELING_CONTEXT_PRE_APPOINTMENT_HOURS <= 168:
    raise ValueError("COUNSELING_CONTEXT_PRE_APPOINTMENT_HOURS must be between 0 and 168")
if not 0 <= COUNSELING_CONTEXT_UNCOMPLETED_GRACE_HOURS <= 168:
    raise ValueError("COUNSELING_CONTEXT_UNCOMPLETED_GRACE_HOURS must be between 0 and 168")
if not 0 <= COUNSELING_CONTEXT_POST_ENCOUNTER_DAYS <= 30:
    raise ValueError("COUNSELING_CONTEXT_POST_ENCOUNTER_DAYS must be between 0 and 30")

NOTIFICATION_EMAIL_MAX_ATTEMPTS = env_int("NOTIFICATION_EMAIL_MAX_ATTEMPTS", 5)
NOTIFICATION_EMAIL_RETRY_BASE_SECONDS = env_int("NOTIFICATION_EMAIL_RETRY_BASE_SECONDS", 60)
NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS = env_int(
    "NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS", 60
)
NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS = env_int("NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS", 300)
WEB_PUSH_ENABLED = env_bool("WEB_PUSH_ENABLED", False)
WEB_PUSH_PUBLIC_KEY = env("WEB_PUSH_PUBLIC_KEY", "")
WEB_PUSH_PRIVATE_KEY = env("WEB_PUSH_PRIVATE_KEY", "")
WEB_PUSH_CONTACT = env("WEB_PUSH_CONTACT", "")
WEB_PUSH_STORAGE_KEY = env("WEB_PUSH_STORAGE_KEY", "")
if WEB_PUSH_ENABLED and not all(
    (WEB_PUSH_PUBLIC_KEY, WEB_PUSH_PRIVATE_KEY, WEB_PUSH_CONTACT, WEB_PUSH_STORAGE_KEY)
):
    raise ValueError("Web Push requires public/private VAPID keys, contact, and storage key")
if WEB_PUSH_ENABLED and not WEB_PUSH_CONTACT.startswith("mailto:"):
    raise ValueError("WEB_PUSH_CONTACT must be a mailto: address")
if WEB_PUSH_ENABLED:
    try:
        Fernet(WEB_PUSH_STORAGE_KEY.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise ValueError("WEB_PUSH_STORAGE_KEY must be a valid Fernet key") from exc
    try:
        public = base64.urlsafe_b64decode(
            WEB_PUSH_PUBLIC_KEY + "=" * (-len(WEB_PUSH_PUBLIC_KEY) % 4)
        )
        private = Vapid.from_string(private_key=WEB_PUSH_PRIVATE_KEY)
        expected_public = private.public_key.public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )
        if len(public) != 65 or public != expected_public:
            raise ValueError("VAPID key mismatch")
    except Exception as exc:
        raise ValueError("WEB_PUSH_PUBLIC_KEY and WEB_PUSH_PRIVATE_KEY must match") from exc
# Shared Summary bodies have a separate required ordered keyring (ADR-080), even locally.
COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS"),
    setting="COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(
    COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
):
    raise ValueError(
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS must not reuse SECRET_KEY, "
        "AUTH_TOTP_ENCRYPTION_KEY, WEB_PUSH_STORAGE_KEY or ROUTINE_INTERVIEW_ENCRYPTION_KEYS"
    )

# Referral source content and per-action remarks share one independent domain keyring (ADR-081).
REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"),
    setting="REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(
    REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
    *COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
):
    raise ValueError(
        "REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS must not reuse SECRET_KEY, "
        "AUTH_TOTP_ENCRYPTION_KEY, WEB_PUSH_STORAGE_KEY, ROUTINE_INTERVIEW_ENCRYPTION_KEYS "
        "or COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS"
    )

# Exit Interview contact/narrative content and operational notes/reasons (ADR-082).
EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"),
    setting="EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(
    EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
    *COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
    *REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
):
    raise ValueError(
        "EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS must not reuse SECRET_KEY, "
        "AUTH_TOTP_ENCRYPTION_KEY, WEB_PUSH_STORAGE_KEY, ROUTINE_INTERVIEW_ENCRYPTION_KEYS, "
        "COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS or REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"
    )

# Selective Individual Inventory E2 content shares one independent keyring (ADR-083).
INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"),
    setting="INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(
    INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
    *COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
    *REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
):
    raise ValueError(
        "INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS must not reuse "
        "another encryption domain or SECRET_KEY"
    )

# Selective Graduate Tracer E2 content shares one independent keyring (ADR-084).
GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"),
    setting="GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(
    GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
    *COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
    *REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
):
    raise ValueError(
        "GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS must not reuse "
        "another encryption domain or SECRET_KEY"
    )


ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"),
    setting="ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(
    ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
    *COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
    *REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
):
    raise ValueError(
        "ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS must not reuse "
        "another encryption domain or SECRET_KEY"
    )

FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS = parse_fernet_keyring(
    required_env("FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS"),
    setting="FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS",
)
if keyring_reuses_secret(
    FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
    *COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
    *REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
):
    raise ValueError(
        "FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS must not reuse "
        "another encryption domain or SECRET_KEY"
    )

# Worker/beat intentionally remain keyless; confidential read/write fails closed (ADR-102).
# Live host preflight requires a provisioned Messages key for web deployment (ADR-105).
_guidance_keys = env("GUIDANCE_MESSAGE_ENCRYPTION_KEYS", "")
GUIDANCE_MESSAGE_ENCRYPTION_KEYS = (
    parse_fernet_keyring(_guidance_keys, setting="GUIDANCE_MESSAGE_ENCRYPTION_KEYS")
    if _guidance_keys
    else ()
)
if keyring_reuses_secret(
    GUIDANCE_MESSAGE_ENCRYPTION_KEYS,
    SECRET_KEY,
    AUTH_TOTP_ENCRYPTION_KEY,
    WEB_PUSH_STORAGE_KEY,
    *ROUTINE_INTERVIEW_ENCRYPTION_KEYS,
    *COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS,
    *REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *GRADUATE_TRACER_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
    *FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS,
):
    raise ValueError(
        "GUIDANCE_MESSAGE_ENCRYPTION_KEYS must not reuse another encryption domain or SECRET_KEY"
    )

if not 1 <= NOTIFICATION_EMAIL_MAX_ATTEMPTS <= 20:
    raise ValueError("NOTIFICATION_EMAIL_MAX_ATTEMPTS must be between 1 and 20")
if not 1 <= NOTIFICATION_EMAIL_RETRY_BASE_SECONDS <= 3_600:
    raise ValueError("NOTIFICATION_EMAIL_RETRY_BASE_SECONDS must be between 1 and 3600")
if not 15 <= NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS <= 3_600:
    raise ValueError("NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS must be between 15 and 3600")
if not 30 <= NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS <= 3_600:
    raise ValueError("NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS must be between 30 and 3600")
if NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS <= SMTP_TIMEOUT:
    raise ValueError("NOTIFICATION_EMAIL_CLAIM_TTL_SECONDS must exceed EMAIL_TIMEOUT")

DOCUMENT_RENDER_TIMEOUT_SECONDS = env_int("DOCUMENT_RENDER_TIMEOUT_SECONDS", 30)
if not 1 <= DOCUMENT_RENDER_TIMEOUT_SECONDS <= 120:
    raise ValueError("DOCUMENT_RENDER_TIMEOUT_SECONDS must be between 1 and 120")

# Operator opt-in for the synthetic ``seed_demo_staging`` dataset. The command also enforces its
# own explicit staging allowlist, so this flag can never enable seeding anywhere else.
DEMO_SEEDING_ENABLED = env_bool("DEMO_SEEDING_ENABLED", IS_LOCAL_STAGING)

API_DOCS_ENABLED = env_bool("API_DOCS_ENABLED", IS_LOCAL_STAGING)
if not IS_LOCAL_STAGING and API_DOCS_ENABLED:
    raise ValueError("API_DOCS_ENABLED must be false in live-staging")
CADDY_MAX_REQUEST_BODY_SIZE = env("CADDY_MAX_REQUEST_BODY_SIZE", "10MB")

PROFILE_PHOTO_MAX_UPLOAD_BYTES = env_int("PROFILE_PHOTO_MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
PROFILE_PHOTO_MAX_OUTPUT_BYTES = env_int("PROFILE_PHOTO_MAX_OUTPUT_BYTES", 2 * 1024 * 1024)
PROFILE_PHOTO_MAX_DIMENSION = env_int("PROFILE_PHOTO_MAX_DIMENSION", 1024)
PROFILE_PHOTO_MAX_PIXELS = env_int("PROFILE_PHOTO_MAX_PIXELS", 25_000_000)
PROFILE_PHOTO_WEBP_QUALITY = env_int("PROFILE_PHOTO_WEBP_QUALITY", 85)
RESOURCE_DOWNLOAD_URL_TTL_SECONDS = env_int("RESOURCE_DOWNLOAD_URL_TTL_SECONDS", 300)
if not 60 <= RESOURCE_DOWNLOAD_URL_TTL_SECONDS <= 900:
    raise ValueError("RESOURCE_DOWNLOAD_URL_TTL_SECONDS must be between 60 and 900")

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "UTC")
INSTITUTION_TIME_ZONE = env("INSTITUTION_TIME_ZONE", "Asia/Manila")
try:
    ZoneInfo(INSTITUTION_TIME_ZONE)
except ZoneInfoNotFoundError as exc:
    raise ValueError("INSTITUTION_TIME_ZONE must be a valid IANA timezone") from exc
USE_I18N = True
USE_TZ = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not IS_LOCAL_STAGING
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not IS_LOCAL_STAGING
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_NAME = env("CSRF_COOKIE_NAME", "compass_csrf")
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = not IS_LOCAL_STAGING
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_PATH = "/"
CSRF_USE_SESSIONS = False
SECURE_HSTS_SECONDS = 0 if IS_LOCAL_STAGING else 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not IS_LOCAL_STAGING
SECURE_HSTS_PRELOAD = not IS_LOCAL_STAGING

CELERY_BROKER_URL = _redis_urls["CELERY_BROKER_URL"]
CELERY_RESULT_BACKEND = _redis_urls["CELERY_RESULT_BACKEND"]
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SEND_SENT_EVENT = False
CELERY_WORKER_SEND_TASK_EVENTS = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_IMPORTS = ("compass.tasks",)
CELERY_BEAT_SCHEDULE = {
    "ecounseling-artifact-recovery": {
        "task": "compass.ecounseling.recover_media_artifacts",
        "schedule": 60,
    },
    "retention-eligibility-discovery": {
        "task": "compass.privacy_governance.discover_retention",
        "schedule": 300,
    },
    "retention-approved-dispatch-recovery": {
        "task": "compass.privacy_governance.recover_disposition",
        "schedule": 60,
    },
    "notification-push-recovery": {
        "task": "compass.notifications.push.dispatch_due",
        "schedule": 60,
    },
    "notification-email-recovery": {
        "task": "compass.notifications.email.dispatch_due",
        "schedule": NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS,
    },
    "email-change-security-alert-recovery": {
        "task": "compass.authentication.email_change.recover_unsent_alerts",
        "schedule": NOTIFICATION_EMAIL_DISPATCH_INTERVAL_SECONDS,
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "compass.common.json_logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "loggers": {
        "compass": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
