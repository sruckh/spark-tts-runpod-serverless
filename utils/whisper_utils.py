"""
WhisperX utilities for word-level timing extraction
Copyright (c) 2025 SparkAudio
Licensed under the Apache License, Version 2.0

This module provides WhisperX integration for generating word-level timings
for subtitle generation.
"""

import os
import logging
import tempfile
from typing import List, Dict, Any, Union
import torch
import whisperx
import soundfile as sf

logger = logging.getLogger(__name__)


class WhisperXProcessor:
    """
    Handles WhisperX processing for word-level timing extraction.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: Union[str, torch.device] = "auto",
        compute_type: str = "float16",
    ):
        """
        Initialize WhisperX processor.

        Args:
            model_size: WhisperX model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to run on (auto, cuda, cpu, mps)
            compute_type: Computation type (float16, float32, int8)
        """
        self.model_size = model_size
        self.compute_type = compute_type

        # Determine device
        if device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "cuda"  # WhisperX uses cuda for MPS too
            else:
                self.device = "cpu"
        else:
            self.device = str(device)

        # Initialize models (lazy loading)
        self.model = None
        self.align_model = None
        self.align_metadata = None

        logger.info(f"WhisperX processor initialized: {model_size} on {self.device}")

    def _load_transcription_model(self):
        """Load the transcription model if not already loaded."""
        if self.model is None:
            try:
                logger.info(f"Loading WhisperX model: {self.model_size}")
                self.model = whisperx.load_model(
                    self.model_size, self.device, compute_type=self.compute_type
                )
                logger.info("Transcription model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load transcription model: {str(e)}")
                raise

    def _load_alignment_model(self, language: str = "en"):
        """
        Load the alignment model for word-level timestamps.

        Args:
            language: Language code for alignment model
        """
        if self.align_model is None or self.align_metadata is None:
            try:
                logger.info(f"Loading alignment model for language: {language}")
                self.align_model, self.align_metadata = whisperx.load_align_model(
                    language_code=language, device=self.device
                )
                logger.info("Alignment model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load alignment model: {str(e)}")
                raise

    def _detect_language(self, audio_path: str) -> str:
        """
        Detect the primary language in the audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            str: Detected language code
        """
        try:
            self._load_transcription_model()

            # Load audio
            audio = whisperx.load_audio(audio_path)

            # Transcribe to detect language
            result = self.model.transcribe(audio, batch_size=16)
            detected_language = result.get("language", "en")

            logger.info(f"Detected language: {detected_language}")
            return detected_language

        except Exception as e:
            logger.warning(
                f"Language detection failed, defaulting to English: {str(e)}"
            )
            return "en"

    def transcribe(self, audio_path: str, language: str = None) -> Dict[str, Any]:
        """
        Transcribe audio file without word-level alignment.

        Args:
            audio_path: Path to audio file
            language: Language code (auto-detected if None)

        Returns:
            Dict: Transcription result
        """
        try:
            self._load_transcription_model()

            # Load audio
            audio = whisperx.load_audio(audio_path)

            # Transcribe
            if language:
                result = self.model.transcribe(audio, batch_size=16, language=language)
            else:
                result = self.model.transcribe(audio, batch_size=16)

            logger.info("Transcription completed successfully")
            return result

        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise

    async def transcribe_with_timings(
        self, audio_path: str, language: str = None
    ) -> List[Dict[str, Any]]:
        """
        Transcribe audio with word-level timestamps.

        Args:
            audio_path: Path to audio file
            language: Language code (auto-detected if None)

        Returns:
            List[Dict]: Word-level timing information
        """
        try:
            # Auto-detect language if not provided
            if language is None:
                language = self._detect_language(audio_path)

            # Load models
            self._load_transcription_model()
            self._load_alignment_model(language)

            # Load audio
            audio = whisperx.load_audio(audio_path)

            # Step 1: Transcribe
            logger.info("Starting transcription...")
            result = self.model.transcribe(audio, batch_size=16, language=language)

            # Step 2: Align for word-level timestamps
            logger.info("Aligning for word-level timestamps...")
            aligned_result = whisperx.align(
                result["segments"],
                self.align_model,
                self.align_metadata,
                audio,
                self.device,
                return_char_alignments=False,
            )

            # Extract word-level timings
            word_timings = []
            for segment in aligned_result["segments"]:
                for word_info in segment.get("words", []):
                    word_timings.append(
                        {
                            "word": word_info["word"],
                            "start": word_info.get("start", 0.0),
                            "end": word_info.get("end", 0.0),
                            "score": word_info.get("score", 1.0),
                        }
                    )

            logger.info(f"Generated {len(word_timings)} word-level timestamps")
            return word_timings

        except Exception as e:
            logger.error(f"Word-level transcription failed: {str(e)}")
            raise

    def transcribe_tensor(
        self, wav_tensor: torch.Tensor, sample_rate: int = 16000, language: str = None
    ) -> List[Dict[str, Any]]:
        """
        Transcribe audio tensor with word-level timestamps.

        Args:
            wav_tensor: Audio waveform tensor
            sample_rate: Audio sample rate
            language: Language code (auto-detected if None)

        Returns:
            List[Dict]: Word-level timing information
        """
        try:
            # Save tensor to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                temp_path = tmp_file.name

            # Convert tensor to numpy and save
            if isinstance(wav_tensor, torch.Tensor):
                wav_np = wav_tensor.cpu().numpy()
            else:
                wav_np = wav_tensor

            sf.write(temp_path, wav_np, sample_rate)

            try:
                # Use the file-based method
                import asyncio

                word_timings = asyncio.run(
                    self.transcribe_with_timings(temp_path, language)
                )
                return word_timings
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Tensor transcription failed: {str(e)}")
            raise

    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported languages for alignment.

        Returns:
            List[str]: Supported language codes
        """
        # Common languages supported by WhisperX alignment
        supported_languages = [
            "en",  # English
            "zh",  # Chinese
            "es",  # Spanish
            "fr",  # French
            "de",  # German
            "ja",  # Japanese
            "ko",  # Korean
            "pt",  # Portuguese
            "it",  # Italian
            "ru",  # Russian
            "ar",  # Arabic
            "hi",  # Hindi
            "tr",  # Turkish
            "pl",  # Polish
            "nl",  # Dutch
            "sv",  # Swedish
            "da",  # Danish
            "no",  # Norwegian
            "fi",  # Finnish
        ]

        return supported_languages

    def cleanup(self):
        """Clean up loaded models to free memory."""
        if hasattr(self.model, "cpu"):
            self.model.cpu()
        if hasattr(self.align_model, "cpu"):
            self.align_model.cpu()

        self.model = None
        self.align_model = None
        self.align_metadata = None

        # Force garbage collection
        import gc

        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("WhisperX models cleaned up")


# Convenience functions
async def extract_word_timings(
    audio_path: str, language: str = None
) -> List[Dict[str, Any]]:
    """
    Extract word-level timings from audio file.

    Args:
        audio_path: Path to audio file
        language: Language code (auto-detected if None)

    Returns:
        List[Dict]: Word-level timing information
    """
    processor = WhisperXProcessor()
    try:
        return await processor.transcribe_with_timings(audio_path, language)
    finally:
        processor.cleanup()


def extract_word_timings_from_tensor(
    wav_tensor: torch.Tensor, sample_rate: int = 16000, language: str = None
) -> List[Dict[str, Any]]:
    """
    Extract word-level timings from audio tensor.

    Args:
        wav_tensor: Audio waveform tensor
        sample_rate: Audio sample rate
        language: Language code (auto-detected if None)

    Returns:
        List[Dict]: Word-level timing information
    """
    processor = WhisperXProcessor()
    try:
        return processor.transcribe_tensor(wav_tensor, sample_rate, language)
    finally:
        processor.cleanup()
