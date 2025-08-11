#!/usr/bin/env python3
"""
Setup script for /runpod-volume
Installs dependencies and downloads models on first run
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VOLUME_PATH = "/runpod-volume/SparkTTS-serverless"
VENV_PATH = f"{VOLUME_PATH}/venv"
MODEL_PATH = f"{VOLUME_PATH}/models/Spark-TTS-0.5B"
CACHE_PATH = f"{VOLUME_PATH}/cache"
SETUP_MARKER = f"{VOLUME_PATH}/.setup_complete"

def setup_volume():
    """Setup the volume with dependencies and models"""
    
    # Check if already setup
    if os.path.exists(SETUP_MARKER):
        logger.info("Volume already setup, checking integrity...")
        if verify_setup():
            logger.info("Setup verified, continuing...")
            return True
        else:
            logger.warning("Setup verification failed, re-running setup...")
    
    logger.info(f"Setting up volume at {VOLUME_PATH}")
    
    # Create directory structure
    os.makedirs(VOLUME_PATH, exist_ok=True)
    os.makedirs(MODEL_PATH, exist_ok=True)
    os.makedirs(CACHE_PATH, exist_ok=True)
    os.makedirs(f"{VOLUME_PATH}/logs", exist_ok=True)
    
    # Create Python virtual environment
    if not os.path.exists(VENV_PATH):
        logger.info("Creating Python 3.11 virtual environment...")
        subprocess.run([
            sys.executable, "-m", "venv", VENV_PATH
        ], check=True)
    
    # Upgrade pip
    logger.info("Upgrading pip...")
    subprocess.run([
        f"{VENV_PATH}/bin/pip", "install", "--upgrade", "pip"
    ], check=True)
    
    # Install PyTorch with CUDA 12.6 support
    logger.info("Installing PyTorch 2.6.0 with CUDA 12.6...")
    subprocess.run([
        f"{VENV_PATH}/bin/pip", "install",
        "torch==2.6.0", "torchvision==0.21.0", "torchaudio==2.6.0",
        "--index-url", "https://download.pytorch.org/whl/cu126"
    ], check=True)
    
    # Install flash-attention
    logger.info("Installing flash-attention...")
    flash_attn_url = "https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.0.post2/flash_attn-2.8.0.post2+cu12torch2.6cxx11abiFALSE-cp311-cp311-linux_x86_64.whl"
    subprocess.run([
        f"{VENV_PATH}/bin/pip", "install", flash_attn_url
    ], check=True)
    
    # Install other dependencies
    logger.info("Installing other dependencies...")
    dependencies = [
        "transformers==4.46.2",
        "soundfile==0.12.1",
        "soxr==0.5.0.post1",
        "gradio==5.18.0",
        "einops==0.8.1",
        "numpy==2.2.3",
        "tqdm==4.66.5",
        "omegaconf==2.3.0",
        "safetensors==0.5.2",
        "boto3==1.34.25",
        "runpod==1.6.2",
        "huggingface-hub==0.20.2",
        "whisperx @ git+https://github.com/m-bain/whisperX.git",
        "ass==0.5.2"
    ]
    
    for dep in dependencies:
        logger.info(f"Installing {dep}...")
        subprocess.run([
            f"{VENV_PATH}/bin/pip", "install", dep
        ], check=True)
    
    # Download models if not present
    if not os.path.exists(f"{MODEL_PATH}/config.yaml"):
        logger.info("Downloading Spark-TTS models...")
        download_models()
    
    # Create setup marker
    with open(SETUP_MARKER, 'w') as f:
        f.write("Setup completed successfully\n")
    
    logger.info("Volume setup completed successfully!")
    return True

def download_models():
    """Download Spark-TTS models from HuggingFace"""
    try:
        from huggingface_hub import snapshot_download
        
        logger.info("Downloading models from HuggingFace...")
        snapshot_download(
            repo_id="SparkAudio/Spark-TTS-0.5B",
            local_dir=MODEL_PATH,
            local_dir_use_symlinks=False,
            cache_dir=CACHE_PATH
        )
        logger.info("Models downloaded successfully")
        
    except Exception as e:
        logger.error(f"Failed to download models: {e}")
        # Try alternative download method
        try:
            import subprocess
            logger.info("Trying git clone method...")
            subprocess.run([
                "git", "clone", 
                "https://huggingface.co/SparkAudio/Spark-TTS-0.5B",
                MODEL_PATH
            ], check=True)
        except Exception as e2:
            logger.error(f"Alternative download also failed: {e2}")
            raise

def verify_setup():
    """Verify that the setup is complete and valid"""
    checks = [
        (VENV_PATH, "Virtual environment"),
        (f"{VENV_PATH}/bin/python", "Python executable"),
        (f"{MODEL_PATH}/config.yaml", "Model config"),
        (f"{MODEL_PATH}/LLM", "LLM model directory"),
    ]
    
    all_good = True
    for path, description in checks:
        if not os.path.exists(path):
            logger.warning(f"Missing: {description} at {path}")
            all_good = False
    
    # Check if torch is importable
    try:
        sys.path.insert(0, f"{VENV_PATH}/lib/python3.11/site-packages")
        import torch
        logger.info(f"PyTorch version: {torch.__version__}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
    except ImportError as e:
        logger.warning(f"Cannot import torch: {e}")
        all_good = False
    
    return all_good

def main():
    """Main entry point"""
    try:
        # Setup volume
        if setup_volume():
            logger.info("Setup successful, starting handler...")
            # Import and run handler
            sys.path.insert(0, "/app")
            sys.path.insert(0, VOLUME_PATH)
            
            # Set environment for the handler
            os.environ['PYTHONPATH'] = f"/app:{VENV_PATH}/lib/python3.11/site-packages"
            
            # Run the handler
            import handler
            logger.info("Handler imported, starting Runpod serverless...")
        else:
            logger.error("Setup failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Setup error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()