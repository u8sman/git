"""Create the first staff account from environment variables when requested."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aigitgateway.settings.production")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402


def main():
    enabled = os.getenv("CREATE_SUPERUSER", "0").lower() in {"1", "true", "yes", "on"}
    username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin").strip()
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
    if not enabled or not password:
        return

    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_staff": True, "is_superuser": True, "is_active": True},
    )
    changed = created
    if not user.is_staff or not user.is_superuser or not user.is_active:
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        changed = True
    if email and user.email != email:
        user.email = email
        changed = True
    if created or os.getenv("RESET_SUPERUSER_PASSWORD", "0").lower() in {"1", "true", "yes", "on"}:
        user.set_password(password)
        changed = True
    if changed:
        user.save()
    print(f"Admin account {'created' if created else 'ready'}: {username}")


if __name__ == "__main__":
    main()
