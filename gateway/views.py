from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .forms import AgentTokenForm, ProjectForm
from .models import AgentToken, Project, PushRecord


def staff_required(view_func):
    """Require an authenticated staff account without creating redirect loops."""

    @login_required(login_url="account_login")
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied("Staff access is required.")
        return view_func(request, *args, **kwargs)

    return wrapped


def active_tokens_queryset():
    return AgentToken.objects.filter(revoked_at__isnull=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    )


@staff_required
def dashboard(request):
    successful_pushes = PushRecord.objects.filter(status="success").count()
    failed_pushes = PushRecord.objects.filter(status="failed").count()
    total_finished = successful_pushes + failed_pushes
    success_rate = round((successful_pushes / total_finished) * 100) if total_finished else None

    context = {
        "project_count": Project.objects.filter(is_active=True).count(),
        "direct_push_projects": Project.objects.filter(
            is_active=True,
            direct_push_enabled=True,
        ).count(),
        "active_tokens": active_tokens_queryset().count(),
        "successful_pushes": successful_pushes,
        "failed_pushes": failed_pushes,
        "success_rate": success_rate,
        "recent_pushes": PushRecord.objects.select_related("project", "token")[:8],
        "recent_projects": Project.objects.order_by("-updated_at")[:4],
        "github_auth_mode": settings.GITHUB_AUTH_MODE,
    }
    return render(request, "gateway/dashboard.html", context)


@staff_required
def project_list(request):
    return render(request, "gateway/project_list.html", {"projects": Project.objects.all()})


@staff_required
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(request, f"Project {project.name} created.")
        return redirect("project_list")
    return render(request, "gateway/project_form.html", {"form": form, "title": "Add project"})


@staff_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(request, f"Project {project.name} updated.")
        return redirect("project_list")
    return render(
        request,
        "gateway/project_form.html",
        {"form": form, "title": "Edit project", "project": project},
    )


@staff_required
@never_cache
def token_list(request):
    form = AgentTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        token, raw = form.save(request.user)
        return render(request, "gateway/token_created.html", {"token": token, "raw_token": raw})
    return render(
        request,
        "gateway/token_list.html",
        {
            "form": form,
            "tokens": AgentToken.objects.prefetch_related("projects"),
            "active_tokens": active_tokens_queryset().count(),
        },
    )


@staff_required
@require_POST
def token_revoke(request, pk):
    token = get_object_or_404(AgentToken, pk=pk)
    token.revoke()
    messages.success(request, f"Token {token.name} revoked. It can no longer push.")
    return redirect("token_list")


@staff_required
def push_history(request):
    pushes = PushRecord.objects.select_related("project", "token")[:250]
    return render(request, "gateway/history.html", {"pushes": pushes})


def instructions(request):
    api_base = request.build_absolute_uri("/api/v1/").rstrip("/")
    return render(request, "gateway/instructions.html", {"api_base": api_base})


def instructions_json(request):
    from django.http import JsonResponse

    api_base = request.build_absolute_uri("/api/v1/").rstrip("/")
    return JsonResponse(
        {
            "name": "AI Git Gateway",
            "purpose": (
                "Submit completed file changes and push a non-force Git commit "
                "directly to GitHub."
            ),
            "authentication": "Authorization: Bearer <agent-token>",
            "projects_endpoint": f"{api_base}/projects",
            "push_endpoint": f"{api_base}/push",
            "push_schema": {
                "project": "project slug",
                "branch": "target branch; optional when project default is correct",
                "commit_message": "required commit message",
                "expected_head": "optional commit SHA for conflict protection",
                "files": [
                    {"path": "relative/path.py", "content": "UTF-8 text"},
                    {"path": "binary.png", "content_base64": "base64 data"},
                    {"path": "deleted.py", "delete": True},
                ],
            },
            "rules": [
                "Finish and verify the code before pushing.",
                "Never reveal or commit the agent token.",
                "Do not retry conflicts blindly.",
                "Return the commit_url to the user.",
                "Remind the user to revoke the agent token after the job.",
            ],
        }
    )


def health(request):
    from django.http import JsonResponse

    return JsonResponse({"ok": True, "service": "ai-git-gateway"})


def readiness(request):
    from django.db import connection
    from django.http import JsonResponse

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"ok": False, "database": "unavailable"}, status=503)
    return JsonResponse({"ok": True, "database": "ready"})
