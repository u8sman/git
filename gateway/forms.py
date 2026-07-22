from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import AgentToken, Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "name",
            "github_owner",
            "github_repo",
            "installation_id",
            "default_branch",
            "direct_push_enabled",
            "allowed_branches",
            "is_active",
        ]
        widgets = {
            "allowed_branches": forms.TextInput(attrs={"placeholder": "main,dev,feature/*,ai/*"}),
        }


class AgentTokenForm(forms.Form):
    name = forms.CharField(max_length=120, help_text="For example: Claude on laptop")
    all_projects = forms.BooleanField(required=False, initial=False)
    projects = forms.ModelMultipleChoiceField(
        queryset=Project.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    expires_in_days = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=365,
        help_text="Leave blank to keep active until you revoke it.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["projects"].queryset = Project.objects.filter(is_active=True)

    def clean(self):
        data = super().clean()
        if not data.get("all_projects") and not data.get("projects"):
            self.add_error("projects", "Choose at least one project or enable all projects.")
        return data

    def save(self, user):
        days = self.cleaned_data.get("expires_in_days")
        expires_at = timezone.now() + timedelta(days=days) if days else None
        token, raw = AgentToken.issue(
            name=self.cleaned_data["name"],
            created_by=user,
            all_projects=self.cleaned_data["all_projects"],
            expires_at=expires_at,
        )
        if not token.all_projects:
            token.projects.set(self.cleaned_data["projects"])
        return token, raw
