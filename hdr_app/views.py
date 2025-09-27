# hdr_app/views.py
import os
import uuid
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import HDREnhancementTask
from .tasks import process_hdr_enhancement
import json

class HDRUploadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Upload image for HDR enhancement"""
        try:
            if 'image' not in request.FILES:
                return Response({'error': 'No image provided'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            image_file = request.FILES['image']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/tiff']
            if image_file.content_type not in allowed_types:
                return Response({'error': 'Invalid file type. Only JPEG, PNG, and TIFF are allowed.'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Generate unique filename
            file_extension = os.path.splitext(image_file.name)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Save file
            file_path = default_storage.save(
                f"uploads/{unique_filename}", 
                ContentFile(image_file.read())
            )
            
            # Create task record
            task = HDREnhancementTask.objects.create(
                user=request.user,
                original_filename=image_file.name,
                file_path=file_path,
                status='pending'
            )
            
            # Queue the HDR enhancement task
            job = process_hdr_enhancement.delay(task.id)
            task.celery_task_id = job.id
            task.save()
            
            return Response({
                'task_id': task.id,
                'celery_task_id': job.id,
                'status': 'pending',
                'message': 'Image uploaded successfully. Processing started.'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HDRStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, task_id):
        """Get status of HDR enhancement task"""
        try:
            task = get_object_or_404(HDREnhancementTask, id=task_id, user=request.user)
            
            return Response({
                'task_id': task.id,
                'status': task.status,
                'progress': task.progress,
                'original_filename': task.original_filename,
                'result_path': task.result_path,
                'error_message': task.error_message,
                'created_at': task.created_at,
                'updated_at': task.updated_at
            })
            
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HDRResultView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, task_id):
        """Download HDR enhanced result"""
        try:
            task = get_object_or_404(HDREnhancementTask, id=task_id, user=request.user)
            
            if task.status != 'completed' or not task.result_path:
                return Response({'error': 'Task not completed or no result available'}, 
                              status=status.HTTP_404_NOT_FOUND)
            
            # Serve the file
            if default_storage.exists(task.result_path):
                file_content = default_storage.open(task.result_path).read()
                response = HttpResponse(file_content, content_type='image/jpeg')
                response['Content-Disposition'] = f'attachment; filename="hdr_enhanced_{task.original_filename}"'
                return response
            else:
                return Response({'error': 'Result file not found'}, 
                              status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HDRHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's HDR enhancement history"""
        try:
            tasks = HDREnhancementTask.objects.filter(user=request.user).order_by('-created_at')
            
            task_data = []
            for task in tasks:
                task_data.append({
                    'id': task.id,
                    'original_filename': task.original_filename,
                    'status': task.status,
                    'progress': task.progress,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at
                })
            
            return Response({
                'tasks': task_data,
                'total': len(task_data)
            })
            
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@login_required
def dashboard(request):
    """Main dashboard view"""
    recent_tasks = HDREnhancementTask.objects.filter(user=request.user).order_by('-created_at')[:5]
    
    context = {
        'user': request.user,
        'recent_tasks': recent_tasks,
        'total_tasks': HDREnhancementTask.objects.filter(user=request.user).count(),
        'completed_tasks': HDREnhancementTask.objects.filter(user=request.user, status='completed').count(),
    }
    
    return render(request, 'dashboard.html', context)

def index(request):
    """Landing page"""
    if request.user.is_authenticated:
        return dashboard(request)
    return render(request, 'index.html')