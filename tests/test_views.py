import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_public_instructions_and_health_are_available(client):
    instructions = client.get(reverse("instructions"))
    assert instructions.status_code == 200
    assert b"For AI coding tools" in instructions.content

    health = client.get(reverse("health"))
    assert health.status_code == 200
    assert health.json()["ok"] is True

    readiness = client.get(reverse("readiness"))
    assert readiness.status_code == 200
    assert readiness.json()["database"] == "ready"


def test_dashboard_redirects_to_allauth_login(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert reverse("account_login") in response.url


def test_staff_user_can_open_dashboard(client):
    user = get_user_model().objects.create_user(
        username="admin",
        password="correct-horse-battery-staple",
        is_staff=True,
    )
    client.force_login(user)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"Give AI a safe lane to GitHub" in response.content


def test_non_staff_user_cannot_open_dashboard(client):
    user = get_user_model().objects.create_user(username="viewer", password="password")
    client.force_login(user)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 403
    assert b"Staff access required" in response.content


def test_signup_is_closed(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200
    assert b"Sign-up is closed" in response.content


def test_token_page_is_never_cached(client):
    user = get_user_model().objects.create_user(
        username="admin-cache",
        password="correct-horse-battery-staple",
        is_staff=True,
    )
    client.force_login(user)
    response = client.get(reverse("token_list"))
    assert response.status_code == 200
    assert "no-cache" in response.headers["Cache-Control"]
    assert "no-store" in response.headers["Cache-Control"]
