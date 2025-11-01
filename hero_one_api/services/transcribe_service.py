"""
Simple transcription service using OpenAI Whisper API
"""
import os
import logging
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class TranscribeService:
    """Simple service for audio transcription using OpenAI Whisper API"""
    
    @staticmethod
    def format_srt_timestamp(seconds: float) -> str:
        """
        Format seconds to SRT timestamp format: HH:MM:SS,mmm
        
        Args:
            seconds: Time in seconds
            
        Returns:
            SRT formatted timestamp like "00:00:05,500"
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
    
    @staticmethod
    def transcribe(audio_file_path: str, language: Optional[str] = None, translate_to_english: bool = False) -> str:
        """
        Transcribe audio/video file to text with timestamps
        
        Args:
            audio_file_path: Path to audio or video file (mp3, mp4, wav, etc.)
            language: Language code like 'en', 'es' (auto-detect if None)
            translate_to_english: If True, translates to English instead of transcribing
            
        Returns:
            Formatted transcription like "[0:00 - 0:05] -> hello world"
        """
        try:
            if not os.path.exists(audio_file_path):
                return f"Error: File not found - {audio_file_path}"
            
            # Initialize OpenAI client (uses OPENAI_API_KEY from env)
            client = OpenAI()
            
            # Choose between transcription or translation
            if translate_to_english:
                # Translation: Translates any language to English
                with open(audio_file_path, 'rb') as audio_file:
                    result = client.audio.translations.create(
                        model='whisper-1',
                        file=audio_file,
                        response_format='verbose_json'
                    )
            else:
                # Transcription: Same language as input
                with open(audio_file_path, 'rb') as audio_file:
                    params = {
                        'model': 'whisper-1',
                        'file': audio_file,
                        'response_format': 'verbose_json',
                        'timestamp_granularities': ['segment']
                    }
                    
                    if language:
                        params['language'] = language
                    
                    result = client.audio.transcriptions.create(**params)
            
            # Format output: [00:00 - 00:15] -> text
            output_lines = []
            
            if hasattr(result, 'segments') and result.segments:
                for segment in result.segments:
                    # Access segment attributes directly (not as dict)
                    start = segment.start if hasattr(segment, 'start') else segment.get('start', 0)
                    end = segment.end if hasattr(segment, 'end') else segment.get('end', 0)
                    text = segment.text.strip() if hasattr(segment, 'text') else segment.get('text', '').strip()
                    
                    # Format time as MM:SS
                    start_min = int(start // 60)
                    start_sec = int(start % 60)
                    end_min = int(end // 60)
                    end_sec = int(end % 60)
                    
                    timestamp = f"[{start_min}:{start_sec:02d} - {end_min}:{end_sec:02d}]"
                    output_lines.append(f"{timestamp} -> {text}")
            else:
                # Fallback if no segments
                output_lines.append(result.text)
            
            return "\n".join(output_lines)
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def generate_srt(audio_file_path: str, output_srt_path: str, language: Optional[str] = None) -> str:
        """
        Generate SRT subtitle file from audio/video
        
        Args:
            audio_file_path: Path to audio or video file (mp3, mp4, wav, etc.)
            output_srt_path: Path where to save the SRT file
            language: Language code like 'en', 'es' (auto-detect if None)
            
        Returns:
            Success message or error string
        """
        try:
            if not os.path.exists(audio_file_path):
                return f"Error: File not found - {audio_file_path}"
            
            # Initialize OpenAI client (uses OPENAI_API_KEY from env)
            client = OpenAI()
            
            # Transcribe with timestamps
            with open(audio_file_path, 'rb') as audio_file:
                params = {
                    'model': 'whisper-1',
                    'file': audio_file,
                    'response_format': 'verbose_json',
                    'timestamp_granularities': ['segment']
                }
                
                if language:
                    params['language'] = language
                
                result = client.audio.transcriptions.create(**params)
            
            # Generate SRT content
            srt_lines = []
            
            if hasattr(result, 'segments') and result.segments:
                for index, segment in enumerate(result.segments, start=1):
                    # Access segment attributes directly (not as dict)
                    start = segment.start if hasattr(segment, 'start') else segment.get('start', 0)
                    end = segment.end if hasattr(segment, 'end') else segment.get('end', 0)
                    text = segment.text.strip() if hasattr(segment, 'text') else segment.get('text', '').strip()
                    
                    # SRT format:
                    # 1
                    # 00:00:00,000 --> 00:00:05,000
                    # Text content
                    # (blank line)
                    
                    srt_lines.append(str(index))
                    srt_lines.append(f"{TranscribeService.format_srt_timestamp(start)} --> {TranscribeService.format_srt_timestamp(end)}")
                    srt_lines.append(text)
                    srt_lines.append("")  # Blank line between subtitles
            else:
                # Fallback if no segments
                return "Error: No segments found in transcription"
            
            # Write to SRT file
            with open(output_srt_path, 'w', encoding='utf-8') as srt_file:
                srt_file.write("\n".join(srt_lines))
            
            logger.info(f"SRT file generated: {output_srt_path}")
            return f"Success: SRT file saved to {output_srt_path}"
            
        except Exception as e:
            logger.error(f"SRT generation failed: {str(e)}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def generate_social_media_content(audio_file_path: str, language: Optional[str] = None) -> dict:
        """
        Generate social media content (caption, description, hashtags) from audio/video
        Always translates to English for better social media reach
        
        Args:
            audio_file_path: Path to audio or video file
            language: Language code like 'en', 'es' (auto-detect if None)
            
        Returns:
            Dict with caption, description, hashtags for Instagram, Facebook, YouTube
        """
        try:
            # Always translate to English for social media content
            transcription = TranscribeService.transcribe(audio_file_path, language, translate_to_english=True)
            
            if transcription.startswith("Error:"):
                return {"error": transcription}
            
            # Initialize OpenAI client
            client = OpenAI()
            
            # Create prompt for social media content generation
            prompt = f"""Based on this video transcription, generate social media content for Instagram, Facebook, and YouTube:

                Transcription:
                {transcription}

                Please provide:
                1. A hook-style caption (1-2 sentences, written like a hook that grabs attention and creates curiosity. Use attention-grabbing phrases, emojis, and make people want to watch)
                2. A detailed description (2-3 paragraphs explaining the video content)
                3. 10-15 trending hashtags relevant to the content

                Format the response as:

                CAPTION:
                [Your hook-style attention-grabbing caption here with emojis]

                DESCRIPTION:
                [Your detailed description here]

                HASHTAGS:
                [Your hashtags separated by spaces, like: #trending #video #content]
            """
            
            # Call OpenAI API for content generation
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a social media expert who creates engaging captions, descriptions, and trending hashtags for video content. Make content suitable for Instagram, Facebook, and YouTube."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse the response
            content = response.choices[0].message.content
            
            # Extract caption, description, and hashtags
            caption = ""
            description = ""
            hashtags = ""
            
            if "CAPTION:" in content:
                caption_part = content.split("CAPTION:")[1].split("DESCRIPTION:")[0].strip()
                caption = caption_part
            
            if "DESCRIPTION:" in content:
                desc_part = content.split("DESCRIPTION:")[1].split("HASHTAGS:")[0].strip()
                description = desc_part
            
            if "HASHTAGS:" in content:
                hashtags_part = content.split("HASHTAGS:")[1].strip()
                hashtags = hashtags_part
            
            result = {
                "transcription": transcription,
                "caption": caption,
                "description": description,
                "hashtags": hashtags,
                "instagram": {
                    "caption": f"{caption}\n\n{hashtags}",
                    "description": description
                },
                "facebook": {
                    "caption": caption,
                    "description": f"{description}\n\n{hashtags}"
                },
                "youtube": {
                    "title": caption,
                    "description": f"{description}\n\n{hashtags}",
                    "tags": [tag.strip().replace('#', '') for tag in hashtags.split() if tag.startswith('#')]
                }
            }
            
            logger.info(f"Social media content generated for: {audio_file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Social media content generation failed: {str(e)}")
            return {"error": f"Error: {str(e)}"}
