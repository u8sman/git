import base64
import binascii
import json
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .auth import authenticate_request
from .github import GitHubAPIError, GitHubClient
from .models import Project, PushRecord


def _json_body(request):
    try:
        body = json.loads(request.body or b"{}")
    except RequestDataTooBig as exc:
        raise ValueError("Request body exceeds the configured size limit.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    return body


def _validate_path(path):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Every file needs a non-empty path.")
    if "\\" in path or "\x00" in path or path.startswith("/"):
        raise ValueError(f"Invalid repository path: {path}")
    parsed = PurePosixPath(path)
    if not parsed.parts or ".." in parsed.parts or parsed.parts[0] == ".git":
        raise ValueError(f"Unsafe repository path: {path}")
    return str(parsed)


def _valid_branch_name(branch):
    if not isinstance(branch, str) or not branch or len(branch) > 200:
        return False
    forbidden = ("..", "@{", "\\", "~", "^", ":", "?", "*", "[")
    if any(item in branch for item in forbidden):
        return False
    if any(ord(char) < 32 or ord(char) == 127 or char.isspace() for char in branch):
        return False
    if branch == "@" or branch.startswith(("/", ".")) or branch.endswith(("/", ".")):
        return False
    parts = branch.split("/")
    if any(not part or part.startswith(".") or part.endswith(".lock") for part in parts):
        return False
    return True


def _validate_files(files):
    if not isinstance(files, list) or not files:
        raise ValueError("files must be a non-empty array.")
    if len(files) > settings.MAX_PUSH_FILES:
        raise ValueError(f"A push may contain at most {settings.MAX_PUSH_FILES} files.")
    validated = []
    seen = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Each file entry must be an object.")
        path = _validate_path(item.get("path"))
        if path in seen:
            raise ValueError(f"Duplicate file path: {path}")
        seen.add(path)
        delete = bool(item.get("delete", False))
        if delete and ("content" in item or "content_base64" in item):
            raise ValueError(f"Deleted file {path} must not include content.")
        if not delete:
            has_text = "content" in item
            has_binary = "content_base64" in item
            if has_text == has_binary:
                raise ValueError(f"File {path} needs exactly one of content or content_base64.")
            value = item["content"] if has_text else item["content_base64"]
            if not isinstance(value, str):
                raise ValueError(f"Content for {path} must be a string.")
            if has_binary:
                try:
                    decoded = base64.b64decode(value, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ValueError(f"content_base64 for {path} is not valid base64.") from exc
                size = len(decoded)
            else:
                size = len(value.encode("utf-8"))
            if size > settings.MAX_FILE_BYTES:
                raise ValueError(f"File {path} exceeds the size limit.")
            mode = item.get("mode", "100644")
            if mode not in {"100644", "100755"}:
                raise ValueError(f"File {path} has an unsupported mode.")
            item = {**item, "mode": mode}
        validated.append({**item, "path": path, "delete": delete})
    return validated


@csrf_exempt
@require_GET
def api_projects(request):
    auth = authenticate_request(request)
    if auth.error:
        return auth.error
    projects = Project.objects.filter(is_active=True)
    if not auth.token.all_projects:
        projects = projects.filter(agent_tokens=auth.token)
    data = [
        {
            "slug": project.slug,
            "name": project.name,
            "repository": project.full_name,
            "default_branch": project.default_branch,
            "direct_push_enabled": project.direct_push_enabled,
            "allowed_branches": [
                item.strip()
                for item in project.allowed_branches.split(",")
                if item.strip()
            ],
        }
        for project in projects.distinct()
    ]
    return JsonResponse({"projects": data})


@csrf_exempt
@require_POST
def api_push(request):
    auth = authenticate_request(request)
    if auth.error:
        return auth.error
    try:
        body = _json_body(request)
        project_slug = body.get("project")
        if not project_slug:
            raise ValueError("project is required.")
        project = Project.objects.get(slug=project_slug, is_active=True)
        if not auth.token.can_access(project):
            return JsonResponse({"error": "This token cannot access that project."}, status=403)
        if not project.direct_push_enabled:
            return JsonResponse({"error": "Direct push is disabled for this project."}, status=403)
        branch = body.get("branch") or project.default_branch
        if not _valid_branch_name(branch) or not project.branch_is_allowed(branch):
            return JsonResponse({"error": f"Branch '{branch}' is not allowed."}, status=403)
        message = body.get("commit_message")
        if not isinstance(message, str) or not message.strip() or len(message) > 500:
            raise ValueError("commit_message is required and must be at most 500 characters.")
        expected_head = body.get("expected_head")
        if expected_head is not None:
            if (
                not isinstance(expected_head, str)
                or len(expected_head) != 40
                or any(char not in "0123456789abcdefABCDEF" for char in expected_head)
            ):
                raise ValueError("expected_head must be a 40-character Git commit SHA.")
        files = _validate_files(body.get("files"))
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found or inactive."}, status=404)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded_for.split(",")[0].strip() or request.META.get("REMOTE_ADDR")
    record = PushRecord.objects.create(
        project=project,
        token=auth.token,
        branch=branch,
        commit_message=message.strip(),
        file_count=len(files),
        request_ip=ip or None,
    )
    try:
        with GitHubClient(project) as github:
            result = github.push_files(
                branch=branch,
                message=message.strip(),
                files=files,
                expected_head=expected_head,
            )
    except GitHubAPIError as exc:
        record.status = "failed"
        record.error_message = str(exc)
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_message", "completed_at"])
        payload = {"error": str(exc), "push_id": record.pk}
        if settings.DEBUG and exc.details:
            payload["details"] = exc.details
        return JsonResponse(payload, status=exc.status_code)
    except Exception:
        record.status = "failed"
        record.error_message = "Unexpected server error. Check server logs."
        record.completed_at = timezone.now()
        record.save(update_fields=["status", "error_message", "completed_at"])
        raise

    record.status = "success"
    record.commit_sha = result["sha"]
    record.commit_url = result["url"]
    record.completed_at = timezone.now()
    record.save(update_fields=["status", "commit_sha", "commit_url", "completed_at"])
    return JsonResponse(
        {
            "ok": True,
            "push_id": record.pk,
            "project": project.slug,
            "repository": project.full_name,
            "branch": branch,
            "commit_sha": result["sha"],
            "commit_url": result["url"],
            "previous_head": result["previous_head"],
        },
        status=201,
    )


@csrf_exempt
@require_GET
def api_pull(request):
    auth = authenticate_request(request)
    if auth.error:
        return auth.error

    project_slug = request.GET.get("project")
    if not project_slug:
        return JsonResponse({"error": "project is required."}, status=400)

    try:
        project = Project.objects.get(slug=project_slug, is_active=True)
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found or inactive."}, status=404)

    if not auth.token.can_access(project):
        return JsonResponse({"error": "This token cannot access that project."}, status=403)

    branch = request.GET.get("branch") or project.default_branch
    if not _valid_branch_name(branch) or not project.branch_is_allowed(branch):
        return JsonResponse({"error": f"Branch '{branch}' is not allowed."}, status=403)

    path = request.GET.get("path") or ""
    recursive = request.GET.get("recursive") in ("1", "true")

    try:
        with GitHubClient(project) as github:
            if recursive:
                head_sha = github.get_ref(branch)
                commit = github.get_commit(head_sha)
                tree_sha = commit["tree"]["sha"]
                tree_data = github.get_tree(tree_sha, recursive=True)
                return JsonResponse({
                    "project": project.slug,
                    "branch": branch,
                    "commit_sha": head_sha,
                    "tree": tree_data.get("tree", [])
                })
            else:
                contents = github.get_contents(path, branch)
                return JsonResponse({
                    "project": project.slug,
                    "branch": branch,
                    "path": path,
                    "contents": contents
                })
    except GitHubAPIError as exc:
        payload = {"error": str(exc)}
        if settings.DEBUG and exc.details:
            payload["details"] = exc.details
        return JsonResponse(payload, status=exc.status_code)
    except Exception as exc:
        return JsonResponse({"error": f"Unexpected server error: {str(exc)}"}, status=500)


@csrf_exempt
@require_GET
def api_openapi(request):
    server_url = request.build_absolute_uri("/api/v1").rstrip("/")
    schema = {
        "openapi": "3.1.0",
        "info": {
            "title": "AI Git Gateway API",
            "description": "Secure API to discover projects, pull file structures/contents, and push commits to GitHub.",
            "version": "1.0.0"
        },
        "servers": [
            {
                "url": server_url,
                "description": "Current gateway server"
            }
        ],
        "paths": {
            "/projects": {
                "get": {
                    "summary": "List allowed projects",
                    "description": "Retrieve the list of projects allowed for this agent token, along with repository details and branch policies.",
                    "operationId": "listProjects",
                    "responses": {
                        "200": {
                            "description": "List of allowed projects",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "projects": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "slug": { "type": "string" },
                                                        "name": { "type": "string" },
                                                        "repository": { "type": "string" },
                                                        "default_branch": { "type": "string" },
                                                        "direct_push_enabled": { "type": "boolean" },
                                                        "allowed_branches": {
                                                            "type": "array",
                                                            "items": { "type": "string" }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/pull": {
                "get": {
                    "summary": "Pull repository file tree or file contents",
                    "description": "Retrieve a list of files (the tree) or fetch the contents of a specific file.",
                    "operationId": "pullFiles",
                    "parameters": [
                        {
                            "name": "project",
                            "in": "query",
                            "required": True,
                            "description": "The project slug",
                            "schema": { "type": "string" }
                        },
                        {
                            "name": "branch",
                            "in": "query",
                            "required": False,
                            "description": "Target branch (defaults to the project's default branch)",
                            "schema": { "type": "string" }
                        },
                        {
                            "name": "path",
                            "in": "query",
                            "required": False,
                            "description": "Relative path to file or directory. If not specified, defaults to root folder.",
                            "schema": { "type": "string" }
                        },
                        {
                            "name": "recursive",
                            "in": "query",
                            "required": False,
                            "description": "Set to true to fetch the entire repository directory tree recursively.",
                            "schema": { "type": "boolean" }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "File tree or file contents response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "project": { "type": "string" },
                                            "branch": { "type": "string" },
                                            "path": { "type": "string" },
                                            "contents": {
                                                "type": "array",
                                                "items": { "type": "object", "additionalProperties": True }
                                            },
                                            "tree": {
                                                "type": "array",
                                                "items": { "type": "object", "additionalProperties": True }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/push": {
                "post": {
                    "summary": "Push new commit",
                    "description": "Commit changes and push directly to GitHub.",
                    "operationId": "pushCommit",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "project": { "type": "string", "description": "The project slug" },
                                        "branch": { "type": "string", "description": "Target branch" },
                                        "commit_message": { "type": "string", "description": "Commit message" },
                                        "expected_head": { "type": "string", "description": "Optional current commit SHA for conflict protection" },
                                        "files": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "path": { "type": "string", "description": "Relative file path" },
                                                    "content": { "type": "string", "description": "UTF-8 content for text files" },
                                                    "content_base64": { "type": "string", "description": "Base64 content for binary files" },
                                                    "delete": { "type": "boolean", "description": "Set to true to delete this file" }
                                                },
                                                "required": ["path"]
                                            }
                                        }
                                    },
                                    "required": ["project", "commit_message", "files"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Commit pushed successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "ok": { "type": "boolean" },
                                            "push_id": { "type": "integer" },
                                            "project": { "type": "string" },
                                            "repository": { "type": "string" },
                                            "branch": { "type": "string" },
                                            "commit_sha": { "type": "string" },
                                            "commit_url": { "type": "string" },
                                            "previous_head": { "type": "string" }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {},
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer"
                }
            }
        },
        "security": [
            {
                "BearerAuth": []
            }
        ]
    }
    return JsonResponse(schema)
