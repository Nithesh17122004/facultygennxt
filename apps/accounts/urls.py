from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_candidate, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verify-email/<str:uidb64>/<str:token>/", views.verify_email, name="verify_email"),
    path("verify-email/", views.verify_email_pending, name="verify_email_pending"),
    path("verify-email/resend/", views.resend_verification, name="resend_verification"),
    path("password-reset/", views.password_reset_request, name="password_reset"),
    path(
        "password-reset/<str:uidb64>/<str:token>/",
        views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path("password-change/", views.AccountPasswordChangeView.as_view(), name="password_change"),
    path("security/", views.account_security, name="security"),
    path("identity/", views.account_identity, name="identity"),
    path("security/mfa/setup/", views.mfa_setup, name="mfa_setup"),
    path("security/mfa/verify/", views.mfa_verify, name="mfa_verify"),
    path("security/mfa/disable/", views.mfa_disable, name="mfa_disable"),
    path("security/export/", views.export_data, name="export_data"),
    path("security/delete/", views.delete_account, name="delete_account"),
    path("dashboard/", views.redirect_dashboard, name="dashboard_redirect"),
]
