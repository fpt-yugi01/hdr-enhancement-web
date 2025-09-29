# hdr_app/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class HDREnhancementTask(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'), 
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hdr_tasks')
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)  # Path to uploaded file
    result_path = models.CharField(max_length=500, blank=True, null=True)  # Path to result file
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.IntegerField(default=0)  # Progress percentage 0-100
    
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Metadata about the enhancement
    processing_time = models.FloatField(null=True, blank=True)  # in seconds
    file_size_original = models.BigIntegerField(null=True, blank=True)  # in bytes
    file_size_result = models.BigIntegerField(null=True, blank=True)  # in bytes
    
    class Meta:
        db_table = 'hdr_enhancement_tasks'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.username} - {self.original_filename} ({self.status})"
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_processing(self):
        return self.status in ['pending', 'processing']
    
    @property
    def has_result(self):
        return self.status == 'completed' and self.result_path

class UserProfile(models.Model):
    """Extended user profile for HDR enhancement service"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='hdr_profile')
    
    # LDAP attributes
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    
    # Service usage limits
    daily_limit = models.IntegerField(default=10)  # Daily processing limit
    monthly_limit = models.IntegerField(default=100)  # Monthly processing limit
    
    # Usage statistics
    total_processed = models.IntegerField(default=0)
    total_successful = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    
    # Preferences
    preferred_output_format = models.CharField(
        max_length=10, 
        choices=[('jpeg', 'JPEG'), ('png', 'PNG'), ('tiff', 'TIFF')],
        default='jpeg'
    )
    preferred_quality = models.IntegerField(default=95)  # For JPEG output
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        
    def __str__(self):
        return f"{self.user.username} - Profile"
    
    def get_daily_usage(self):
        """Get today's processing count"""
        today = timezone.now().date()
        return HDREnhancementTask.objects.filter(
            user=self.user,
            created_at__date=today
        ).count()
    
    def get_monthly_usage(self):
        """Get this month's processing count"""
        now = timezone.now()
        return HDREnhancementTask.objects.filter(
            user=self.user,
            created_at__year=now.year,
            created_at__month=now.month
        ).count()
    
    def can_process_more(self):
        """Check if user can process more images today"""
        return self.get_daily_usage() < self.daily_limit