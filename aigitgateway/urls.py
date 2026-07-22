from allauth.account.decorators import secure_admin_login
from django.contrib import admin
from django.urls import include, path

admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("gateway.urls")),
]
