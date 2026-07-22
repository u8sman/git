import pytest
from django.contrib.auth import get_user_model

from gateway.models import AgentToken, Project

pytestmark = pytest.mark.django_db


def test_token_is_shown_once_and_only_hash_is_stored():
    user = get_user_model().objects.create_user("admin")
    token, raw = AgentToken.issue(name="Test", created_by=user, all_projects=True)
    assert raw.startswith("aig_")
    assert raw not in token.token_hash
    assert AgentToken.authenticate(raw) == token


def test_revoked_token_cannot_authenticate():
    token, raw = AgentToken.issue(name="Test", all_projects=True)
    token.revoke()
    assert AgentToken.authenticate(raw) is None


def test_branch_patterns():
    project = Project.objects.create(
        name="Example",
        github_owner="o",
        github_repo="r",
        allowed_branches="main,ai/*",
    )
    assert project.branch_is_allowed("main")
    assert project.branch_is_allowed("ai/job-1")
    assert not project.branch_is_allowed("release")
