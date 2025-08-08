


**Project GOALS**

 1. Work as a runpod serverless
 2. Initial Container should be minimal and build easily on gihub
 3. sruckh/spark-tts-runpod-serverless is the respository for github
 4. All the parameters to cli.inference should be supported by API endpoint in serverless environment
 5. gemneye/ is the repository for dockerhub
 6. serverless should create a python virtual environment on /runpod-volume at build-time
 7. pythond modules and dependencies should be installed onto the /runpod-volume in the python virtual environment
 8. AI models shoud be written to /runpod-volume on first time load, and read from /runpod-volume on subsequent inference API calls.
 9. Files stored on the /runpod-volume drive should be stored in the sub-directory called Spark-TTS
 10. S3 storage will be used to store output and read reference voice audio files
 11. voice reference audio is in the voices sub-directory 
 12. voice output will be stored in the output sub-direcory
 13. base64 should never be used for files.  Either direct files names, or urls to files should be used.
 14. pre-signed URLs should be used for downloading files from the S3 volume
 15.  environmental variables should be used for everything requiring variable input
 16. WhisperX should be used for creating word-level timings
 17. the python module ass should be use for creating Advanced SubStation Alpha sub-titles for use with ffmpeg
 18. lazy model loading is prohibited because it does not make sense in a serverless platform
 19. python 3.11-slim should be used for main container image
 21. This version of flash_attn should be installed in python virtual environment on /runpod-volume, https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.0.post2/flash_attn-2.8.0.post2+cu12torch2.6cxx11abiFALSE-cp311-cp311-linux_x86_64.whl
 22. This version of pytorch should be installed in python virtual environment on /runpod-volume, "pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu126"
 23.  These rules should be maintained across all sub-agents that are launched.
 24. use pylint and flake8 tools to lint code
 25. use github secrets DOCKER_USERNAME and DOCKER_PASSWORD for pushing container to dockerhub

