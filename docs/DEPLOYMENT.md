# Spark-TTS Runpod Serverless Deployment Guide

## Prerequisites

1. **Runpod Account**: Sign up at [runpod.io](https://runpod.io)
2. **AWS S3 Bucket**: For storing voice references and output files
3. **Docker Hub Account**: (Optional) If building custom images
4. **GPU Credits**: Ensure you have sufficient credits for GPU usage

## Step 1: S3 Setup

### Create S3 Bucket

1. Log into AWS Console
2. Navigate to S3
3. Create a new bucket (e.g., `spark-tts-data`)
4. Configure bucket settings:
   ```
   - Region: Choose closest to your Runpod region
   - Block Public Access: Enable (we'll use pre-signed URLs)
   - Versioning: Optional but recommended
   - Encryption: Enable server-side encryption
   ```

### Create IAM User

1. Navigate to IAM → Users
2. Create new user: `spark-tts-runpod`
3. Attach policy:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::spark-tts-data/*",
           "arn:aws:s3:::spark-tts-data"
         ]
       }
     ]
   }
   ```
4. Create access key and save credentials

### Initialize Bucket Structure

```bash
# Create required directories
aws s3api put-object --bucket spark-tts-data --key voices/
aws s3api put-object --bucket spark-tts-data --key output/
aws s3api put-object --bucket spark-tts-data --key output/subtitles/

# Upload reference voices (optional)
aws s3 cp reference_voice.wav s3://spark-tts-data/voices/
```

## Step 2: Runpod Configuration

### Create Network Volume

1. Navigate to Runpod Console → Storage
2. Click "New Network Volume"
3. Configure:
   ```
   Name: spark-tts-volume
   Size: 50GB (minimum 20GB)
   Region: Same as your endpoint region
   Type: High Performance
   ```
4. Save the volume ID

### Create Serverless Endpoint

1. Navigate to Serverless → Endpoints
2. Click "New Endpoint"
3. Configure:

   **Basic Settings:**
   ```
   Name: spark-tts-serverless
   Select GPUs: 
     - RTX 3090 (24GB VRAM)
     - RTX 4090 (24GB VRAM)
     - A5000 (24GB VRAM)
     - Or higher
   
   Min Workers: 0 (scales to zero)
   Max Workers: 3 (adjust based on load)
   ```

   **Container Configuration:**
   ```
   Container Image: gemeneye/spark-tts-runpod-serverless:latest
   Container Disk: 20 GB
   ```

   **Environment Variables:**
   ```bash
   S3_BUCKET_NAME=spark-tts-data
   AWS_ACCESS_KEY_ID=your-access-key
   AWS_SECRET_ACCESS_KEY=your-secret-key
   AWS_REGION=us-east-1
   LOG_LEVEL=INFO
   ```

   **Volume Mount:**
   ```
   Volume: spark-tts-volume (select from dropdown)
   Mount Path: /runpod-volume
   ```

   **Advanced Settings:**
   ```
   Idle Timeout: 5 seconds
   Execution Timeout: 300 seconds
   Max Concurrency: 1 (per worker)
   ```

4. Click "Create Endpoint"
5. Save the Endpoint ID and API Key

## Step 3: First-Time Setup

The first request will trigger automatic setup:

1. **Test the endpoint:**
   ```bash
   curl -X POST https://api.runpod.ai/v2/{endpoint-id}/runsync \
     -H "Authorization: Bearer {your-api-key}" \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "text": "Setup test",
         "output_name": "setup_test"
       }
     }'
   ```

2. **Monitor setup progress:**
   - First run takes 5-10 minutes (downloading models)
   - Check Runpod logs for progress
   - Volume will be populated with ~15GB of data

## Step 4: Production Configuration

### Scaling Configuration

For production workloads:

```yaml
Min Workers: 1  # Keep one warm
Max Workers: 10  # Based on expected load
Idle Timeout: 60  # Keep warm longer
GPU Types: 
  - RTX 4090  # Best price/performance
  - A5000     # More availability
  - A6000     # Higher memory for batch
```

### Monitoring Setup

1. **CloudWatch Integration** (optional):
   ```bash
   # Add to environment variables
   CLOUDWATCH_ENABLED=true
   CLOUDWATCH_REGION=us-east-1
   CLOUDWATCH_LOG_GROUP=/aws/runpod/spark-tts
   ```

2. **Runpod Metrics**:
   - Monitor via Runpod dashboard
   - Set up alerts for errors
   - Track GPU utilization

### Performance Optimization

1. **Model Caching**:
   - Models persist on network volume
   - No reload between requests
   - ~2-5 second generation time

2. **Batch Processing**:
   ```python
   # Process multiple texts efficiently
   texts = ["text1", "text2", "text3"]
   for text in texts:
       # Send requests with small delay
       response = send_request(text)
       time.sleep(0.1)  # Avoid rate limits
   ```

3. **GPU Selection**:
   - RTX 4090: Best for single requests
   - A6000: Better for batch processing
   - A100: Maximum performance (higher cost)

## Step 5: Testing & Validation

### Health Check

```bash
# Check endpoint status
curl https://api.runpod.ai/v2/{endpoint-id}/health
```

### Performance Test

```python
import time
import requests

def benchmark_endpoint(endpoint_id, api_key, num_requests=10):
    times = []
    for i in range(num_requests):
        start = time.time()
        response = requests.post(
            f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "input": {
                    "text": f"Test {i}: This is a performance test.",
                    "output_name": f"perf_test_{i}"
                }
            }
        )
        times.append(time.time() - start)
    
    print(f"Average: {sum(times)/len(times):.2f}s")
    print(f"Min: {min(times):.2f}s, Max: {max(times):.2f}s")
```

### Voice Cloning Test

```bash
# Upload reference voice
aws s3 cp reference.wav s3://spark-tts-data/voices/test_ref.wav

# Test voice cloning
curl -X POST https://api.runpod.ai/v2/{endpoint-id}/runsync \
  -H "Authorization: Bearer {api-key}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Testing voice cloning capabilities.",
      "prompt_text": "This is my voice.",
      "prompt_speech_url": "s3://spark-tts-data/voices/test_ref.wav"
    }
  }'
```

## Troubleshooting

### Common Issues

1. **"Model not found" error**:
   - Volume not properly mounted
   - First-time setup incomplete
   - Solution: Check volume mount, restart endpoint

2. **S3 Access Denied**:
   - Invalid credentials
   - Bucket policy incorrect
   - Solution: Verify IAM permissions

3. **Out of Memory**:
   - Text too long
   - GPU memory insufficient
   - Solution: Reduce max_length, use larger GPU

4. **Slow Cold Starts**:
   - Normal for serverless
   - Solution: Set min_workers > 0

### Logs Access

```bash
# Via Runpod CLI
runpod logs {endpoint-id} --tail 100

# Via Web Console
# Navigate to Endpoint → Logs tab
```

### Volume Inspection

```bash
# SSH into a worker (if enabled)
runpod ssh {worker-id}

# Check volume contents
ls -la /runpod-volume/SparkTTS-serverless/

# Check model files
ls -la /runpod-volume/SparkTTS-serverless/models/
```

## Maintenance

### Update Container

```bash
# Build new version
docker build -t gemeneye/spark-tts-runpod-serverless:v1.1 .
docker push gemeneye/spark-tts-runpod-serverless:v1.1

# Update endpoint
# Runpod Console → Endpoint → Settings → Container Image
```

### Clear Cache

```bash
# If volume gets full
# SSH into worker
rm -rf /runpod-volume/SparkTTS-serverless/cache/*
```

### Backup Models

```bash
# Backup models to S3
aws s3 sync /runpod-volume/SparkTTS-serverless/models/ \
  s3://spark-tts-data/backups/models/
```

## Cost Optimization

### Strategies

1. **Scale to Zero**: Set min_workers=0 for dev/test
2. **Spot Instances**: Use spot GPUs when available
3. **Region Selection**: Choose cheapest region
4. **GPU Efficiency**: RTX 4090 best price/performance
5. **Batch Requests**: Process multiple texts per GPU activation

### Cost Breakdown (Estimated)

```
RTX 4090:
- Rate: ~$0.44/hour
- Per request: ~$0.0012 (10 sec generation)
- Monthly (1000 req/day): ~$36

A5000:
- Rate: ~$0.34/hour  
- Per request: ~$0.0009
- Monthly (1000 req/day): ~$27

Storage:
- Network Volume: $0.10/GB/month = $5/month (50GB)
- S3: ~$0.023/GB/month + requests
```

## Security Best Practices

1. **API Key Rotation**: Rotate Runpod API keys monthly
2. **S3 Bucket Policy**: Use least privilege access
3. **Environment Variables**: Never commit credentials
4. **Network Security**: Use VPC endpoints if available
5. **Audit Logging**: Enable CloudTrail for S3 access

## Support

- **Runpod Support**: support@runpod.io
- **GitHub Issues**: [sruckh/spark-tts-runpod-serverless](https://github.com/sruckh/spark-tts-runpod-serverless/issues)
- **Discord**: Runpod Community Discord