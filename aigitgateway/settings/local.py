import os

from .base import *  # noqa: F403

DEBUG = env_bool("DEBUG", True)  # noqa: F405
SECRET_KEY = os.getenv("SECRET_KEY", "local-only-ai-git-gateway-key")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")  # noqa: F405
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
WHITENOISE_KEEP_ONLY_HASHED_FILES = False
