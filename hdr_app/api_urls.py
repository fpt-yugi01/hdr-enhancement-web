# hdr_app/api_urls.py
from django.urls import path
from . import views

app_name = 'hdr_api'

urlpatterns = [
    path('upload/', views.HDRUploadView.as_view(), name='upload'),
    path('status/<int:task_id>/', views.HDRStatusView.as_view(), name='status'),
    path('result/<int:task_id>/', views.HDRResultView.as_view(), name='result'),
    path('history/', views.HDRHistoryView.as_view(), name='history'),
]