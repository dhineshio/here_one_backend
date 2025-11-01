"""
Transcribe API views for audio transcription and social media content generation
"""
from ninja import NinjaAPI, File, Form
from ninja.files import UploadedFile
from django.http import JsonResponse, FileResponse
from django.conf import settings
from pathlib import Path
from typing import Optional
import os
import uuid
from ..services.transcribe_service import TranscribeService
import logging

logger = logging.getLogger(__name__)

# Create transcribe API router
transcribe_api = NinjaAPI(urls_namespace='transcribe', version='1.0.0')


@transcribe_api.post("/transcribe")
def transcribe_audio(request, audio: UploadedFile = File(...)):
    """
    Transcribe audio/video file to text with timestamps
    
    Args:
        audio: Audio or video file upload
        language: Optional language code (e.g., 'en', 'es') - pass in form data
        translate_to_english: 'true' or 'false' - translate to English (default: false)
    
    Returns:
        JSON with transcription text (format: [0:00 - 0:05] -> text)
    """
    try:
        # Get optional parameters from request
        language = request.POST.get('language', None)
        translate_to_english = request.POST.get('translate_to_english', 'false').lower() == 'true'
        
        # Create media directories
        media_root = Path(settings.BASE_DIR) / 'media'
        uploads_dir = media_root / 'uploads'
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_ext = Path(audio.name).suffix
        file_name = f"{file_id}{file_ext}"
        file_path = uploads_dir / file_name
        
        # Save uploaded file
        with open(file_path, 'wb') as f:
            for chunk in audio.chunks():
                f.write(chunk)
        
        logger.info(f"File uploaded for transcription: {file_path}")
        
        # Transcribe
        transcription = TranscribeService.transcribe(
            audio_file_path=str(file_path),
            language=language if language else None,
            translate_to_english=translate_to_english
        )
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Check for errors
        if transcription.startswith("Error:"):
            return JsonResponse({
                "success": False,
                "error": transcription
            }, status=400)
        
        return JsonResponse({
            "success": True,
            "transcription": transcription,
            "file_id": file_id
        })
    
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        
        # Clean up on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


@transcribe_api.post("/generate-srt")
def generate_srt_file(request, audio: UploadedFile = File(...)):
    """
    Generate SRT subtitle file from audio/video
    
    Args:
        audio: Audio or video file upload
        language: Optional language code (e.g., 'en', 'es') - pass in form data
    
    Returns:
        SRT file download
    """
    try:
        # Get optional language parameter from request
        language = request.POST.get('language', None)
        
        # Create media directories
        media_root = Path(settings.BASE_DIR) / 'media'
        uploads_dir = media_root / 'uploads'
        srt_dir = media_root / 'srt'
        uploads_dir.mkdir(parents=True, exist_ok=True)
        srt_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_ext = Path(audio.name).suffix
        file_name = f"{file_id}{file_ext}"
        file_path = uploads_dir / file_name
        
        # Save uploaded file
        with open(file_path, 'wb') as f:
            for chunk in audio.chunks():
                f.write(chunk)
        
        logger.info(f"File uploaded for SRT generation: {file_path}")
        
        # Generate SRT
        srt_filename = f"{file_id}.srt"
        srt_path = srt_dir / srt_filename
        
        result = TranscribeService.generate_srt(
            audio_file_path=str(file_path),
            output_srt_path=str(srt_path),
            language=language if language else None
        )
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Check for errors
        if result.startswith("Error:"):
            return JsonResponse({
                "success": False,
                "error": result
            }, status=400)
        
        # Return SRT file
        response = FileResponse(
            open(srt_path, 'rb'),
            content_type='application/x-subrip',
            as_attachment=True,
            filename=f"subtitles_{file_id}.srt"
        )
        
        return response
    
    except Exception as e:
        logger.error(f"SRT generation error: {str(e)}")
        
        # Clean up on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)


@transcribe_api.post("/social-media-content")
def generate_social_media_content(request, audio: UploadedFile = File(...)):
    """
    Generate social media content (caption, description, hashtags) from audio/video
    Always translates to English for better social media reach
    
    Args:
        audio: Audio or video file upload
        language: Optional language code (e.g., 'en', 'es') - pass in form data
    
    Returns:
        JSON with caption, description, hashtags for Instagram, Facebook, YouTube
    """
    try:
        # Get optional language parameter from request
        language = request.POST.get('language', None)
        
        # Create media directories
        media_root = Path(settings.BASE_DIR) / 'media'
        uploads_dir = media_root / 'uploads'
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_ext = Path(audio.name).suffix
        file_name = f"{file_id}{file_ext}"
        file_path = uploads_dir / file_name
        
        # Save uploaded file
        with open(file_path, 'wb') as f:
            for chunk in audio.chunks():
                f.write(chunk)
        
        logger.info(f"File uploaded for social media content generation: {file_path}")
        
        # Generate content (always translates to English)
        result = TranscribeService.generate_social_media_content(
            audio_file_path=str(file_path),
            language=language if language else None
        )
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Check for errors
        if "error" in result:
            return JsonResponse({
                "success": False,
                "error": result.get("error", "Unknown error")
            }, status=400)
        
        return JsonResponse({
            "success": True,
            "file_id": file_id,
            "transcription": result.get("transcription", ""),
            "caption": result.get("caption", ""),
            "description": result.get("description", ""),
            "hashtags": result.get("hashtags", ""),
            "instagram": result.get("instagram", {}),
            "facebook": result.get("facebook", {}),
            "youtube": result.get("youtube", {})
        })
    
    except Exception as e:
        logger.error(f"Social media content generation error: {str(e)}")
        
        # Clean up on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)
