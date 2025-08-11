# Minimal Dockerfile for Spark-TTS Runpod Serverless
# Builds quickly on GitHub Actions
# Dependencies are installed on /runpod-volume at runtime

FROM runpod/base:0.4.0-cuda12.2.0

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-pip \
    python3.11-dev \
    git \
    wget \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Install only essential Python packages for the container
# Most dependencies will be installed on /runpod-volume
RUN pip install --no-cache-dir \
    runpod==1.6.2 \
    boto3==1.34.25 \
    huggingface-hub==0.20.2

# Copy application code
COPY cli/ /app/cli/
COPY sparktts/ /app/sparktts/
COPY handler.py /app/
COPY s3_utils.py /app/
COPY setup_volume.py /app/
COPY requirements_runtime.txt /app/

# Create volume mount point
RUN mkdir -p /runpod-volume

# Set environment variables
ENV PYTHONPATH="/app:/runpod-volume/SparkTTS-serverless/venv/lib/python3.11/site-packages"
ENV PATH="/runpod-volume/SparkTTS-serverless/venv/bin:$PATH"
ENV TRANSFORMERS_CACHE="/runpod-volume/SparkTTS-serverless/cache"
ENV HF_HOME="/runpod-volume/SparkTTS-serverless/cache"
ENV TORCH_HOME="/runpod-volume/SparkTTS-serverless/cache"

# Run setup script on container start (will check if already setup)
CMD ["python", "-u", "/app/setup_volume.py"]