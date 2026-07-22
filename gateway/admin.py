from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import AgentToken, Project, PushRecord

admin.site.site_header = "AI Git Gateway"
admin.site.site_title = "Gateway admin"
admin.site.index_title = "Repository access and delivery"

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    compressed_fields = True
    warn_unsaved_form = True


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    compressed_fields = True


@admin.register(Project)
class ProjectAdmin(ModelAdmin):
    list_display = (
        "name",
        "repository",
        "default_branch",
        "direct_push_status",
        "is_active",
        "updated_at",
    )
    list_filter = ("direct_push_enabled", "is_active")
    search_fields = ("name", "slug", "github_owner", "github_repo")
    readonly_fields = ("slug", "created_at", "updated_at")
    list_per_page = 30
    compressed_fields = True
    warn_unsaved_form = True
    fieldsets = (
        ("Repository", {"fields": ("name", "slug", "github_owner", "github_repo")}),
        ("GitHub access", {"fields": ("installation_id",)}),
        (
            "Delivery policy",
            {
                "fields": (
                    "default_branch",
                    "direct_push_enabled",
                    "allowed_branches",
                    "is_active",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Repository")
    def repository(self, obj):
        return obj.full_name

    @admin.display(description="Direct push", boolean=True)
    def direct_push_status(self, obj):
        return obj.direct_push_enabled


@admin.register(AgentToken)
class AgentTokenAdmin(ModelAdmin):
    list_display = (
        "name",
        "display_token",
        "scope",
        "status_badge",
        "created_at",
        "last_used_at",
        "expires_at",
    )
    list_filter = ("all_projects", "revoked_at", "expires_at")
    search_fields = ("name", "token_id", "created_by__username", "created_by__email")
    list_per_page = 30
    compressed_fields = True
    actions = ("revoke_selected_tokens",)

    @admin.display(description="Scope")
    def scope(self, obj):
        if obj.all_projects:
            return "All projects"
        return ", ".join(obj.projects.values_list("name", flat=True)) or "No projects"

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.revoked_at:
            return format_html('<span style="color:#b91c1c;font-weight:600">Revoked</span>')
        if obj.expires_at and obj.expires_at <= timezone.now():
            return format_html('<span style="color:#6b7280;font-weight:600">Expired</span>')
        return format_html('<span style="color:#047857;font-weight:600">Active</span>')

    def has_add_permission(self, request):
        # Tokens must be created through the dashboard so the secret can be shown exactly once.
        return False

    def has_delete_permission(self, request, obj=None):
        # Keep revoked tokens as part of the access audit trail.
        return False

    @admin.action(description="Revoke selected active tokens", permissions=["revoke"])
    def revoke_selected_tokens(self, request, queryset):
        revoked = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f"Revoked {revoked} active token(s).")

    def has_revoke_permission(self, request):
        return request.user.has_perm("gateway.change_agenttoken")


@admin.register(PushRecord)
class PushRecordAdmin(ModelAdmin):
    list_display = (
        "project",
        "branch",
        "status_badge",
        "file_count",
        "short_sha",
        "token",
        "created_at",
    )
    list_filter = ("status", "project", "created_at")
    search_fields = ("commit_message", "commit_sha", "branch", "token__name")
    readonly_fields = [field.name for field in PushRecord._meta.fields]
    list_per_page = 40
    compressed_fields = True

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {"success": "#047857", "failed": "#b91c1c", "pending": "#a16207"}
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>',
            colours.get(obj.status, "#4b5563"),
            obj.get_status_display(),
        )

    @admin.display(description="Commit")
    def short_sha(self, obj):
        if not obj.commit_sha:
            return "—"
        if obj.commit_url:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">{}</a>',
                obj.commit_url,
                obj.commit_sha[:8],
            )
        return obj.commit_sha[:8]
