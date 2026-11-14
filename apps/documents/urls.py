from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("<uuid:pk>/download/", views.download, name="download"),
    path("<uuid:pk>/delete/", views.delete_document, name="delete"),
]
