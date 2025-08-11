# Spark-TTS Runpod Serverless Architecture

## System Overview

Spark-TTS Runpod Serverless is a cloud-native implementation of the Spark-TTS text-to-speech system, optimized for serverless GPU inference on Runpod's infrastructure.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│   Runpod     │────▶│   Worker    │
│             │     │   Endpoint   │     │   (GPU)     │
└─────────────┘     └──────────────┘     └─────────────┘
                            │                     │
                            ▼                     ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   S3 Bucket  │     │   Network   │
                    │              │◀────│   Volume    │
                    └──────────────┘     └─────────────┘
```

## Component Architecture

### 1. Container Layer (Minimal)

The Docker container is designed to be minimal and fast-building:

```dockerfile
Base Image: runpod/base:0.4.0-cuda12.2.0
├── System Dependencies (minimal)
│   ├── Python 3.11
│   ├── ffmpeg
│   └── git
├── Application Code
│   ├── handler.py       # Main Runpod handler
│   ├── s3_utils.py      # S3 integration
│   ├── setup_volume.py  # Volume initialization
│   ├── cli/             # Spark-TTS CLI code
│   └── sparktts/        # Core library
└── Entry Point
    └── setup_volume.py → handler.py
```

**Key Design Decisions:**
- No model files in container (loaded from volume)
- No heavy dependencies (installed on volume)
- Fast GitHub Actions builds (<5 minutes)
- Container size <1GB

### 2. Volume Layer (Persistent)

The network volume stores all heavy dependencies and models:

```
/runpod-volume/SparkTTS-serverless/
├── venv/                  # Python 3.11 virtual environment
│   ├── bin/
│   └── lib/python3.11/
│       └── site-packages/
│           ├── torch==2.6.0
│           ├── transformers==4.46.2
│           ├── flash_attn==2.8.0
│           └── ...
├── models/                # Model files (~8GB)
│   └── Spark-TTS-0.5B/
│       ├── config.yaml
│       ├── LLM/          # Qwen2.5 model
│       ├── codec/        # Audio codec
│       └── vocoder/      # Vocoder model
├── cache/                 # HuggingFace cache
└── logs/                  # Application logs
```

**Volume Initialization Process:**
1. Check for setup marker
2. Create virtual environment
3. Install PyTorch with CUDA 12.6
4. Install flash-attention wheel
5. Install other dependencies
6. Download models from HuggingFace
7. Create setup completion marker

### 3. Request Processing Pipeline

```
Request Flow:
┌──────────┐
│  Request │
└────┬─────┘
     ▼
[Input Validation]
     ├── Validate required parameters
     ├── Check parameter ranges
     └── Parse S3 URLs
     ▼
[Reference Audio Processing] (if provided)
     ├── Download from S3
     ├── Resample to 16kHz
     └── Convert to tensor
     ▼
[Text Processing]
     ├── Tokenization
     ├── Language detection
     └── Sentence segmentation
     ▼
[Model Inference]
     ├── Load models (eager, not lazy)
     ├── Generate audio tokens
     └── Vocoder synthesis
     ▼
[Post-Processing]
     ├── WhisperX (optional)
     ├── Subtitle generation (optional)
     └── Audio normalization
     ▼
[Output Handling]
     ├── Upload audio to S3
     ├── Generate pre-signed URLs
     └── Return response
```

### 4. Model Loading Strategy

**Eager Loading (No Lazy Loading):**

```python
# Models loaded on startup, not per request
class ModelManager:
    def __init__(self):
        self.load_all_models()  # Load immediately
    
    def load_all_models(self):
        self.llm = load_llm()
        self.codec = load_codec()
        self.vocoder = load_vocoder()
        # All models in memory before first request
```

**Benefits:**
- Predictable latency (no cold model loads)
- Better for serverless (models persist between requests)
- Optimal GPU memory allocation

### 5. S3 Integration Architecture

```
S3 Bucket Structure:
spark-tts-data/
├── voices/                 # Input: Reference audio files
│   ├── speaker1.wav
│   └── speaker2.wav
├── output/                 # Output: Generated audio
│   ├── {job_id}.wav
│   └── subtitles/         # Output: Generated subtitles
│       └── {job_id}.ass
└── backups/               # Optional: Model backups
```

**S3 Operations:**
- **Download**: Reference audio via pre-signed URLs
- **Upload**: Generated audio with expiring URLs
- **No Base64**: Direct file operations only
- **Streaming**: Large file support

### 6. API Design

**Endpoint Structure:**
```
POST /runsync
├── Synchronous execution
├── 300-second timeout
└── Direct response

POST /run
├── Asynchronous execution
├── Webhook support
└── Job ID returned
```

**Parameter Mapping:**
All CLI parameters mapped to API:
```python
CLI: --pitch_shift 2.0
API: {"pitch_shift": 2.0}

CLI: --prompt_speech_path file.wav
API: {"prompt_speech_url": "s3://..."}
```

### 7. Performance Optimizations

**GPU Optimization:**
- Flash Attention 2.8.0 for efficient attention
- Mixed precision (FP16) inference
- Optimal batch sizing
- CUDA 12.6 with latest kernels

**Memory Management:**
```python
# Efficient memory usage
torch.cuda.empty_cache()  # Clear unused
torch.backends.cudnn.benchmark = True  # Optimize convolutions
```

**Caching Strategy:**
- Models cached in GPU memory
- Tokenizer cache on volume
- S3 response caching (1 hour)

### 8. Error Handling & Recovery

**Error Hierarchy:**
```
Application Errors
├── Input Validation
│   └── Return 400 with details
├── Model Errors
│   ├── Retry with lower precision
│   └── Return 500 with error
├── S3 Errors
│   ├── Retry with backoff
│   └── Return 503 if persistent
└── System Errors
    ├── Log to volume
    └── Return 500 with trace ID
```

**Recovery Mechanisms:**
- Automatic volume repair
- Model re-download on corruption
- S3 fallback to direct upload
- Graceful degradation

### 9. Security Architecture

**Layers of Security:**
```
1. API Layer
   ├── Runpod API key authentication
   └── Rate limiting

2. Storage Layer
   ├── S3 IAM policies
   ├── Pre-signed URLs (expiring)
   └── Bucket encryption

3. Compute Layer
   ├── Isolated containers
   ├── No root access
   └── Environment variable secrets

4. Network Layer
   ├── Private VPC (if configured)
   └── TLS encryption
```

### 10. Scaling Architecture

**Horizontal Scaling:**
```
Load Balancer
    │
    ├── Worker 1 (GPU)
    ├── Worker 2 (GPU)
    └── Worker N (GPU)
         │
         └── Shared Network Volume
```

**Scaling Triggers:**
- Request queue depth
- Average response time
- GPU utilization
- Memory pressure

**Scaling Limits:**
- Min workers: 0 (scale to zero)
- Max workers: Configured limit
- Scale-up time: ~30 seconds
- Scale-down delay: 60 seconds

## Data Flow Diagram

```
[Client Request]
       │
       ▼
[Runpod API Gateway]
       │
       ├──────[Authentication]
       │
       ▼
[Load Balancer]
       │
       ├──────[Route to Available Worker]
       │
       ▼
[Worker Container]
       │
       ├──────[Load Models from Volume]
       │
       ├──────[Download Reference from S3]
       │
       ├──────[Process with Spark-TTS]
       │
       ├──────[Generate Audio]
       │
       ├──────[Upload to S3]
       │
       ▼
[Response with URLs]
```

## Technology Stack

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Runtime | Python | 3.11 | Primary language |
| ML Framework | PyTorch | 2.6.0 | Deep learning |
| GPU Acceleration | CUDA | 12.6 | GPU compute |
| Attention | Flash Attention | 2.8.0 | Efficient attention |
| Container | Docker | Latest | Containerization |
| Orchestration | Runpod | Latest | Serverless platform |
| Storage | AWS S3 | Latest | Object storage |
| CI/CD | GitHub Actions | Latest | Automation |
| Models | Qwen2.5 | 0.5B | LLM backbone |

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Cold Start | 30-60s | First request, model loading |
| Warm Start | <1s | Models already loaded |
| Generation Time | 2-5s | For 10-second audio |
| GPU Memory | 8-12GB | Depends on batch size |
| Disk Usage | ~15GB | Models + dependencies |
| Network Volume | 50GB | Recommended size |
| Max Text Length | 4096 tokens | Configurable |
| Audio Quality | 24kHz | Sample rate |

## Future Enhancements

1. **Multi-GPU Support**: Distribute inference across GPUs
2. **Model Quantization**: Reduce model size with INT8
3. **Streaming Response**: Real-time audio streaming
4. **Edge Caching**: CDN for generated audio
5. **A/B Testing**: Multiple model versions
6. **Batch API**: Process multiple texts efficiently
7. **WebSocket Support**: Real-time bidirectional communication
8. **Monitoring Dashboard**: Grafana integration