#!/usr/bin/env python3
"""
Runpod Serverless Handler for Spark-TTS
Supports all CLI parameters with S3 integration
"""

import os
import sys
import json
import torch
import soundfile as sf
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import boto3
from botocore.exceptions import NoCredentialsError
import runpod

# Add project root to path
sys.path.append('/runpod-volume/SparkTTS-serverless')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cli.SparkTTS import SparkTTS
from s3_utils import S3Handler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for model persistence
spark_tts_model = None
s3_handler = None
VOLUME_PATH = "/runpod-volume/SparkTTS-serverless"
MODEL_PATH = f"{VOLUME_PATH}/models/Spark-TTS-0.5B"

def initialize_models():
    """Initialize models eagerly (no lazy loading)"""
    global spark_tts_model, s3_handler
    
    logger.info("Initializing Spark-TTS models...")
    
    # Initialize S3 handler with optional custom endpoint URL for Backblaze B2
    s3_handler = S3Handler(
        bucket_name=os.environ.get('S3_BUCKET_NAME'),
        access_key=os.environ.get('AWS_ACCESS_KEY_ID'),
        secret_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region=os.environ.get('AWS_REGION', 'us-east-1'),
        endpoint_url=os.environ.get('AWS_ENDPOINT_URL')  # For Backblaze B2 or other S3-compatible services
    )
    
    # Check if models exist on volume
    if not os.path.exists(MODEL_PATH):
        logger.info(f"Models not found at {MODEL_PATH}, downloading...")
        download_models()
    
    # Initialize Spark-TTS
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    spark_tts_model = SparkTTS(Path(MODEL_PATH), device=device)
    logger.info("Models initialized successfully")

def download_models():
    """Download models to volume if not present"""
    os.makedirs(MODEL_PATH, exist_ok=True)
    
    # Download from HuggingFace or S3
    # This would be implemented based on your model storage strategy
    from huggingface_hub import snapshot_download
    
    try:
        snapshot_download(
            repo_id="SparkAudio/Spark-TTS-0.5B",
            local_dir=MODEL_PATH,
            local_dir_use_symlinks=False
        )
        logger.info("Models downloaded successfully")
    except Exception as e:
        logger.error(f"Failed to download models: {e}")
        raise

def handler(job):
    """
    Main handler for Runpod Serverless
    Supports all CLI inference parameters
    """
    try:
        job_input = job['input']
        
        # Extract parameters (matching cli/inference.py)
        text = job_input.get('text')
        if not text:
            return {"error": "Text parameter is required"}
        
        # Optional parameters with defaults
        prompt_text = job_input.get('prompt_text')
        prompt_speech_url = job_input.get('prompt_speech_url')  # S3 URL for reference audio
        output_name = job_input.get('output_name', 'output')
        speaker_gender = job_input.get('speaker_gender', 'male')
        pitch_shift = job_input.get('pitch_shift', 0.0)
        speed_shift = job_input.get('speed_shift', 1.0)
        multi_sentence_gap = job_input.get('multi_sentence_gap', 0.3)
        task_token = job_input.get('task_token', 'zero_shot')
        temperature = job_input.get('temperature', 0.7)
        top_p = job_input.get('top_p', 0.95)
        max_length = job_input.get('max_length', 4096)
        enable_whisperx = job_input.get('enable_whisperx', False)
        enable_subtitles = job_input.get('enable_subtitles', False)
        
        # Handle reference audio from S3
        prompt_speech_16k = None
        if prompt_speech_url:
            logger.info(f"Downloading reference audio from: {prompt_speech_url}")
            local_ref_path = f"/tmp/ref_audio_{job['id']}.wav"
            s3_handler.download_file(prompt_speech_url, local_ref_path)
            
            # Load and process reference audio
            import torchaudio
            waveform, sample_rate = torchaudio.load(local_ref_path)
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)
            prompt_speech_16k = waveform.squeeze().numpy()
            
            # Clean up temp file
            os.remove(local_ref_path)
        
        # Generate speech
        logger.info(f"Generating speech for text: {text[:50]}...")
        audio_data = spark_tts_model.generate(
            text=text,
            prompt_text=prompt_text,
            prompt_speech_16k=prompt_speech_16k,
            speaker_gender=speaker_gender,
            pitch_shift=pitch_shift,
            speed_shift=speed_shift,
            multi_sentence_gap=multi_sentence_gap,
            task_token=task_token,
            temperature=temperature,
            top_p=top_p,
            max_length=max_length
        )
        
        # Save audio to temp file
        temp_output_path = f"/tmp/{output_name}_{job['id']}.wav"
        sf.write(temp_output_path, audio_data, spark_tts_model.sample_rate)
        
        # Process with WhisperX if requested
        word_timings = None
        if enable_whisperx:
            logger.info("Generating word-level timings with WhisperX...")
            word_timings = generate_word_timings(temp_output_path)
        
        # Generate subtitles if requested
        subtitles_url = None
        if enable_subtitles and word_timings:
            logger.info("Generating subtitles...")
            subtitles_path = generate_subtitles(word_timings, output_name, job['id'])
            subtitles_url = s3_handler.upload_file(
                subtitles_path,
                f"output/subtitles/{output_name}_{job['id']}.ass"
            )
            os.remove(subtitles_path)
        
        # Upload audio to S3
        audio_url = s3_handler.upload_file(
            temp_output_path,
            f"output/{output_name}_{job['id']}.wav"
        )
        
        # Clean up temp file
        os.remove(temp_output_path)
        
        # Prepare response
        response = {
            "status": "success",
            "audio_url": audio_url,
            "sample_rate": spark_tts_model.sample_rate,
            "duration": len(audio_data) / spark_tts_model.sample_rate
        }
        
        if word_timings:
            response["word_timings"] = word_timings
        
        if subtitles_url:
            response["subtitles_url"] = subtitles_url
        
        logger.info("Speech generation completed successfully")
        return response
        
    except Exception as e:
        logger.error(f"Error in handler: {str(e)}")
        return {"error": str(e)}

def generate_word_timings(audio_path):
    """Generate word-level timings using WhisperX"""
    try:
        import whisperx
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        batch_size = 16
        compute_type = "float16" if device == "cuda" else "int8"
        
        # Load model
        model = whisperx.load_model("large-v2", device, compute_type=compute_type)
        
        # Transcribe
        audio = whisperx.load_audio(audio_path)
        result = model.transcribe(audio, batch_size=batch_size)
        
        # Align
        model_a, metadata = whisperx.load_align_model(
            language_code=result["language"], device=device
        )
        result = whisperx.align(
            result["segments"], model_a, metadata, audio, device,
            return_char_alignments=False
        )
        
        return result["segments"]
        
    except Exception as e:
        logger.error(f"WhisperX processing failed: {e}")
        return None

def generate_subtitles(word_timings, output_name, job_id):
    """Generate ASS subtitles from word timings"""
    try:
        import ass
        
        # Create ASS document
        doc = ass.Document()
        doc.styles.append(ass.Style(
            name="Default",
            fontname="Arial",
            fontsize=20,
            primary_color=ass.Color(255, 255, 255),
            secondary_color=ass.Color(255, 0, 0),
            outline_color=ass.Color(0, 0, 0),
            back_color=ass.Color(0, 0, 0, 128),
            bold=False,
            italic=False,
            underline=False,
            strike_out=False,
            scale_x=100.0,
            scale_y=100.0,
            spacing=0.0,
            angle=0.0,
            border_style=1,
            outline=2.0,
            shadow=1.0,
            alignment=2,
            margin_l=10,
            margin_r=10,
            margin_v=10,
            encoding=1
        ))
        
        # Add events from word timings
        for segment in word_timings:
            start_time = int(segment['start'] * 1000)
            end_time = int(segment['end'] * 1000)
            text = segment['text'].strip()
            
            doc.events.append(ass.Dialogue(
                layer=0,
                start=start_time,
                end=end_time,
                style="Default",
                text=text
            ))
        
        # Save to file
        output_path = f"/tmp/{output_name}_{job_id}.ass"
        with open(output_path, "w", encoding='utf-8') as f:
            doc.dump_file(f)
        
        return output_path
        
    except Exception as e:
        logger.error(f"Subtitle generation failed: {e}")
        return None

# Initialize models on startup
initialize_models()

# Runpod serverless handler
runpod.serverless.start({
    "handler": handler
})