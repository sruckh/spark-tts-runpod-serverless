**Project GOALS**

  1. This should be a simple repackaging project.  This source code already works without change.  The goal is to repackage it so that it runs as a runpod serverless.
  2. The initial container should be minimal and build easily on GitHub
  3. sruckh/spark-tts-runpod-serverless is the repository for GitHub.  Update the origin with the new github repository if it is not already set.
  4. All the parameters to cli.inference script should be supported by the API endpoint in the serverless environment
  5. gemeneye/ is the repository for DockerHub.  The sercrets DOCKER_USERNAME and DOCKER_PASSWORD have been configured for github action to automatically build and deploy container to dockerhub.
  6. There is not enough space on the serverless container for all the python modules, dependencies, programs, and AI models.  A network volume, /runpod-volume will be attached at runtime, this is where programs, modules, and AI models need to be installed.
  7. A sub-directory SparkTTS-serverless should be created on the /runpod-volume.  This is where all the data on the /runpod-volume should be stored.
  8. AI models should be written to /runpod-volume on first load, and read from /runpod-volume on subsequent inference API calls
  10. S3 storage will be used to store output and to read read reference voice audio files used for one-shot voice cloning.
  11. Voice reference audio is in the voices sub-directory
  12. Voice output will be stored in the output sub-directory
  13. Base64 should never be used for files; use direct file names or URLs to files
  14. Pre-signed URLs should be used for downloading files from the S3 volume
  15. Environmental variables should be used for everything requiring variable input
  16. WhisperX should be used for creating word-level timings
  17. The Python module, ass, should be used for creating Advanced SubStation Alpha subtitles for use with FFmpeg
  18. Lazy model loading is prohibited because it does not make sense in a serverless platform
  19. Create a python 3.11 environment for the serverless
  20. This version of flash_attn should be installed in Python virtual environment on /runpod-volume, https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.0.post2/flash_attn-2.8.0.post2+cu12torch2.6cxx11abiFALSE-cp311-cp311-linux_x86_64.whl
  21. This version of PyTorch should be installed in Python virtual environment on /runpod-volume, "pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu126"
  22. These rules should be maintained across all sub-agents that are launched.
  23. Use pylint, flake8, and black tools, which are already installed to lint programs when necessary.
