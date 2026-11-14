from django.urls import path

from . import views

app_name = "institutions"

urlpatterns = [
    # Public directory
    path("institutions/", views.directory, name="directory"),
    path("institutions/register/", views.register, name="register"),
    path("institutions/invite/<str:uidb64>/<str:token>/", views.accept_invite, name="accept_invite"),
    path("institutions/<slug:slug>/", views.detail, name="detail"),
    # Institution dashboard
    path("dashboard/institution/", views.dashboard, name="dashboard"),
    path("dashboard/institution/profile/", views.profile, name="profile"),
    path("dashboard/institution/profile/documents/upload/", views.upload_document, name="upload_document"),
    path("dashboard/institution/profile/request-verification/", views.request_verification, name="request_verification"),
    path("dashboard/institution/team/", views.recruiters, name="recruiters"),
    path("dashboard/institution/team/invite/", views.recruiter_invite, name="recruiter_invite"),
    path("dashboard/institution/team/<uuid:pk>/toggle/", views.recruiter_toggle, name="recruiter_toggle"),
    path("dashboard/institution/team/<uuid:pk>/resend-invite/", views.recruiter_resend_invite, name="recruiter_resend_invite"),
    path("dashboard/institution/settings/", views.settings_view, name="settings"),
]
