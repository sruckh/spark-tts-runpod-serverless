# Spark-TTS RunPod Serverless Dockerfile
# Copyright (c) 2025 SparkAudio
# Licensed under the Apache License, Version 2.0

FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV RUNPOD_VOLUME=/runpod-volume
ENV VIRTUAL_ENV=$RUNPOD_VOLUME/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH="$RUNPOD_VOLUME/Spark-TTS:$PYTHONPATH"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    curl \
    ffmpeg \
    git \
    libsndfile1 \
    libsox-fmt-all \
    libsox-dev \
    sox \
    wget \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create runpod-volume directory structure
RUN mkdir -p $RUNPOD_VOLUME/Spark-TTS/pretrained_models \
    && mkdir -p $RUNPOD_VOLUME/Spark-TTS/utils \
    && mkdir -p $RUNPOD_VOLUME/logs

# Create Python virtual environment on runpod-volume
RUN python -m venv $VIRTUAL_ENV

# Upgrade pip and install wheel in virtual environment
RUN pip install --upgrade pip setuptools wheel

# Copy requirements file
COPY requirements-serverless.txt /tmp/requirements-serverless.txt

# Install PyTorch 2.6.0 with CUDA 12.6 support in virtual environment
RUN pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu126

# Install flash_attn from specific wheel in virtual environment
RUN pip install https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.0.post2/flash_attn-2.8.0.post2+cu12torch2.6cxx11abiFALSE-cp311-cp311-linux_x86_64.whl

# Install other dependencies in virtual environment
RUN pip install -r /tmp/requirements-serverless.txt

# Copy application code to runpod-volume
COPY cli/ $RUNPOD_VOLUME/Spark-TTS/cli/
COPY sparktts/ $RUNPOD_VOLUME/Spark-TTS/sparktts/
COPY utils/ $RUNPOD_VOLUME/Spark-TTS/utils/
COPY handler.py $RUNPOD_VOLUME/Spark-TTS/
COPY download_models.py $RUNPOD_VOLUME/Spark-TTS/

# Set working directory
WORKDIR $RUNPOD_VOLUME/Spark-TTS

# Download models during build (optional - can be done at runtime)
# Uncomment the next line if you want models downloaded at build time
# RUN python download_models.py

# Create non-root user for security
RUN groupadd -r sparktts && useradd -r -g sparktts sparktts
RUN chown -R sparktts:sparktts $RUNPOD_VOLUME
USER sparktts

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD python -c "import torch; print('Health check passed')"

# Set default command
CMD ["python", "handler.py"]

# Labels for metadata
LABEL maintainer="SparkAudio"
LABEL version="1.0.0"
LABEL description="Spark-TTS RunPod Serverless"
LABEL org.opencontainers.image.source="https://github.com/sruckh/spark-tts-runpod-serverless"
LABEL org.opencontainers.image.documentation="https://github.com/sruckh/spark-tts-runpod-serverless/blob/main/README.md"
LABEL org.opencontainers.image.licenses="Apache-2.0"