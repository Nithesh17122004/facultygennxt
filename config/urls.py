"""Root URL configuration for FacultyNxtGen."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.accounts import views as account_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("documents/", include("apps.documents.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("search/", include("apps.search.urls")),
    path("dashboard/candidate/", include("apps.candidates.urls")),
    path("dashboard/admin/", include("apps.dashboard.urls")),
    path("", include("apps.institutions.urls")),
    path("", include("apps.applications.urls")),
    path("dashboard/", account_views.redirect_dashboard),
    path("", include("apps.jobs.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "apps.core.views.error_400"
handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
