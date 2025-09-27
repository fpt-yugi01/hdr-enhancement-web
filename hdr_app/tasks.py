# hdr_app/tasks.py
from celery import shared_task
import torch
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import os
import sys
import logging
from django.conf import settings
from .models import HDREnhancementTask

# Add DiffHDR to path
sys.path.append(os.path.join(settings.BASE_DIR, 'DiffHDR-pytorch'))

logger = logging.getLogger(__name__)

@shared_task
def process_hdr_enhancement(task_id):
    """
    Celery task to process HDR enhancement using DiffHDR model
    """
    try:
        task = HDREnhancementTask.objects.get(id=task_id)
        task.status = 'processing'
        task.progress = 10
        task.save()
        
        # Load the model (you'll need to implement this based on DiffHDR structure)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {device}")
        
        # Update progress
        task.progress = 30
        task.save()
        
        # Load and preprocess image
        input_path = os.path.join(settings.MEDIA_ROOT, task.file_path)
        image = Image.open(input_path).convert('RGB')
        
        # Preprocessing transforms
        transform = transforms.Compose([
            transforms.Resize((256, 256)),  # Adjust based on model requirements
            transforms.ToTensor(),
        ])
        
        input_tensor = transform(image).unsqueeze(0).to(device)
        
        # Update progress
        task.progress = 50
        task.save()
        
        # Load DiffHDR model (implement based on actual model structure)
        model = load_diffhdr_model(device)
        
        # Update progress
        task.progress = 70
        task.save()
        
        # Process image
        with torch.inference_mode():
            enhanced_tensor = model(input_tensor)
        
        # Update progress
        task.progress = 90
        task.save()
        
        # Post-process and save result
        enhanced_image = tensor_to_pil(enhanced_tensor)
        
        # Save result
        result_filename = f"enhanced_{task_id}_{task.original_filename}"
        result_path = f"results/{result_filename}"
        full_result_path = os.path.join(settings.MEDIA_ROOT, result_path)
        
        os.makedirs(os.path.dirname(full_result_path), exist_ok=True)
        enhanced_image.save(full_result_path, 'JPEG', quality=95)
        
        # Update task
        task.result_path = result_path
        task.status = 'completed'
        task.progress = 100
        task.save()
        
        logger.info(f"HDR enhancement completed for task {task_id}")
        return {'status': 'success', 'result_path': result_path}
        
    except Exception as e:
        logger.error(f"HDR enhancement failed for task {task_id}: {str(e)}")
        task = HDREnhancementTask.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        raise

def load_diffhdr_model(device):
    """
    Load the DiffHDR model - implement based on actual model structure
    """
    try:
        # This is a placeholder - you'll need to implement based on the actual DiffHDR model
        from diffhdr_model import DiffHDRNet  # Adjust import based on actual structure
        
        model = DiffHDRNet()
        
        # Load pretrained weights if available
        weights_path = settings.HDR_MODEL_WEIGHTS
        if os.path.exists(weights_path):
            model.load_state_dict(torch.load(weights_path, map_location=device))
        
        model.to(device)
        model.eval()
        
        return model
    except Exception as e:
        logger.error(f"Failed to load DiffHDR model: {str(e)}")
        raise

def tensor_to_pil(tensor):
    """
    Convert PyTorch tensor to PIL Image
    """
    # Remove batch dimension and move to CPU
    tensor = tensor.squeeze(0).cpu()
    
    # Denormalize if needed (adjust based on your model's output)
    tensor = torch.clamp(tensor, 0, 1)
    
    # Convert to PIL
    transform = transforms.ToPILImage()
    return transform(tensor)