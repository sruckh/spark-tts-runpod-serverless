#!/usr/bin/env python3
"""
RunPod Serverless Handler for Spark-TTS
Copyright (c) 2025 SparkAudio
Licensed under the Apache License, Version 2.0

This module provides a RunPod serverless wrapper around the Spark-TTS model
for text-to-speech generation with voice cloning capabilities.
"""

import os
import sys
import json
import logging
import tempfile
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

import torch
import soundfile as sf
import boto3
from botocore.exceptions import ClientError

# Add project root to path for imports
sys.path.insert(0, '/runpod-volume/Spark-TTS')

from cli.SparkTTS import SparkTTS
from utils.s3_utils import S3Manager
from utils.whisper_utils import WhisperXProcessor
from utils.ass_utils import ASSGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for model caching
MODEL_INSTANCE = None
MODEL_DIR = "/runpod-volume/Spark-TTS/pretrained_models/Spark-TTS-0.5B"
S3_MANAGER = None
WHISPERX_PROCESSOR = None


def get_device() -> torch.device:
    """
    Get the best available device (CUDA, MPS, or CPU).
    
    Returns:
        torch.device: The selected device
    """
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        logger.info(f"Using CUDA device: {device}")
        return device
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device("mps:0")
        logger.info(f"Using MPS device: {device}")
        return device
    else:
        device = torch.device("cpu")
        logger.info("Using CPU device")
        return device


def initialize_model() -> SparkTTS:
    """
    Initialize the SparkTTS model instance.
    
    Returns:
        SparkTTS: Initialized model instance
        
    Raises:
        Exception: If model initialization fails
    """
    global MODEL_INSTANCE
    
    if MODEL_INSTANCE is None:
        try:
            device = get_device()
            logger.info(f"Initializing SparkTTS model from: {MODEL_DIR}")
            
            if not os.path.exists(MODEL_DIR):
                raise FileNotFoundError(f"Model directory not found: {MODEL_DIR}")
                
            MODEL_INSTANCE = SparkTTS(MODEL_DIR, device)
            logger.info("Model initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize model: {str(e)}")
            logger.error(traceback.format_exc())
            raise
            
    return MODEL_INSTANCE


def initialize_s3_manager() -> S3Manager:
    """
    Initialize S3 manager for file operations.
    
    Returns:
        S3Manager: Initialized S3 manager
    """
    global S3_MANAGER
    
    if S3_MANAGER is None:
        try:
            S3_MANAGER = S3Manager()
            logger.info("S3 manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize S3 manager: {str(e)}")
            raise
            
    return S3_MANAGER


def initialize_whisperx() -> WhisperXProcessor:
    """
    Initialize WhisperX processor for word-level timings.
    
    Returns:
        WhisperXProcessor: Initialized WhisperX processor
    """
    global WHISPERX_PROCESSOR
    
    if WHISPERX_PROCESSOR is None:
        try:
            device = get_device()
            WHISPERX_PROCESSOR = WhisperXProcessor(device=device)
            logger.info("WhisperX processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WhisperX: {str(e)}")
            raise
            
    return WHISPERX_PROCESSOR


def validate_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize job input parameters.
    
    Args:
        job_input: Raw job input from RunPod
        
    Returns:
        Dict[str, Any]: Validated parameters
        
    Raises:
        ValueError: If validation fails
    """
    # Required parameters
    if 'text' not in job_input or not job_input['text'].strip():
        raise ValueError("Parameter 'text' is required and cannot be empty")
    
    # Validate gender if provided
    if 'gender' in job_input:
        valid_genders = ['male', 'female']
        if job_input['gender'] not in valid_genders:
            raise ValueError(f"Invalid gender. Must be one of: {valid_genders}")
    
    # Validate pitch if provided
    if 'pitch' in job_input:
        valid_pitches = ['very_low', 'low', 'moderate', 'high', 'very_high']
        if job_input['pitch'] not in valid_pitches:
            raise ValueError(f"Invalid pitch. Must be one of: {valid_pitches}")
    
    # Validate speed if provided
    if 'speed' in job_input:
        valid_speeds = ['very_low', 'low', 'moderate', 'high', 'very_high']
        if job_input['speed'] not in valid_speeds:
            raise ValueError(f"Invalid speed. Must be one of: {valid_speeds}")
    
    # Validate voice cloning parameters
    if 'prompt_speech_url' in job_input and 'gender' in job_input:
        raise ValueError("Cannot specify both prompt_speech_url (voice cloning) and gender (controllable TTS)")
    
    if 'prompt_speech_url' not in job_input and 'gender' not in job_input:
        raise ValueError("Must specify either prompt_speech_url for voice cloning or gender for controllable TTS")
    
    # Validate generation parameters
    validated = {
        'text': job_input['text'].strip(),
        'prompt_text': job_input.get('prompt_text', '').strip() or None,
        'prompt_speech_url': job_input.get('prompt_speech_url', '').strip() or None,
        'gender': job_input.get('gender'),
        'pitch': job_input.get('pitch'),
        'speed': job_input.get('speed'),
        'temperature': float(job_input.get('temperature', 0.8)),
        'top_k': int(job_input.get('top_k', 50)),
        'top_p': float(job_input.get('top_p', 0.95)),
        'generate_subtitles': job_input.get('generate_subtitles', False),
        'output_format': job_input.get('output_format', 'wav').lower()
    }
    
    # Validate temperature range
    if not 0.1 <= validated['temperature'] <= 2.0:
        raise ValueError("Temperature must be between 0.1 and 2.0")
    
    # Validate top_k range
    if not 1 <= validated['top_k'] <= 100:
        raise ValueError("top_k must be between 1 and 100")
    
    # Validate top_p range
    if not 0.1 <= validated['top_p'] <= 1.0:
        raise ValueError("top_p must be between 0.1 and 1.0")
    
    # Validate output format
    valid_formats = ['wav', 'mp3', 'flac']
    if validated['output_format'] not in valid_formats:
        raise ValueError(f"Invalid output_format. Must be one of: {valid_formats}")
    
    return validated


async def download_voice_file(s3_manager: S3Manager, voice_url: str) -> str:
    """
    Download voice reference file from S3.
    
    Args:
        s3_manager: S3 manager instance
        voice_url: Pre-signed URL or S3 path
        
    Returns:
        str: Local path to downloaded file
        
    Raises:
        Exception: If download fails
    """
    try:
        # Create temporary file for the voice sample
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            tmp_path = tmp_file.name
        
        # Download from S3
        await s3_manager.download_file(voice_url, tmp_path)
        
        logger.info(f"Downloaded voice file to: {tmp_path}")
        return tmp_path
        
    except Exception as e:
        logger.error(f"Failed to download voice file from {voice_url}: {str(e)}")
        raise


async def upload_output_file(s3_manager: S3Manager, local_path: str, filename: str) -> str:
    """
    Upload generated audio file to S3.
    
    Args:
        s3_manager: S3 manager instance
        local_path: Local path to the file
        filename: Target filename in S3
        
    Returns:
        str: Pre-signed URL for the uploaded file
        
    Raises:
        Exception: If upload fails
    """
    try:
        s3_key = f"output/{filename}"
        presigned_url = await s3_manager.upload_file(local_path, s3_key)
        
        logger.info(f"Uploaded output file: {s3_key}")
        return presigned_url
        
    except Exception as e:
        logger.error(f"Failed to upload output file: {str(e)}")
        raise


def generate_audio(model: SparkTTS, params: Dict[str, Any], prompt_speech_path: Optional[str] = None) -> torch.Tensor:
    """
    Generate audio using the SparkTTS model.
    
    Args:
        model: SparkTTS model instance
        params: Validated parameters
        prompt_speech_path: Path to prompt audio file (if using voice cloning)
        
    Returns:
        torch.Tensor: Generated waveform
        
    Raises:
        Exception: If generation fails
    """
    try:
        logger.info("Starting TTS generation...")
        
        with torch.no_grad():
            wav = model.inference(
                text=params['text'],
                prompt_speech_path=prompt_speech_path,
                prompt_text=params['prompt_text'],
                gender=params['gender'],
                pitch=params['pitch'],
                speed=params['speed'],
                temperature=params['temperature'],
                top_k=params['top_k'],
                top_p=params['top_p']
            )
        
        logger.info("TTS generation completed successfully")
        return wav
        
    except Exception as e:
        logger.error(f"Failed to generate audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def save_audio_file(wav: torch.Tensor, output_path: str, sample_rate: int = 16000, output_format: str = 'wav') -> None:
    """
    Save generated waveform to file.
    
    Args:
        wav: Generated waveform tensor
        output_path: Path to save the file
        sample_rate: Audio sample rate
        output_format: Output audio format
        
    Raises:
        Exception: If saving fails
    """
    try:
        # Convert tensor to numpy if needed
        if isinstance(wav, torch.Tensor):
            wav_np = wav.cpu().numpy()
        else:
            wav_np = wav
        
        # Save with soundfile
        if output_format == 'wav':
            sf.write(output_path, wav_np, sample_rate, format='WAV')
        elif output_format == 'mp3':
            sf.write(output_path, wav_np, sample_rate, format='MP3')
        elif output_format == 'flac':
            sf.write(output_path, wav_np, sample_rate, format='FLAC')
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        logger.info(f"Audio saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to save audio file: {str(e)}")
        raise


async def handler(job):
    """
    Main RunPod serverless handler function.
    
    Args:
        job: RunPod job object containing input parameters
        
    Returns:
        Dict[str, Any]: Job result with output URLs and metadata
    """
    job_input = job.get("input", {})
    logger.info(f"Received job input: {json.dumps(job_input, indent=2)}")
    
    # Temporary file paths to clean up
    temp_files = []
    
    try:
        # Validate input parameters
        params = validate_input(job_input)
        logger.info("Input validation passed")
        
        # Initialize components
        model = initialize_model()
        s3_manager = initialize_s3_manager()
        
        # Handle voice cloning if prompt speech is provided
        prompt_speech_path = None
        if params['prompt_speech_url']:
            prompt_speech_path = await download_voice_file(s3_manager, params['prompt_speech_url'])
            temp_files.append(prompt_speech_path)
        
        # Generate audio
        wav = generate_audio(model, params, prompt_speech_path)
        
        # Create output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"sparktts_{timestamp}.{params['output_format']}"
        
        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{params['output_format']}") as tmp_file:
            temp_audio_path = tmp_file.name
        temp_files.append(temp_audio_path)
        
        save_audio_file(wav, temp_audio_path, model.sample_rate, params['output_format'])
        
        # Upload to S3
        audio_url = await upload_output_file(s3_manager, temp_audio_path, output_filename)
        
        # Prepare response
        result = {
            "audio_url": audio_url,
            "filename": output_filename,
            "duration_seconds": len(wav) / model.sample_rate,
            "sample_rate": model.sample_rate,
            "format": params['output_format'],
            "generation_params": {
                "text": params['text'],
                "temperature": params['temperature'],
                "top_k": params['top_k'],
                "top_p": params['top_p']
            }
        }
        
        # Generate subtitles if requested
        if params['generate_subtitles'] and prompt_speech_path:
            try:
                whisperx = initialize_whisperx()
                
                # Generate word-level timings
                word_timings = await whisperx.transcribe_with_timings(temp_audio_path)
                
                # Generate ASS subtitles
                ass_generator = ASSGenerator()
                ass_content = ass_generator.generate(params['text'], word_timings)
                
                # Save ASS file
                ass_filename = f"sparktts_{timestamp}.ass"
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ass') as ass_file:
                    ass_file.write(ass_content)
                    temp_ass_path = ass_file.name
                temp_files.append(temp_ass_path)
                
                # Upload ASS file
                ass_url = await upload_output_file(s3_manager, temp_ass_path, ass_filename)
                
                result["subtitle_url"] = ass_url
                result["subtitle_format"] = "ass"
                result["word_timings"] = word_timings
                
                logger.info("Subtitles generated successfully")
                
            except Exception as e:
                logger.error(f"Failed to generate subtitles: {str(e)}")
                result["subtitle_error"] = str(e)
        
        logger.info("Job completed successfully")
        return result
        
    except Exception as e:
        error_msg = f"Job failed: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        return {"error": error_msg, "traceback": traceback.format_exc()}
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {str(e)}")


def runpod_handler(job):
    """
    Synchronous wrapper for the async handler function.
    
    Args:
        job: RunPod job object
        
    Returns:
        Dict[str, Any]: Job result
    """
    import asyncio
    
    try:
        # Run the async handler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(handler(job))
        loop.close()
        return result
        
    except Exception as e:
        logger.error(f"Handler wrapper failed: {str(e)}")
        return {"error": str(e)}


if __name__ == "__main__":
    # Test the handler locally
    import runpod
    
    # Set up test job
    test_job = {
        "input": {
            "text": "Hello, this is a test of the Spark TTS system.",
            "gender": "female",
            "pitch": "moderate",
            "speed": "moderate",
            "temperature": 0.8,
            "top_k": 50,
            "top_p": 0.95,
            "output_format": "wav",
            "generate_subtitles": False
        }
    }
    
    print("Running test...")
    result = runpod_handler(test_job)
    print(f"Result: {json.dumps(result, indent=2)}")
    
    # Start RunPod serverless
    runpod.serverless.start({"handler": runpod_handler})