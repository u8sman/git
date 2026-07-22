"""Shared settings for AI Git Gateway.

The layout follows Cookiecutter-Django's split-settings approach while keeping
this small application intentionally compact.
"""

import base64
import binascii
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.getenv(name, default).split(",") if value.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-key")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "gateway",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "aigitgateway.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "gateway.context_processors.gateway_context",
            ],
        },
    }
]
WSGI_APPLICATION = "aigitgateway.wsgi.application"
ASGI_APPLICATION = "aigitgateway.asgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.getenv("DATABASE_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = os.getenv("TIME_ZONE", "Europe/London")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0
WHITENOISE_KEEP_ONLY_HASHED_FILES = not DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "account_login"

# django-allauth is the only browser login flow, including Django admin.
ACCOUNT_ADAPTER = "gateway.adapters.PrivateGatewayAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_CHANGE_EMAIL = False
ACCOUNT_REAUTHENTICATION_REQUIRED = True
ACCOUNT_EMAIL_NOTIFICATIONS = False
ACCOUNT_RATE_LIMITS = {
    "login": "15/5m/ip",
    "login_failed": "5/5m/ip,5/15m/key",
}
ALLAUTH_TRUSTED_PROXY_COUNT = int(os.getenv("ALLAUTH_TRUSTED_PROXY_COUNT", "0"))

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "AI Git Gateway <noreply@localhost>")

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_NAME = "aigit_sessionid"
CSRF_COOKIE_NAME = "aigit_csrftoken"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"

GITHUB_AUTH_MODE = os.getenv("GITHUB_AUTH_MODE", "app").strip().lower()
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
GITHUB_APP_PRIVATE_KEY_BASE64 = os.getenv("GITHUB_APP_PRIVATE_KEY_BASE64", "").strip()
if not GITHUB_APP_PRIVATE_KEY and GITHUB_APP_PRIVATE_KEY_BASE64:
    try:
        GITHUB_APP_PRIVATE_KEY = base64.b64decode(
            GITHUB_APP_PRIVATE_KEY_BASE64,
            validate=True,
        ).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ImproperlyConfigured(
            "GITHUB_APP_PRIVATE_KEY_BASE64 must be valid Base64-encoded UTF-8 PEM data."
        ) from exc
GITHUB_APP_PRIVATE_KEY_PATH = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
MAX_PUSH_FILES = int(os.getenv("MAX_PUSH_FILES", "100"))
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(2 * 1024 * 1024)))
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", str(16 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_REQUEST_BYTES

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

UNFOLD = {
    "SITE_TITLE": "AI Git Gateway Admin",
    "SITE_HEADER": "AI Git Gateway",
    "SITE_SUBHEADER": "Repository control plane",
    "SITE_URL": "/",
    "SITE_SYMBOL": "terminal",
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "any",
            "type": "image/svg+xml",
            "href": lambda request: static("gateway/favicon.svg"),
        }
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SHOW_BACK_BUTTON": True,
    "BORDER_RADIUS": "10px",
    "COLORS": {
        "primary": {
            "50": "oklch(97.8% .014 292)",
            "100": "oklch(94.5% .031 292)",
            "200": "oklch(89.8% .061 291)",
            "300": "oklch(82.2% .114 289)",
            "400": "oklch(71.2% .185 286)",
            "500": "oklch(61.5% .235 283)",
            "600": "oklch(54.5% .245 281)",
            "700": "oklch(48.2% .218 280)",
            "800": "oklch(42.2% .174 280)",
            "900": "oklch(37.2% .137 281)",
            "950": "oklch(27.5% .105 279)",
        }
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Gateway"),
                "separator": True,
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("dashboard"),
                    },
                    {
                        "title": _("Projects"),
                        "icon": "account_tree",
                        "link": reverse_lazy("admin:gateway_project_changelist"),
                    },
                    {
                        "title": _("Agent tokens"),
                        "icon": "key",
                        "link": reverse_lazy("admin:gateway_agenttoken_changelist"),
                    },
                    {
                        "title": _("Push records"),
                        "icon": "commit",
                        "link": reverse_lazy("admin:gateway_pushrecord_changelist"),
                    },
                    {
                        "title": _("AI instructions"),
                        "icon": "smart_toy",
                        "link": reverse_lazy("instructions"),
                    },
                ],
            },
            {
                "title": _("Access"),
                "separator": True,
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_user_changelist"),
                    },
                    {
                        "title": _("Groups"),
                        "icon": "shield_person",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
        ],
    },
}
