#!/usr/bin/env python3
"""
Model download utility for Spark-TTS RunPod serverless
Copyright (c) 2025 SparkAudio
Licensed under the Apache License, Version 2.0

This script downloads and caches models to /runpod-volume/Spark-TTS/
"""

import logging
import os
import shutil
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
RUNPOD_VOLUME = os.environ.get("RUNPOD_VOLUME", "/runpod-volume")
SPARK_TTS_DIR = f"{RUNPOD_VOLUME}/Spark-TTS"
MODELS_DIR = f"{SPARK_TTS_DIR}/pretrained_models"
SPARK_TTS_MODEL_DIR = f"{MODELS_DIR}/Spark-TTS-0.5B"

# Model URLs and information
MODELS_CONFIG = {
    "Spark-TTS-0.5B": {
        "repo_url": "https://huggingface.co/SparkAudio/Spark-TTS-0.5B",
        "local_path": SPARK_TTS_MODEL_DIR,
        "required_files": [
            "config.yaml",
            "LLM/config.json",
            "LLM/pytorch_model.bin",
            "LLM/tokenizer.json",
            "LLM/tokenizer_config.json",
            "audio_tokenizer/config.yaml",
            "audio_tokenizer/pytorch_model.bin",
        ],
    }
}


def check_git_lfs() -> bool:
    """
    Check if git-lfs is available.

    Returns:
        bool: True if git-lfs is available
    """
    try:
        result = subprocess.run(
            ["git", "lfs", "version"], capture_output=True, text=True
        )
        if result.returncode == 0:
            logger.info("Git LFS is available")
            return True
        else:
            logger.warning("Git LFS not found, large files may not download properly")
            return False
    except FileNotFoundError:
        logger.warning("Git not found, cannot check for Git LFS")
        return False


def download_huggingface_model(repo_url: str, local_path: str) -> bool:
    """
    Download a HuggingFace model repository.

    Args:
        repo_url: HuggingFace repository URL
        local_path: Local path to download to

    Returns:
        bool: True if successful
    """
    try:
        logger.info(f"Downloading model from {repo_url}")
        logger.info(f"Target directory: {local_path}")

        # Create parent directory
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Clone the repository
        cmd = ["git", "clone", repo_url, local_path]

        logger.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Git clone failed: {result.stderr}")
            return False

        # Initialize git-lfs if available
        if check_git_lfs():
            lfs_cmd = ["git", "lfs", "pull"]
            logger.info("Pulling LFS files...")
            lfs_result = subprocess.run(
                lfs_cmd, cwd=local_path, capture_output=True, text=True
            )
            if lfs_result.returncode != 0:
                logger.warning(f"Git LFS pull failed: {lfs_result.stderr}")
                logger.warning("Some large files may be missing")

        logger.info(f"Model downloaded successfully to {local_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to download model: {str(e)}")
        return False


def verify_model_files(model_name: str, local_path: str, required_files: list) -> bool:
    """
    Verify that all required model files are present.

    Args:
        model_name: Name of the model
        local_path: Local path to check
        required_files: List of required file paths

    Returns:
        bool: True if all files are present
    """
    try:
        logger.info(f"Verifying {model_name} files...")

        missing_files = []
        for file_path in required_files:
            full_path = os.path.join(local_path, file_path)
            if not os.path.exists(full_path):
                missing_files.append(file_path)

        if missing_files:
            logger.error(f"Missing files for {model_name}:")
            for file_path in missing_files:
                logger.error(f"  - {file_path}")
            return False

        logger.info(f"All required files present for {model_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to verify model files: {str(e)}")
        return False


def get_directory_size(path: str) -> int:
    """
    Get total size of directory in bytes.

    Args:
        path: Directory path

    Returns:
        int: Total size in bytes
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass
    except OSError:
        pass
    return total_size


def format_size(size_bytes: int) -> str:
    """
    Format size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Formatted size string
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def download_all_models() -> bool:
    """
    Download all required models.

    Returns:
        bool: True if all downloads successful
    """
    success = True

    logger.info("Starting model downloads...")
    logger.info(f"Models will be stored in: {MODELS_DIR}")

    # Create models directory
    os.makedirs(MODELS_DIR, exist_ok=True)

    for model_name, config in MODELS_CONFIG.items():
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing model: {model_name}")
        logger.info(f"{'='*50}")

        local_path = config["local_path"]

        # Check if model already exists
        if os.path.exists(local_path):
            logger.info(f"Model directory exists: {local_path}")

            # Verify files
            if verify_model_files(model_name, local_path, config["required_files"]):
                logger.info(f"Model {model_name} already downloaded and verified")

                # Show size info
                size_bytes = get_directory_size(local_path)
                logger.info(f"Model size: {format_size(size_bytes)}")
                continue
            else:
                logger.warning(
                    f"Model {model_name} exists but is incomplete, re-downloading..."
                )
                shutil.rmtree(local_path)

        # Download the model
        if download_huggingface_model(config["repo_url"], local_path):
            # Verify the download
            if verify_model_files(model_name, local_path, config["required_files"]):
                size_bytes = get_directory_size(local_path)
                logger.info(f"Model {model_name} downloaded successfully")
                logger.info(f"Model size: {format_size(size_bytes)}")
            else:
                logger.error(f"Model {model_name} download verification failed")
                success = False
        else:
            logger.error(f"Failed to download model {model_name}")
            success = False

    return success


def cleanup_git_files():
    """Remove .git directories to save space."""
    try:
        logger.info("Cleaning up .git directories to save space...")

        for root, dirs, files in os.walk(MODELS_DIR):
            if ".git" in dirs:
                git_path = os.path.join(root, ".git")
                logger.info(f"Removing: {git_path}")
                shutil.rmtree(git_path)
                dirs.remove(".git")  # Don't recurse into .git

        logger.info("Git cleanup completed")

    except Exception as e:
        logger.error(f"Git cleanup failed: {str(e)}")


def show_summary():
    """Show download summary."""
    try:
        logger.info(f"\n{'='*50}")
        logger.info("DOWNLOAD SUMMARY")
        logger.info(f"{'='*50}")

        total_size = 0
        for model_name, config in MODELS_CONFIG.items():
            local_path = config["local_path"]
            if os.path.exists(local_path):
                size_bytes = get_directory_size(local_path)
                total_size += size_bytes
                logger.info(f"{model_name}: {format_size(size_bytes)}")
            else:
                logger.error(f"{model_name}: NOT FOUND")

        logger.info(f"Total size: {format_size(total_size)}")

        # Disk usage for entire Spark-TTS directory
        if os.path.exists(SPARK_TTS_DIR):
            total_spark_size = get_directory_size(SPARK_TTS_DIR)
            logger.info(
                f"Total Spark-TTS directory size: {format_size(total_spark_size)}"
            )

        logger.info(f"Models directory: {MODELS_DIR}")

    except Exception as e:
        logger.error(f"Failed to show summary: {str(e)}")


def main():
    """Main function."""
    try:
        logger.info("Spark-TTS Model Downloader")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"RunPod volume: {RUNPOD_VOLUME}")
        logger.info(f"Spark-TTS directory: {SPARK_TTS_DIR}")

        # Check available disk space
        if os.path.exists(RUNPOD_VOLUME):
            stat = os.statvfs(RUNPOD_VOLUME)
            free_bytes = stat.f_bavail * stat.f_frsize
            logger.info(f"Available disk space: {format_size(free_bytes)}")

            # Check if we have enough space (rough estimate: 2GB needed)
            if free_bytes < 2 * 1024**3:
                logger.warning(
                    f"Low disk space! Only {format_size(free_bytes)} available"
                )
                logger.warning("Model download may fail due to insufficient space")

        # Download models
        if download_all_models():
            logger.info("All models downloaded successfully!")

            # Clean up git files to save space
            cleanup_git_files()

            # Show summary
            show_summary()

            logger.info("Model download completed successfully!")
            return 0
        else:
            logger.error("Some model downloads failed!")
            return 1

    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
