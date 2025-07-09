from django.urls import path

from . import views

urlpatterns = [
    path("", views.job_search, name="job_search"),
    path("job/<int:job_id>/", views.job_detail, name="job_detail"),
    path("websites/", views.manage_websites, name="manage_websites"),
    path(
        "websites/delete/<int:website_id>/", views.delete_website, name="delete_website"
    ),
]
