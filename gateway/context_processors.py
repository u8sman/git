from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import AgentToken


def _github_is_configured():
    if settings.GITHUB_AUTH_MODE == "token":
        return bool(settings.GITHUB_TOKEN)
    if settings.GITHUB_AUTH_MODE == "app":
        return bool(
            settings.GITHUB_APP_ID
            and (
                settings.GITHUB_APP_PRIVATE_KEY
                or settings.GITHUB_APP_PRIVATE_KEY_PATH
            )
        )
    return False


def gateway_context(request):
    active_count = 0
    if getattr(request, "user", None) and request.user.is_authenticated:
        active_count = (
            AgentToken.objects.filter(revoked_at__isnull=True)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .count()
        )

    return {
        "active_agent_token_count": active_count,
        "gateway_auth_mode": settings.GITHUB_AUTH_MODE,
        "gateway_auth_label": (
            "GitHub App" if settings.GITHUB_AUTH_MODE == "app" else "Server token"
        ),
        "gateway_configured": _github_is_configured(),
        "gateway_name": "AI Git Gateway",
    }
