from django.core.exceptions import ValidationError

from allauth.account.adapter import DefaultAccountAdapter


class PrivateGatewayAccountAdapter(DefaultAccountAdapter):
    """Keep the control panel private and limited to staff users."""

    def is_open_for_signup(self, request):
        return False

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(
                "This account does not have gateway administration access.",
                code="staff_only",
            )
