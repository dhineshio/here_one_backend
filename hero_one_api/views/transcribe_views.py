"""
Transcribe views for handling file uploads and content generation
"""
import os
import logging
from pathlib import Path
from ninja import Router, File, Query
from ninja.files import UploadedFile
from ninja.security import HttpBearer
from rest_framework_simplejwt.tokens import AccessToken
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from typing import Optional

from hero_one_api.models import Job, Client
from hero_one_api.services.transcribe_service import TranscribeService
from hero_one_api.services.audio_service import AudioService
from hero_one_api.schemas import ErrorResponseSchema

logger = logging.getLogger(__name__)

User = get_user_model()

# JWT Authentication
class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
            return user
        except Exception:
            return None

transcribe_router = Router(tags=["Transcribe"])


# Supported file extensions
AUDIO_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac']
VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm']
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']


def get_file_type(filename: str) -> Optional[str]:
    """Determine file type based on extension"""
    ext = Path(filename).suffix.lower()
    
    if ext in AUDIO_EXTENSIONS:
        return 'audio'
    elif ext in VIDEO_EXTENSIONS:
        return 'video'
    elif ext in IMAGE_EXTENSIONS:
        return 'image'
    return None


def save_uploaded_file(file: UploadedFile, user_id: int) -> str:
    """Save uploaded file to media directory"""
    # Create upload directory structure: media/uploads/{user_id}/
    upload_dir = Path(settings.MEDIA_ROOT) / 'uploads' / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename with timestamp
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{file.name}"
    file_path = upload_dir / filename
    
    # Save file
    with open(file_path, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)
    
    return str(file_path)


@transcribe_router.post("/upload", response={200: dict, 400: ErrorResponseSchema, 401: ErrorResponseSchema}, auth=AuthBearer())
def upload_and_generate_content(
    request,
    client_id: int,
    file: UploadedFile = File(...),
    caption_length: str = 'medium',
    description_length: str = 'medium',
    hashtag_count: int = 15
):
    """
    Upload a file (audio, video, or image) and generate social media content
    
    - **client_id**: ID of the client/brand this content is for (required)
    - **file**: Audio (mp3, wav, etc.), Video (mp4, mov, etc.), or Image (jpg, png, etc.)
    - **caption_length**: 'short', 'medium', or 'long' (default: medium)
    - **description_length**: 'short', 'medium', or 'long' (default: medium)
    - **hashtag_count**: Number of hashtags (5-30, default: 15)
    
    Returns job information with job_id to track progress
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {"detail": "Authentication required"}
        
        user = request.auth
        
        # Check if client exists and belongs to user
        try:
            client = Client.objects.get(id=client_id, user=user)
        except Client.DoesNotExist:
            return 400, {"detail": f"Client with ID {client_id} not found or does not belong to you"}
        
        # Check if user can use credit
        if not user.can_use_credit():
            return 400, {"detail": "Daily credit limit reached. Please upgrade to premium for unlimited access."}
        
        # Validate file type
        file_type = get_file_type(file.name)
        if not file_type:
            return 400, {
                "detail": f"Unsupported file type. Supported formats: "
                         f"Audio ({', '.join(AUDIO_EXTENSIONS)}), "
                         f"Video ({', '.join(VIDEO_EXTENSIONS)}), "
                         f"Image ({', '.join(IMAGE_EXTENSIONS)})"
            }
        
        # Validate parameters
        if caption_length not in ['short', 'medium', 'long']:
            return 400, {"detail": "caption_length must be 'short', 'medium', or 'long'"}
        
        if description_length not in ['short', 'medium', 'long']:
            return 400, {"detail": "description_length must be 'short', 'medium', or 'long'"}
        
        hashtag_count = max(5, min(30, hashtag_count))
        
        # Save uploaded file
        file_path = save_uploaded_file(file, user.id)
        logger.info(f"File uploaded: {file_path} by user {user.email}")
        
        # Use credit
        success, message = user.use_credit(
            action_type='content_generation',
            description=f"Generate content from {file_type}: {file.name}"
        )
        
        if not success:
            # Delete uploaded file if credit usage failed
            if os.path.exists(file_path):
                os.remove(file_path)
            return 400, {"detail": message}
        
        # Create job
        job = Job.objects.create(
            client=client,
            user=user,
            file_type=file_type,
            original_filename=file.name,
            file_path=file_path,
            caption_length=caption_length,
            description_length=description_length,
            hashtag_count=hashtag_count,
            status='pending'
        )
        
        logger.info(f"Job created: {job.job_id} for user {user.email}")
        
        # Process the file based on type
        try:
            job.start_processing()
            
            if file_type == 'image':
                # Process image directly
                result = TranscribeService.generate_social_media_content_from_image(
                    image_file_path=file_path,
                    caption_length=caption_length,
                    description_length=description_length,
                    hashtag_count=hashtag_count
                )
                
                if "error" in result:
                    job.mark_failed(result["error"])
                    return 400, {"detail": result["error"], "job_id": str(job.job_id)}
                
                job.mark_completed(result)
                
            elif file_type == 'video':
                # Convert video to audio first
                logger.info(f"Converting video to audio: {file_path}")
                success, audio_path_or_error = AudioService.video_to_audio(file_path)
                
                if not success:
                    job.mark_failed(f"Video to audio conversion failed: {audio_path_or_error}")
                    return 400, {"detail": audio_path_or_error, "job_id": str(job.job_id)}
                
                # Save converted audio path
                job.converted_audio_path = audio_path_or_error
                job.save(update_fields=['converted_audio_path'])
                
                logger.info(f"Video converted to audio: {audio_path_or_error}")
                
                # Generate content from audio
                result = TranscribeService.generate_social_media_content(
                    audio_file_path=audio_path_or_error,
                    caption_length=caption_length,
                    description_length=description_length,
                    hashtag_count=hashtag_count
                )
                
                if "error" in result:
                    job.mark_failed(result["error"])
                    return 400, {"detail": result["error"], "job_id": str(job.job_id)}
                
                job.mark_completed(result)
                
            elif file_type == 'audio':
                # Process audio directly
                result = TranscribeService.generate_social_media_content(
                    audio_file_path=file_path,
                    caption_length=caption_length,
                    description_length=description_length,
                    hashtag_count=hashtag_count
                )
                
                if "error" in result:
                    job.mark_failed(result["error"])
                    return 400, {"detail": result["error"], "job_id": str(job.job_id)}
                
                job.mark_completed(result)
            
            logger.info(f"Job completed: {job.job_id}")
            
            return 200, {
                "message": "Content generated successfully",
                "job_id": str(job.job_id),
                "client_id": client.id,
                "client_name": client.client_name,
                "file_type": file_type,
                "status": "completed",
                "result": result,
                "credits_used": message
            }
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            logger.error(f"Job {job.job_id} failed: {error_msg}")
            job.mark_failed(error_msg)
            return 400, {"detail": error_msg, "job_id": str(job.job_id)}
    
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return 400, {"detail": f"Upload failed: {str(e)}"}


@transcribe_router.get("/job/{job_id}", response={200: dict, 404: ErrorResponseSchema, 401: ErrorResponseSchema}, auth=AuthBearer())
def get_job_status(request, job_id: str):
    """
    Get the status and results of a job
    
    - **job_id**: UUID of the job
    
    Returns job status, results (if completed), and processing information
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {"detail": "Authentication required"}
        
        user = request.auth
        
        # Get job
        try:
            job = Job.objects.get(job_id=job_id, user=user)
        except Job.DoesNotExist:
            return 404, {"detail": "Job not found"}
        
        response = {
            "job_id": str(job.job_id),
            "client_id": job.client.id,
            "client_name": job.client.client_name,
            "file_type": job.file_type,
            "original_filename": job.original_filename,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "processing_time": job.get_duration_display(),
        }
        
        if job.status == 'completed':
            response["result"] = job.result_data
        elif job.status == 'failed':
            response["error"] = job.error_message
        
        return 200, response
        
    except Exception as e:
        logger.error(f"Get job status failed: {str(e)}")
        return 400, {"detail": f"Failed to get job status: {str(e)}"}


@transcribe_router.get("/jobs", response={200: dict, 401: ErrorResponseSchema}, auth=AuthBearer())
def list_user_jobs(request, limit: int = Query(10), offset: int = Query(0), client_id: Optional[int] = Query(None)):
    """
    List all jobs for the authenticated user
    
    - **limit**: Number of jobs to return (default: 10, max: 100)
    - **offset**: Number of jobs to skip (default: 0)
    - **client_id**: Filter by specific client ID (optional)
    
    Returns paginated list of user's jobs
    """
    try:
        # Check authentication
        if not request.auth:
            return 401, {"detail": "Authentication required"}
        
        user = request.auth
        
        # Validate and limit pagination
        limit = min(max(1, limit), 100)
        offset = max(0, offset)
        
        # Get jobs - filter by client if provided
        jobs_query = Job.objects.filter(user=user)
        
        if client_id:
            # Verify client belongs to user
            try:
                client = Client.objects.get(id=client_id, user=user)
                jobs_query = jobs_query.filter(client=client)
            except Client.DoesNotExist:
                return 400, {"detail": f"Client with ID {client_id} not found or does not belong to you"}
        
        jobs = jobs_query.select_related('client')[offset:offset + limit]
        total_count = jobs_query.count()
        
        jobs_list = [
            {
                "job_id": str(job.job_id),
                "client_id": job.client.id,
                "client_name": job.client.client_name,
                "file_type": job.file_type,
                "original_filename": job.original_filename,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "processing_time": job.get_duration_display(),
            }
            for job in jobs
        ]
        
        return 200, {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "jobs": jobs_list
        }
        
    except Exception as e:
        logger.error(f"List jobs failed: {str(e)}")
        return 400, {"detail": f"Failed to list jobs: {str(e)}"}
