from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    # Institutions
    path("institutions/", views.institutions, name="institutions"),
    path("institutions/pending/", views.institutions_pending, name="institutions_pending"),
    path("institutions/<uuid:pk>/", views.institution_detail, name="institution_detail"),
    path("institutions/<uuid:pk>/decision/", views.institution_decision, name="institution_decision"),
    # Jobs
    path("jobs/", views.jobs, name="jobs"),
    path("jobs/create/", views.admin_job_create, name="admin_job_create"),
    path("jobs/pending/", views.jobs_pending, name="jobs_pending"),
    path("jobs/<uuid:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<uuid:pk>/decision/", views.job_decision, name="job_decision"),
    # Reports
    path("reports/", views.reports, name="reports"),
    path("reports/<uuid:pk>/", views.report_detail, name="report_detail"),
    path("reports/<uuid:pk>/resolve/", views.resolve_report, name="report_resolve"),
    # Users
    path("users/", views.users, name="users"),
    path("users/<uuid:pk>/", views.user_detail, name="user_detail"),
    path("users/<uuid:pk>/moderate/", views.user_moderate, name="user_moderate"),
    # Content and audit
    path("content/", views.content, name="content"),
    path("content/enquiries/<uuid:pk>/", views.enquiry_detail, name="enquiry_detail"),
    path("audit/", views.audit_log, name="audit"),
    path("team/", views.team, name="team"),
]
