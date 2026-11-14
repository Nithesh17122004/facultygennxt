from django.urls import path

from . import views

app_name = "applications"

urlpatterns = [
    # Candidate applications
    path("applications/", views.candidate_list, name="candidate_list"),
    path("applications/apply/<uuid:job_id>/", views.apply, name="apply"),
    path("applications/click/<uuid:job_id>/", views.external_click, name="external_click"),
    path("applications/<uuid:pk>/", views.candidate_detail, name="candidate_detail"),
    path("applications/<uuid:pk>/withdraw/", views.withdraw, name="withdraw"),
    # Institution applicant management
    path("dashboard/institution/applicants/", views.recruiter_list, name="recruiter_list"),
    path("dashboard/institution/applicants/<uuid:pk>/", views.recruiter_detail, name="recruiter_detail"),
]
