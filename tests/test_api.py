import json
from unittest.mock import patch

import pytest
from django.urls import reverse

from gateway.models import AgentToken, Project, PushRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def project():
    return Project.objects.create(name="Example", github_owner="owner", github_repo="repo")


@pytest.fixture
def token(project):
    obj, raw = AgentToken.issue(name="Agent", all_projects=False)
    obj.projects.add(project)
    return obj, raw


def auth(raw):
    return {"HTTP_AUTHORIZATION": f"Bearer {raw}"}


def test_projects_are_scoped(client, project, token):
    _, raw = token
    response = client.get(reverse("api_projects"), **auth(raw))
    assert response.status_code == 200
    assert response.json()["projects"][0]["slug"] == project.slug


def test_rejects_unsafe_path(client, project, token):
    _, raw = token
    response = client.post(
        reverse("api_push"),
        data=json.dumps(
            {
                "project": project.slug,
                "commit_message": "bad",
                "files": [{"path": "../x", "content": "x"}],
            }
        ),
        content_type="application/json",
        **auth(raw),
    )
    assert response.status_code == 400


@patch("gateway.api.GitHubClient.push_files")
def test_push_success(mock_push, client, project, token):
    mock_push.return_value = {
        "sha": "a" * 40,
        "url": "https://github.com/o/r/commit/a",
        "previous_head": "b" * 40,
    }
    _, raw = token
    response = client.post(
        reverse("api_push"),
        data=json.dumps(
            {
                "project": project.slug,
                "branch": "main",
                "commit_message": "Ship",
                "files": [{"path": "app.py", "content": "print(1)\n"}],
            }
        ),
        content_type="application/json",
        **auth(raw),
    )
    assert response.status_code == 201
    assert PushRecord.objects.get().status == "success"


def test_revoked_token_is_rejected(client, project, token):
    obj, raw = token
    obj.revoke()
    response = client.get(reverse("api_projects"), **auth(raw))
    assert response.status_code == 401


def test_rejects_non_object_json(client, project, token):
    _, raw = token
    response = client.post(
        reverse("api_push"),
        data=json.dumps([]),
        content_type="application/json",
        **auth(raw),
    )
    assert response.status_code == 400
    assert "JSON object" in response.json()["error"]


def test_rejects_invalid_expected_head(client, project, token):
    _, raw = token
    response = client.post(
        reverse("api_push"),
        data=json.dumps(
            {
                "project": project.slug,
                "commit_message": "Ship",
                "expected_head": "not-a-sha",
                "files": [{"path": "app.py", "content": "print(1)\n"}],
            }
        ),
        content_type="application/json",
        **auth(raw),
    )
    assert response.status_code == 400
    assert "expected_head" in response.json()["error"]
