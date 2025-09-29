# hdr_app/urls.py
from django.urls import path
from . import views

app_name = 'hdr_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
]