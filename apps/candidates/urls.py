from django.urls import path

from . import views

app_name = "candidates"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("privacy/", views.privacy, name="privacy"),
    path("settings/", views.settings_view, name="settings"),
    path("qualifications/", views.qualifications, name="qualifications"),
    path("qualifications/<uuid:pk>/edit/", views.qualification_edit, name="qualification_edit"),
    path("qualifications/<uuid:pk>/delete/", views.qualification_delete, name="qualification_delete"),
    path("teaching-experience/", views.teaching_experience, name="teaching_experience"),
    path("teaching-experience/<uuid:pk>/edit/", views.teaching_experience_edit, name="teaching_experience_edit"),
    path("teaching-experience/<uuid:pk>/delete/", views.teaching_experience_delete, name="teaching_experience_delete"),
    path("research-experience/", views.research_experience, name="research_experience"),
    path("research-experience/<uuid:pk>/edit/", views.research_experience_edit, name="research_experience_edit"),
    path("research-experience/<uuid:pk>/delete/", views.research_experience_delete, name="research_experience_delete"),
    path("publications/", views.publications, name="publications"),
    path("publications/<uuid:pk>/edit/", views.publication_edit, name="publication_edit"),
    path("publications/<uuid:pk>/delete/", views.publication_delete, name="publication_delete"),
    path("certifications/", views.certifications, name="certifications"),
    path("certifications/<uuid:pk>/edit/", views.certification_edit, name="certification_edit"),
    path("certifications/<uuid:pk>/delete/", views.certification_delete, name="certification_delete"),
    path("documents/", views.documents, name="documents"),
    path("saved-jobs/", views.saved_jobs, name="saved_jobs"),
    path("job-alerts/", views.job_alerts, name="job_alerts"),
    path("job-alerts/create/", views.job_alert_create, name="job_alert_create"),
    path("job-alerts/<uuid:pk>/edit/", views.job_alert_edit, name="job_alert_edit"),
    path("job-alerts/<uuid:pk>/toggle/", views.job_alert_toggle, name="job_alert_toggle"),
    path("job-alerts/<uuid:pk>/delete/", views.job_alert_delete, name="job_alert_delete"),
    path("recommended-jobs/", views.recommended_jobs, name="recommended_jobs"),
]
