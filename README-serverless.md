# Spark-TTS RunPod Serverless

[![Build Status](https://github.com/sruckh/spark-tts-runpod-serverless/workflows/Build%20and%20Deploy%20to%20DockerHub/badge.svg)](https://github.com/sruckh/spark-tts-runpod-serverless/actions)
[![Docker Pulls](https://img.shields.io/docker/pulls/gemneye/spark-tts-runpod-serverless)](https://hub.docker.com/r/gemneye/spark-tts-runpod-serverless)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

A RunPod serverless implementation of Spark-TTS for high-quality text-to-speech generation with voice cloning capabilities.

## Features

- 🎤 **Zero-shot Voice Cloning**: Clone any voice with just a reference audio sample
- 🎛️ **Controllable TTS**: Control gender, pitch, and speed without reference audio
- 🌍 **Multilingual Support**: Built-in support for Chinese and English
- ⏱️ **Word-level Timing**: Generate precise word-level timestamps using WhisperX
- 📝 **Advanced Subtitles**: Create ASS (Advanced SubStation Alpha) subtitles with karaoke effects
- ☁️ **S3 Integration**: Seamless file storage with pre-signed URLs
- 🐳 **Production Ready**: Optimized Docker container with proper error handling
- 🚀 **RunPod Optimized**: Built specifically for RunPod serverless platform

## Quick Start

### 1. Deploy to RunPod

```bash
# Use the pre-built Docker image
docker pull gemneye/spark-tts-runpod-serverless:latest
```

Deploy this image as a RunPod serverless endpoint with the following environment variables:

- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key  
- `AWS_REGION`: AWS region (e.g., `us-east-1`)
- `S3_BUCKET_NAME`: S3 bucket for voice files and outputs

### 2. API Usage

#### Voice Cloning Example

```python
import requests

# Voice cloning with reference audio
payload = {
    "input": {
        "text": "Hello, this is a test of voice cloning with Spark-TTS!",
        "prompt_speech_url": "https://your-bucket.s3.amazonaws.com/voices/reference.wav",
        "prompt_text": "This is the transcript of the reference audio",
        "temperature": 0.8,
        "top_k": 50,
        "top_p": 0.95,
        "output_format": "wav",
        "generate_subtitles": True
    }
}

response = requests.post("https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync", 
                        json=payload,
                        headers={"Authorization": "Bearer YOUR_API_KEY"})

result = response.json()
print(f"Generated audio: {result['output']['audio_url']}")
print(f"Subtitles: {result['output']['subtitle_url']}")
```

#### Controllable TTS Example

```python
# Controllable TTS without reference audio
payload = {
    "input": {
        "text": "Hello, this is controllable text-to-speech generation!",
        "gender": "female",
        "pitch": "moderate", 
        "speed": "moderate",
        "temperature": 0.8,
        "output_format": "wav"
    }
}

response = requests.post("https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync",
                        json=payload,
                        headers={"Authorization": "Bearer YOUR_API_KEY"})
```

## API Parameters

### Required Parameters

- `text` (string): Text to convert to speech

### Voice Cloning Parameters (Option 1)

- `prompt_speech_url` (string): Pre-signed URL to reference audio file
- `prompt_text` (string, optional): Transcript of reference audio for better quality

### Controllable TTS Parameters (Option 2)

- `gender` (string): `"male"` or `"female"`
- `pitch` (string): `"very_low"`, `"low"`, `"moderate"`, `"high"`, `"very_high"`
- `speed` (string): `"very_low"`, `"low"`, `"moderate"`, `"high"`, `"very_high"`

### Optional Parameters

- `temperature` (float): Sampling temperature (0.1-2.0, default: 0.8)
- `top_k` (int): Top-k sampling (1-100, default: 50)
- `top_p` (float): Top-p sampling (0.1-1.0, default: 0.95)
- `output_format` (string): `"wav"`, `"mp3"`, or `"flac"` (default: "wav")
- `generate_subtitles` (bool): Generate word-level subtitles (default: false)

## Response Format

```json
{
  "audio_url": "https://your-bucket.s3.amazonaws.com/output/sparktts_20250108_142530.wav",
  "filename": "sparktts_20250108_142530.wav",
  "duration_seconds": 4.25,
  "sample_rate": 16000,
  "format": "wav",
  "subtitle_url": "https://your-bucket.s3.amazonaws.com/output/sparktts_20250108_142530.ass",
  "subtitle_format": "ass",
  "word_timings": [
    {"word": "Hello", "start": 0.12, "end": 0.48, "score": 0.98},
    {"word": "world", "start": 0.52, "end": 0.89, "score": 0.96}
  ],
  "generation_params": {
    "text": "Hello world",
    "temperature": 0.8,
    "top_k": 50,
    "top_p": 0.95
  }
}
```

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- CUDA-compatible GPU (recommended)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/sruckh/spark-tts-runpod-serverless.git
cd spark-tts-runpod-serverless
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your AWS credentials
```

3. Build and run with Docker Compose:
```bash
# Build the container
docker-compose build

# Run the service
docker-compose up

# With MinIO for local S3 testing
docker-compose --profile testing up
```

4. Test the API:
```bash
curl -X POST http://localhost:8000 \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Hello, this is a test!",
      "gender": "female",
      "pitch": "moderate",
      "speed": "moderate"
    }
  }'
```

### Code Quality

The project uses several tools for code quality:

```bash
# Format code
black .
isort .

# Lint code  
flake8 .
pylint handler.py utils/

# Type checking (if using mypy)
mypy handler.py
```

## Architecture

### Directory Structure

```
/runpod-volume/Spark-TTS/
├── cli/                    # Original Spark-TTS CLI
├── sparktts/              # Core Spark-TTS modules  
├── pretrained_models/     # Downloaded models
│   └── Spark-TTS-0.5B/   # Main model
├── utils/                 # Serverless utilities
│   ├── s3_utils.py       # S3 integration
│   ├── whisper_utils.py  # WhisperX integration
│   └── ass_utils.py      # Subtitle generation
├── handler.py            # Main RunPod handler
└── download_models.py    # Model download utility
```

### Components

- **handler.py**: Main RunPod serverless handler
- **s3_utils.py**: S3 file operations with pre-signed URLs
- **whisper_utils.py**: WhisperX integration for word-level timing
- **ass_utils.py**: Advanced SubStation Alpha subtitle generation
- **download_models.py**: Automatic model downloading and caching

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 | Yes |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 | Yes |
| `AWS_REGION` | AWS region | Yes |
| `S3_BUCKET_NAME` | S3 bucket name | Yes |
| `LOG_LEVEL` | Logging level (INFO, DEBUG, etc.) | No |

## S3 Bucket Structure

Your S3 bucket should be organized as follows:

```
your-bucket/
├── voices/              # Reference voice samples
│   ├── female_voice_1.wav
│   ├── male_voice_1.wav
│   └── ...
└── output/              # Generated audio and subtitles
    ├── sparktts_20250108_142530.wav
    ├── sparktts_20250108_142530.ass
    └── ...
```

## Performance Optimization

- **Model Caching**: Models are cached on `/runpod-volume` for fast subsequent runs
- **Memory Management**: Efficient memory usage with proper cleanup
- **Batch Processing**: Optimized for single-request processing in serverless environment
- **GPU Acceleration**: Full CUDA support with fallback to CPU

## Troubleshooting

### Common Issues

1. **Model Loading Errors**: Ensure models are properly downloaded to `/runpod-volume/Spark-TTS/pretrained_models/`
2. **S3 Access Errors**: Verify AWS credentials and bucket permissions
3. **Memory Issues**: Ensure sufficient memory allocation (minimum 4GB recommended)
4. **CUDA Errors**: Check CUDA installation and compatibility

### Debug Mode

Enable debug logging by setting `LOG_LEVEL=DEBUG` environment variable.

### Health Check

The container includes a health check endpoint:
```bash
docker exec spark-tts-serverless python -c "import torch; print('Health check passed')"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add type hints where applicable
- Include comprehensive error handling
- Write tests for new functionality
- Update documentation for API changes

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [SparkAudio](https://github.com/SparkAudio/Spark-TTS) for the original Spark-TTS implementation
- [RunPod](https://runpod.io) for the serverless platform
- [WhisperX](https://github.com/m-bain/whisperX) for word-level timing
- [Advanced SubStation Alpha](https://github.com/ass-tools/ass) for subtitle support

## Support

For issues and questions:

1. Check the [Issues](https://github.com/sruckh/spark-tts-runpod-serverless/issues) page
2. Join the community discussions
3. Read the [Spark-TTS documentation](https://github.com/SparkAudio/Spark-TTS)

---

**Note**: This is a serverless implementation of Spark-TTS. For the original implementation and training code, visit the [official Spark-TTS repository](https://github.com/SparkAudio/Spark-TTS).