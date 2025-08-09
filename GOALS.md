**Project GOALS**

  1. Work as a RunPod serverless
  2. The initial container should be minimal and build easily on GitHub
  3. sruckh/spark-tts-runpod-serverless is the repository for GitHub
  4. All the parameters to cli.inference should be supported by the API endpoint in the serverless environment
  5. gemeneye/ is the repository for DockerHub
  6. Serverless should create a Python virtual environment on /runpod-volume at build time
  7. Python modules and dependencies should be installed onto the /runpod-volume in the Python virtual environment
  8. AI models should be written to /runpod-volume on first load, and read from /runpod-volume on subsequent inference API calls
  9. Files stored on the /runpod-volume drive should be stored in the sub-directory called Spark-TTS
  10. S3 storage will be used to store outputs and read reference voice audio files
  11. Voice reference audio is in the voices sub-directory
  12. Voice output will be stored in the output sub-directory
  13. Base64 should never be used for files; use direct file names or URLs to files
  14. Pre-signed URLs should be used for downloading files from the S3 volume
  15. Environmental variables should be used for everything requiring variable input
  16. WhisperX should be used for creating word-level timings
  17. The Python module ASS should be used for creating Advanced SubStation Alpha subtitles for use with FFmpeg
  18. Lazy model loading is prohibited because it does not make sense in a serverless platform
  19. Python 3.11-slim should be used for the main container image
  20. This version of flash_attn should be installed in Python virtual environment on /runpod-volume, https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.0.post2/flash_attn-2.8.0.post2+cu12torch2.6cxx11abiFALSE-cp311-cp311-linux_x86_64.whl
  21. This version of PyTorch should be installed in Python virtual environment on /runpod-volume, "pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu126"
  22. These rules should be maintained across all sub-agents that are launched.
  23. Use pylint and flake8 tools to lint code
  24. Use GitHub secrets DOCKER_USERNAME and DOCKER_PASSWORD for pushing container to DockerHub
