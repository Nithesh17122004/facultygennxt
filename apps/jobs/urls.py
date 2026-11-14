from django.urls import path

from . import recruiter_views, views

app_name = "jobs"

urlpatterns = [
    # Public
    path("jobs/", views.find_jobs, name="find"),
    path("jobs/teaching/", views.category_jobs, {"category": "teaching"}, name="teaching"),
    path("jobs/research/", views.category_jobs, {"category": "research"}, name="research"),
    path("jobs/non-teaching/", views.category_jobs, {"category": "non_teaching"}, name="non_teaching"),
    path("jobs/<slug:slug>/save/", views.toggle_save, name="toggle_save"),
    path("jobs/<slug:slug>/report/", views.report, name="report"),
    path("jobs/<slug:slug>/", views.job_detail, name="detail"),
    # Focused SEO landing pages
    path("faculty-jobs-in-india/", views.landing_page, {"slug": "faculty-jobs-in-india"}, name="landing_india"),
    path("assistant-professor-jobs/", views.landing_page, {"slug": "assistant-professor-jobs"}, name="landing_assistant_professor"),
    path("professor-jobs/", views.landing_page, {"slug": "professor-jobs"}, name="landing_professor"),
    path("engineering-college-faculty-jobs/", views.landing_page, {"slug": "engineering-college-faculty-jobs"}, name="landing_engineering"),
    path("arts-and-science-college-jobs/", views.landing_page, {"slug": "arts-and-science-college-jobs"}, name="landing_arts_science"),
    path("research-fellow-jobs/", views.landing_page, {"slug": "research-fellow-jobs"}, name="landing_research"),
    path("faculty-jobs-in-<slug:state_slug>/", views.state_landing_page, name="landing_state"),
    # Recruiter dashboard
    path("dashboard/institution/jobs/", recruiter_views.recruiter_list, name="recruiter_list"),
    path("dashboard/institution/jobs/new/", recruiter_views.recruiter_create, name="recruiter_create"),
    path("dashboard/institution/jobs/<uuid:pk>/", recruiter_views.recruiter_detail, name="recruiter_detail"),
    path("dashboard/institution/jobs/<uuid:pk>/edit/", recruiter_views.recruiter_edit, name="recruiter_edit"),
    path("dashboard/institution/jobs/<uuid:pk>/submit/", recruiter_views.recruiter_submit, name="recruiter_submit"),
    path("dashboard/institution/jobs/<uuid:pk>/delete/", recruiter_views.recruiter_delete, name="recruiter_delete"),
    path("dashboard/institution/jobs/<uuid:pk>/analytics/", recruiter_views.recruiter_analytics, name="recruiter_analytics"),
]
