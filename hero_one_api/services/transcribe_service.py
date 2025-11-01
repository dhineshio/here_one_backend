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
    def generate_social_media_content(
        audio_file_path: str, 
        language: Optional[str] = None,
        caption_length: str = 'medium',
        description_length: str = 'medium',
        hashtag_count: int = 15
    ) -> dict:
        """
        Generate social media content (caption, description, hashtags) from audio/video
        Always translates to English for better social media reach
        
        Args:
            audio_file_path: Path to audio or video file
            language: Language code like 'en', 'es' (auto-detect if None)
            caption_length: 'short' (1 sentence), 'medium' (2 sentences), 'long' (3 sentences)
            description_length: 'short' (1 paragraph), 'medium' (2-3 paragraphs), 'long' (4-5 paragraphs)
            hashtag_count: Number of hashtags to generate (5-30, default: 15)
            
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
            
            # Define caption length requirements
            caption_requirements = {
                'short': '1 sentence (concise and punchy)',
                'medium': '2 sentences (engaging with hook)',
                'long': '3 sentences (detailed with strong hook)'
            }
            
            # Define description length requirements
            description_requirements = {
                'short': '1 paragraph (brief overview)',
                'medium': '2-3 paragraphs (detailed explanation)',
                'long': '4-5 paragraphs (comprehensive and detailed)'
            }
            
            caption_req = caption_requirements.get(caption_length, caption_requirements['medium'])
            description_req = description_requirements.get(description_length, description_requirements['medium'])
            
            # Validate and set hashtag count
            hashtag_count = max(5, min(30, hashtag_count))  # Ensure between 5 and 30
            
            # Create prompt for social media content generation
            prompt = f"""Based on this video transcription, generate social media content for Instagram, Facebook, and YouTube:

                Transcription:
                {transcription}

                Please provide:
                1. A hook-style caption ({caption_req}, written like a hook that grabs attention and creates curiosity. Use attention-grabbing phrases, emojis, and make people want to watch)
                2. A detailed description ({description_req} explaining the video content)
                3. Exactly {hashtag_count} trending hashtags relevant to the content

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
