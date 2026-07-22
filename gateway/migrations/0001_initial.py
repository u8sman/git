# Generated manually for AI Git Gateway
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(blank=True, max_length=140, unique=True)),
                ("github_owner", models.CharField(max_length=120)),
                ("github_repo", models.CharField(max_length=120)),
                ("installation_id", models.PositiveBigIntegerField(blank=True, help_text="Required in GitHub App mode. Leave blank in server token mode.", null=True)),
                ("default_branch", models.CharField(default="main", max_length=120)),
                ("direct_push_enabled", models.BooleanField(default=True)),
                ("allowed_branches", models.CharField(default="main,master,dev,develop,feature/*,ai/*", help_text="Comma-separated branch names or wildcard patterns.", max_length=500)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="AgentToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("token_id", models.CharField(db_index=True, max_length=12, unique=True)),
                ("token_hash", models.CharField(max_length=64)),
                ("all_projects", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_agent_tokens", to=settings.AUTH_USER_MODEL)),
                ("projects", models.ManyToManyField(blank=True, related_name="agent_tokens", to="gateway.project")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PushRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("branch", models.CharField(max_length=120)),
                ("commit_message", models.CharField(max_length=500)),
                ("commit_sha", models.CharField(blank=True, max_length=64)),
                ("commit_url", models.URLField(blank=True)),
                ("file_count", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")], default="pending", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("request_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pushes", to="gateway.project")),
                ("token", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pushes", to="gateway.agenttoken")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
