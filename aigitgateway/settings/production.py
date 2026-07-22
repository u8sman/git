import os
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if len(SECRET_KEY) < 32 or SECRET_KEY in {
    "unsafe-development-key",
    "local-only-change-this-key",
    "local-compose-only-key",
}:
    raise ImproperlyConfigured("Set a random SECRET_KEY of at least 32 characters in production.")

database_url = os.getenv("DATABASE_URL", "").strip()
if not database_url:
    raise ImproperlyConfigured("DATABASE_URL must be set in production.")
DATABASES = {
    "default": dj_database_url.parse(
        database_url,
        conn_max_age=int(os.getenv("DATABASE_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

APP_URL = (
    os.getenv("APP_URL", "").strip()
    or os.getenv("SERVICE_URL_WEB_8000", "").strip()
).rstrip("/")
parsed_app_url = urlparse(APP_URL) if APP_URL else None
app_hostname = parsed_app_url.hostname if parsed_app_url else None
app_origin = (
    f"{parsed_app_url.scheme}://{parsed_app_url.netloc}"
    if parsed_app_url and parsed_app_url.scheme
    else None
)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")  # noqa: F405
if app_hostname and app_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(app_hostname)
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set APP_URL or ALLOWED_HOSTS in production.")

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")  # noqa: F405
if app_origin and app_origin not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(app_origin)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SESSION_COOKIE_SECURE = bool(parsed_app_url and parsed_app_url.scheme == "https")
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)  # noqa: F405
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

ALLAUTH_TRUSTED_PROXY_COUNT = int(os.getenv("ALLAUTH_TRUSTED_PROXY_COUNT", "1"))
