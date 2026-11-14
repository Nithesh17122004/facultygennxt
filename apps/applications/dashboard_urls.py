from django.urls import path

from . import views

app_name = "applications"

urlpatterns = [
    path("", views.recruiter_list, name="recruiter_list"),
    path("<uuid:pk>/", views.recruiter_detail, name="recruiter_detail"),
]
