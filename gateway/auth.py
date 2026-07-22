from dataclasses import dataclass

from django.http import JsonResponse

from .models import AgentToken


@dataclass
class AuthResult:
    token: AgentToken | None
    error: JsonResponse | None


def authenticate_request(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return AuthResult(
            None,
            JsonResponse({"error": "Use Authorization: Bearer <token>."}, status=401),
        )
    token = AgentToken.authenticate(header.removeprefix("Bearer ").strip())
    if token is None:
        return AuthResult(
            None,
            JsonResponse(
                {"error": "Invalid, expired, or revoked agent token."},
                status=401,
            ),
        )
    return AuthResult(token, None)
