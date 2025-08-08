"""
Utilities package for Spark-TTS RunPod serverless
Copyright (c) 2025 SparkAudio
Licensed under the Apache License, Version 2.0
"""

__version__ = "1.0.0"
__author__ = "SparkAudio"
__license__ = "Apache-2.0"

from .s3_utils import S3Manager, download_voice_sample, upload_generated_audio, cleanup_old_files
from .whisper_utils import WhisperXProcessor, extract_word_timings, extract_word_timings_from_tensor
from .ass_utils import ASSGenerator, generate_ass_subtitles, validate_ass_file

__all__ = [
    "S3Manager",
    "download_voice_sample", 
    "upload_generated_audio",
    "cleanup_old_files",
    "WhisperXProcessor",
    "extract_word_timings",
    "extract_word_timings_from_tensor", 
    "ASSGenerator",
    "generate_ass_subtitles",
    "validate_ass_file"
]