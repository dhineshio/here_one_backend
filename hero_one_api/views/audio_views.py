"""
Audio API views for video to audio conversion
"""
from ninja import NinjaAPI, File
from ninja.files import UploadedFile
from django.http import FileResponse, JsonResponse
from django.conf import settings
from pathlib import Path
import os
import uuid
from ..services.audio_service import AudioService
import logging

logger = logging.getLogger(__name__)

# Create audio API router
audio_api = NinjaAPI(urls_namespace='audio', version='1.0.0')

@audio_api.post("/convert-video-to-audio-async")
def convert_video_to_audio_async(request, video: UploadedFile = File(...)):
    """
    Convert uploaded video to audio (background processing)
    Returns immediately with job ID
    
    Args:
        video: Video file upload
    
    Returns:
        JSON with job_id for tracking
    """
    try:
        # Create media directories
        media_root = Path(settings.BASE_DIR) / 'media'
        video_dir = media_root / 'videos'
        audio_dir = media_root / 'audio'
        video_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        job_id = str(uuid.uuid4())
        video_ext = Path(video.name).suffix
        video_filename = f"{job_id}{video_ext}"
        video_path = video_dir / video_filename
        
        # Save uploaded video
        with open(video_path, 'wb') as f:
            for chunk in video.chunks():
                f.write(chunk)
        
        logger.info(f"Video uploaded for async conversion: {video_path}")
        
        # Convert in background
        audio_filename = f"{job_id}.mp3"
        audio_path = audio_dir / audio_filename
        
        def callback(success, result):
            """Callback after conversion"""
            # Clean up video file
            if os.path.exists(video_path):
                os.remove(video_path)
            
            if success:
                logger.info(f"Async conversion completed: {result}")
            else:
                logger.error(f"Async conversion failed: {result}")
        
        AudioService.video_to_audio_background(
            video_path=str(video_path),
            output_path=str(audio_path),
            audio_format='mp3',
            audio_bitrate='192k',
            callback=callback
        )
        
        return JsonResponse({
            "success": True,
            "message": "Video conversion started",
            "job_id": job_id,
            "download_url": f"/api/audio/download/{job_id}"
        }, status=202)
    
    except Exception as e:
        logger.error(f"Async conversion error: {str(e)}")
        
        # Clean up on error
        if 'video_path' in locals() and os.path.exists(video_path):
            os.remove(video_path)
        
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)

@audio_api.get("/download/{job_id}")
def download_audio(request, job_id: str):
    """
    Download converted audio file by job ID
    
    Args:
        job_id: Job ID from async conversion
    
    Returns:
        Audio file download or error
    """
    try:
        media_root = Path(settings.BASE_DIR) / 'media'
        audio_dir = media_root / 'audio'
        audio_path = audio_dir / f"{job_id}.mp3"
        
        if not audio_path.exists():
            return JsonResponse({
                "success": False,
                "error": "Audio file not found or conversion not complete"
            }, status=404)
        
        # Return audio file
        response = FileResponse(
            open(audio_path, 'rb'),
            content_type='audio/mpeg',
            as_attachment=True,
            filename=f"{job_id}.mp3"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)

@audio_api.get("/status/{job_id}")
def check_conversion_status(request, job_id: str):
    """
    Check conversion status by job ID
    
    Args:
        job_id: Job ID from async conversion
    
    Returns:
        JSON with conversion status
    """
    try:
        media_root = Path(settings.BASE_DIR) / 'media'
        audio_dir = media_root / 'audio'
        audio_path = audio_dir / f"{job_id}.mp3"
        
        if audio_path.exists():
            file_size = os.path.getsize(audio_path)
            return JsonResponse({
                "success": True,
                "status": "completed",
                "job_id": job_id,
                "file_size": file_size,
                "download_url": f"/api/audio/download/{job_id}"
            })
        else:
            return JsonResponse({
                "success": True,
                "status": "processing",
                "job_id": job_id,
                "message": "Conversion in progress"
            })
    
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)
