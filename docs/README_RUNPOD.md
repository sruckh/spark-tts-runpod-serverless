# Spark-TTS Runpod Serverless

This is a repackaged version of Spark-TTS optimized for deployment on Runpod Serverless infrastructure.

## Features

- ✅ All CLI parameters supported via API
- ✅ S3 integration for voice references and output
- ✅ Minimal Docker container (builds on GitHub Actions)
- ✅ Eager model loading (no lazy loading)
- ✅ WhisperX word-level timing generation
- ✅ ASS subtitle generation
- ✅ Python 3.11 with optimized PyTorch 2.6.0 + CUDA 12.6
- ✅ Flash Attention 2.8.0 for improved performance

## Quick Start

### 1. Deploy to Runpod

1. Create a new Serverless Endpoint on Runpod
2. Use Docker image: `gemeneye/spark-tts-runpod-serverless:latest`
3. Set GPU: at least 24GB VRAM recommended (RTX 3090/4090 or A5000)
4. Configure environment variables (see below)
5. Attach a network volume at `/runpod-volume`

### 2. Environment Variables

Required:
- `S3_BUCKET_NAME`: Your S3 bucket for voices and output
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `AWS_REGION`: AWS region (default: us-east-1)

Optional:
- `LOG_LEVEL`: Logging level (default: INFO)
- `MAX_LENGTH`: Maximum token length (default: 4096)

### 3. API Usage

Send a POST request to your Runpod endpoint:

```json
{
  "input": {
    "text": "Hello, this is a test of Spark-TTS on Runpod Serverless.",
    "speaker_gender": "female",
    "prompt_text": "Reference speaker says this.",
    "prompt_speech_url": "s3://your-bucket/voices/reference.wav",
    "output_name": "test_output",
    "pitch_shift": 0.0,
    "speed_shift": 1.0,
    "temperature": 0.7,
    "top_p": 0.95,
    "enable_whisperx": true,
    "enable_subtitles": true
  }
}
```

### 4. Response Format

```json
{
  "status": "success",
  "audio_url": "https://your-bucket.s3.amazonaws.com/output/test_output_xyz.wav",
  "sample_rate": 24000,
  "duration": 3.5,
  "word_timings": [...],
  "subtitles_url": "https://your-bucket.s3.amazonaws.com/output/subtitles/test_output_xyz.ass"
}
```

## API Parameters

All parameters from the original CLI are supported:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | string | required | Text to synthesize |
| `prompt_text` | string | optional | Reference text for voice cloning |
| `prompt_speech_url` | string | optional | S3 URL to reference audio |
| `output_name` | string | "output" | Output file name prefix |
| `speaker_gender` | string | "male" | Gender: "male" or "female" |
| `pitch_shift` | float | 0.0 | Pitch adjustment (-12 to 12) |
| `speed_shift` | float | 1.0 | Speed adjustment (0.5 to 2.0) |
| `multi_sentence_gap` | float | 0.3 | Gap between sentences (seconds) |
| `task_token` | string | "zero_shot" | Task type |
| `temperature` | float | 0.7 | Generation temperature |
| `top_p` | float | 0.95 | Nucleus sampling |
| `max_length` | int | 4096 | Maximum tokens |
| `enable_whisperx` | bool | false | Generate word timings |
| `enable_subtitles` | bool | false | Generate ASS subtitles |

## S3 Bucket Structure

Your S3 bucket should have this structure:
```
your-bucket/
├── voices/           # Reference voice audio files
│   ├── voice1.wav
│   └── voice2.wav
└── output/          # Generated audio files
    └── subtitles/   # Generated subtitle files
```

## Volume Structure

The `/runpod-volume` is organized as:
```
/runpod-volume/SparkTTS-serverless/
├── venv/            # Python 3.11 virtual environment
├── models/          # Spark-TTS model files
│   └── Spark-TTS-0.5B/
├── cache/           # HuggingFace and PyTorch cache
└── logs/            # Application logs
```

## Performance

- First request: ~30-60s (model loading)
- Subsequent requests: ~2-5s for 10-second audio
- GPU Memory: ~8-12GB
- Disk space on volume: ~15GB

## Troubleshooting

### Container won't start
- Check environment variables are set correctly
- Ensure network volume is attached at `/runpod-volume`
- Check container logs for specific errors

### S3 errors
- Verify AWS credentials and bucket permissions
- Ensure bucket exists and is accessible
- Check S3 URLs are properly formatted

### Model loading fails
- Volume might be full (needs ~15GB free)
- Network issues downloading from HuggingFace
- Check logs at `/runpod-volume/SparkTTS-serverless/logs/`

### Out of memory
- Reduce `max_length` parameter
- Use smaller batch sizes
- Ensure GPU has at least 24GB VRAM

## Development

### Building locally
```bash
docker build -t spark-tts-runpod .
```

### Testing locally
```bash
docker run -it \
  -e S3_BUCKET_NAME=your-bucket \
  -e AWS_ACCESS_KEY_ID=your-key \
  -e AWS_SECRET_ACCESS_KEY=your-secret \
  -v /path/to/volume:/runpod-volume \
  --gpus all \
  spark-tts-runpod
```

## GitHub Repository

[sruckh/spark-tts-runpod-serverless](https://github.com/sruckh/spark-tts-runpod-serverless)

## Docker Hub

[gemeneye/spark-tts-runpod-serverless](https://hub.docker.com/r/gemeneye/spark-tts-runpod-serverless)

## License

Apache 2.0 - See LICENSE file for details

## Credits

Based on [Spark-TTS](https://github.com/SparkAudio/Spark-TTS) by SparkAudio