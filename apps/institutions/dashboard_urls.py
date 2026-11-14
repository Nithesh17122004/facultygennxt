from django.urls import path

from . import views

app_name = "institutions"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("profile/documents/upload/", views.upload_document, name="upload_document"),
    path("profile/request-verification/", views.request_verification, name="request_verification"),
    path("team/", views.recruiters, name="recruiters"),
    path("team/invite/", views.recruiter_invite, name="recruiter_invite"),
    path("team/<uuid:pk>/toggle/", views.recruiter_toggle, name="recruiter_toggle"),
    path("team/<uuid:pk>/resend-invite/", views.recruiter_resend_invite, name="recruiter_resend_invite"),
    path("settings/", views.settings_view, name="settings"),
]
