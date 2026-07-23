import fnmatch
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Project(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    github_owner = models.CharField(max_length=120)
    github_repo = models.CharField(max_length=120)
    installation_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="Required in GitHub App mode. Leave blank in server token mode.",
    )
    default_branch = models.CharField(max_length=120, default="main")
    direct_push_enabled = models.BooleanField(default=True)
    allowed_branches = models.CharField(
        max_length=500,
        default="main,master,dev,develop,feature/*,ai/*",
        help_text="Comma-separated branch names or wildcard patterns.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        for field in ["github_owner", "github_repo"]:
            val = getattr(self, field, "")
            if val and val.startswith("http"):
                path = val.split("github.com/")[-1].strip("/")
                parts = path.split("/")
                if len(parts) >= 2:
                    self.github_owner = parts[0]
                    self.github_repo = parts[1].removesuffix(".git")
                    break

        if not self.slug:
            base = slugify(self.name) or "project"
            candidate = base
            index = 2
            while Project.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f"{base}-{index}"
                index += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.github_owner}/{self.github_repo}"

    def branch_is_allowed(self, branch):
        patterns = [item.strip() for item in self.allowed_branches.split(",") if item.strip()]
        return any(fnmatch.fnmatchcase(branch, pattern) for pattern in patterns)

    def __str__(self):
        return f"{self.name} ({self.full_name})"


class AgentToken(models.Model):
    name = models.CharField(max_length=120)
    token_id = models.CharField(max_length=12, unique=True, db_index=True)
    token_hash = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_agent_tokens",
    )
    projects = models.ManyToManyField(Project, blank=True, related_name="agent_tokens")
    all_projects = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    is_paused = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def issue(cls, *, name, created_by=None, all_projects=False, expires_at=None):
        token_id = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)
        raw = f"aig_{token_id}_{secret}"
        obj = cls.objects.create(
            name=name,
            token_id=token_id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            created_by=created_by,
            all_projects=all_projects,
            expires_at=expires_at,
        )
        return obj, raw

    @classmethod
    def authenticate(cls, raw):
        if not raw or not raw.startswith("aig_"):
            return None
        parts = raw.split("_", 2)
        if len(parts) != 3:
            return None
        try:
            token = cls.objects.prefetch_related("projects").get(token_id=parts[1])
        except cls.DoesNotExist:
            return None
        candidate = hashlib.sha256(raw.encode()).hexdigest()
        if not hmac.compare_digest(candidate, token.token_hash) or not token.is_active:
            return None
        token.last_used_at = timezone.now()
        token.save(update_fields=["last_used_at"])
        return token

    @property
    def is_expired(self):
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_active(self):
        if self.revoked_at or self.is_paused:
            return False
        return not self.expires_at or self.expires_at > timezone.now()

    @property
    def display_token(self):
        return f"aig_{self.token_id}_••••••••"

    def revoke(self):
        if not self.revoked_at:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    def can_access(self, project):
        return self.all_projects or self.projects.filter(pk=project.pk).exists()

    def __str__(self):
        return self.name


class PushRecord(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="pushes")
    token = models.ForeignKey(
        AgentToken,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pushes",
    )
    branch = models.CharField(max_length=120)
    commit_message = models.CharField(max_length=500)
    commit_sha = models.CharField(max_length=64, blank=True)
    commit_url = models.URLField(blank=True)
    file_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.slug}:{self.branch} {self.status}"
