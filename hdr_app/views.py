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
from django.utils import timezone
from .models import HDREnhancementTask, UserProfile
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
    
    # Convert tasks to JSON-serializable format
    tasks_data = []
    for task in recent_tasks:
        tasks_data.append({
            'id': task.id,
            'original_filename': task.original_filename,
            'status': task.status,
            'progress': task.progress,
            'created_at': task.created_at.isoformat() if task.created_at else '',
            'updated_at': task.updated_at.isoformat() if task.updated_at else '',
        })
    
    context = {
        'user': request.user,
        'recent_tasks_json': json.dumps(tasks_data),  # JSON data for Alpine.js
        'total_tasks': HDREnhancementTask.objects.filter(user=request.user).count(),
        'completed_tasks': HDREnhancementTask.objects.filter(user=request.user, status='completed').count(),
    }
    
    return render(request, 'dashboard.html', context)

def index(request):
    """Landing page"""
    if request.user.is_authenticated:
        return dashboard(request)
    return render(request, 'index.html')

class HDRCancelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, task_id):
        """Cancel HDR enhancement task"""
        try:
            task = get_object_or_404(HDREnhancementTask, id=task_id, user=request.user)
            
            # Only allow canceling pending or processing tasks
            if task.status not in ['pending', 'processing']:
                return Response({'error': 'Task cannot be cancelled'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            # Cancel Celery task if it exists
            if task.celery_task_id:
                from celery import current_app
                current_app.control.revoke(task.celery_task_id, terminate=True)
            
            # Update task status
            task.status = 'cancelled'
            task.error_message = 'Task cancelled by user'
            task.save()
            
            return Response({'success': True, 'message': 'Task cancelled successfully'})
            
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user profile information"""
        try:
            # Get or create user profile
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            # Get usage statistics
            now = timezone.now()
            today = now.date()
            this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            daily_usage = HDREnhancementTask.objects.filter(
                user=request.user,
                created_at__date=today
            ).count()
            
            monthly_usage = HDREnhancementTask.objects.filter(
                user=request.user,
                created_at__gte=this_month_start
            ).count()
            
            # Recent activity
            recent_tasks = HDREnhancementTask.objects.filter(
                user=request.user
            ).order_by('-created_at')[:10]
            
            recent_tasks_data = []
            for task in recent_tasks:
                recent_tasks_data.append({
                    'id': task.id,
                    'original_filename': task.original_filename,
                    'status': task.status,
                    'created_at': task.created_at.isoformat(),
                    'processing_time': task.processing_time,
                })
            
            data = {
                'user': {
                    'username': request.user.username,
                    'email': request.user.email,
                    'first_name': request.user.first_name,
                    'last_name': request.user.last_name,
                    'date_joined': request.user.date_joined.isoformat(),
                    'last_login': request.user.last_login.isoformat() if request.user.last_login else None,
                },
                'profile': {
                    'employee_id': profile.employee_id,
                    'department': profile.department,
                    'daily_limit': profile.daily_limit,
                    'monthly_limit': profile.monthly_limit,
                    'preferred_output_format': profile.preferred_output_format,
                    'preferred_quality': profile.preferred_quality,
                },
                'statistics': {
                    'total_processed': profile.total_processed,
                    'total_successful': profile.total_successful,
                    'total_failed': profile.total_failed,
                    'daily_usage': daily_usage,
                    'monthly_usage': monthly_usage,
                    'daily_remaining': max(0, profile.daily_limit - daily_usage),
                    'monthly_remaining': max(0, profile.monthly_limit - monthly_usage),
                    'success_rate': round((profile.total_successful / max(1, profile.total_processed)) * 100, 2),
                },
                'recent_tasks': recent_tasks_data
            }
            
            return Response(data)
            
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        """Update user profile preferences"""
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            # Update profile fields
            if 'preferred_output_format' in request.data:
                profile.preferred_output_format = request.data['preferred_output_format']
            
            if 'preferred_quality' in request.data:
                quality = int(request.data['preferred_quality'])
                if 1 <= quality <= 100:
                    profile.preferred_quality = quality
            
            profile.save()
            
            return Response({'success': True, 'message': 'Profile updated successfully'})
            
        except Exception as e:
            return Response({'error': str(e)}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@login_required
def profile(request):
    """User profile page"""
    return render(request, 'profile.html')