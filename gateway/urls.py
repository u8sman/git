from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("projects/", views.project_list, name="project_list"),
    path("projects/new/", views.project_create, name="project_create"),
    path("projects/<int:pk>/edit/", views.project_edit, name="project_edit"),
    path("tokens/", views.token_list, name="token_list"),
    path("tokens/<int:pk>/revoke/", views.token_revoke, name="token_revoke"),
    path("tokens/<int:pk>/toggle-pause/", views.token_toggle_pause, name="token_toggle_pause"),
    path("history/", views.push_history, name="push_history"),
    path("instructions/", views.instructions, name="instructions"),
    path("api/v1/instructions", views.instructions_json, name="instructions_json"),
    path("api/v1/projects", api.api_projects, name="api_projects"),
    path("api/v1/pull", api.api_pull, name="api_pull"),
    path("api/v1/push", api.api_push, name="api_push"),
    path("api/v1/openapi.json", api.api_openapi, name="api_openapi"),
    path("health/", views.health, name="health"),
    path("ready/", views.readiness, name="readiness"),
]
