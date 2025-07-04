from django.urls import path
from . import views

urlpatterns = [
    path('', views.job_search, name='job_search'),
    path('job/<int:job_id>/', views.job_detail, name='job_detail'),
] 