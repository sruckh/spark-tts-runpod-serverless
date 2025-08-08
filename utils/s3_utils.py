"""
S3 utilities for RunPod Spark-TTS serverless
Copyright (c) 2025 SparkAudio
Licensed under the Apache License, Version 2.0

This module handles S3 operations for voice files and output audio.
"""

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class S3Manager:
    """
    Manages S3 operations for voice files and audio output.
    """

    def __init__(self):
        """
        Initialize S3 manager with environment variables.

        Required environment variables:
        - AWS_ACCESS_KEY_ID
        - AWS_SECRET_ACCESS_KEY
        - AWS_REGION
        - S3_BUCKET_NAME
        """
        self.access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.region = os.environ.get("AWS_REGION", "us-east-1")
        self.bucket_name = os.environ.get("S3_BUCKET_NAME")

        if not all([self.access_key, self.secret_key, self.bucket_name]):
            raise ValueError(
                "Missing required environment variables: "
                "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME"
            )

        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
            )

            # Test connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info("S3 connection established for bucket: %s", self.bucket_name)

        except NoCredentialsError as exc:
            raise ValueError("Invalid AWS credentials") from exc
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise ValueError(f"S3 bucket not found: {self.bucket_name}") from e
            raise ValueError(f"S3 connection failed: {str(e)}") from e

    def _parse_s3_url(self, url: str) -> tuple[str, str]:
        """
        Parse S3 URL to extract bucket and key.

        Args:
            url: S3 URL (s3://bucket/key or pre-signed URL)

        Returns:
            tuple: (bucket, key)

        Raises:
            ValueError: If URL format is invalid
        """
        parsed = urlparse(url)

        if parsed.scheme == "s3":
            # Direct S3 URL: s3://bucket/key
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            return bucket, key

        if parsed.scheme in ["http", "https"]:
            # Pre-signed URL
            if "s3.amazonaws.com" in parsed.netloc:
                # Virtual-hosted style: https://bucket.s3.amazonaws.com/key
                bucket = parsed.netloc.split(".")[0]
                key = parsed.path.lstrip("/")
            elif parsed.netloc.endswith(".amazonaws.com"):
                # Path style: https://s3.region.amazonaws.com/bucket/key
                path_parts = parsed.path.strip("/").split("/", 1)
                if len(path_parts) != 2:
                    raise ValueError(f"Invalid S3 URL format: {url}")
                bucket, key = path_parts
            else:
                raise ValueError(f"Unrecognized S3 URL format: {url}")

            return bucket, key

        else:
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    async def download_file(self, source_url: str, local_path: str) -> None:
        """
        Download file from S3 to local path.

        Args:
            source_url: S3 URL or pre-signed URL
            local_path: Local file path to save to

        Raises:
            Exception: If download fails
        """
        try:
            if source_url.startswith("http"):
                # Use pre-signed URL directly
                import aiofiles
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.get(source_url) as response:
                        response.raise_for_status()

                        async with aiofiles.open(local_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)

                logger.info("Downloaded from pre-signed URL to: %s", local_path)

            else:
                # Parse S3 URL and download directly
                bucket, key = self._parse_s3_url(source_url)

                self.s3_client.download_file(bucket, key, local_path)
                logger.info("Downloaded s3://%s/%s to: %s", bucket, key, local_path)

        except Exception as e:
            logger.error("Failed to download %s: %s", source_url, str(e))
            raise

    async def upload_file(
        self, local_path: str, s3_key: str, content_type: Optional[str] = None
    ) -> str:
        """
        Upload file to S3 and return pre-signed URL.

        Args:
            local_path: Local file path to upload
            s3_key: S3 key (path) for the file
            content_type: MIME type (auto-detected if None)

        Returns:
            str: Pre-signed URL for the uploaded file

        Raises:
            Exception: If upload fails
        """
        try:
            # Auto-detect content type if not provided
            if content_type is None:
                import mimetypes

                content_type, _ = mimetypes.guess_type(local_path)
                if content_type is None:
                    # Default content types for audio files
                    if local_path.endswith(".wav"):
                        content_type = "audio/wav"
                    elif local_path.endswith(".mp3"):
                        content_type = "audio/mpeg"
                    elif local_path.endswith(".flac"):
                        content_type = "audio/flac"
                    elif local_path.endswith(".ass"):
                        content_type = "text/plain"
                    else:
                        content_type = "application/octet-stream"

            # Upload file
            extra_args = {"ContentType": content_type}
            self.s3_client.upload_file(
                local_path, self.bucket_name, s3_key, ExtraArgs=extra_args
            )

            # Generate pre-signed URL (valid for 24 hours)
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=86400,  # 24 hours
            )

            logger.info("Uploaded %s to s3://%s/%s", local_path, self.bucket_name, s3_key)
            return presigned_url

        except Exception as e:
            logger.error("Failed to upload %s: %s", local_path, str(e))
            raise

    def list_voice_files(self, prefix: str = "voices/") -> list[Dict[str, Any]]:
        """
        List available voice files in the voices directory.

        Args:
            prefix: S3 prefix to search (default: "voices/")

        Returns:
            list: List of voice file metadata
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix
            )

            files = []
            for obj in response.get("Contents", []):
                # Skip directories
                if obj["Key"].endswith("/"):
                    continue

                # Generate pre-signed URL
                presigned_url = self.s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": obj["Key"]},
                    ExpiresIn=3600,  # 1 hour
                )

                files.append(
                    {
                        "key": obj["Key"],
                        "filename": os.path.basename(obj["Key"]),
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "url": presigned_url,
                    }
                )

            logger.info("Found %d voice files", len(files))
            return files

        except Exception as e:
            logger.error("Failed to list voice files: %s", str(e))
            raise

    def delete_old_outputs(self, max_age_hours: int = 24) -> int:
        """
        Delete old output files to save storage.

        Args:
            max_age_hours: Maximum age in hours before deletion

        Returns:
            int: Number of files deleted
        """
        try:
            from datetime import datetime, timedelta, timezone

            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix="output/"
            )

            deleted_count = 0
            for obj in response.get("Contents", []):
                if obj["LastModified"] < cutoff_time:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name, Key=obj["Key"]
                    )
                    deleted_count += 1
                    logger.debug("Deleted old output file: %s", obj['Key'])

            logger.info("Deleted %d old output files", deleted_count)
            return deleted_count

        except Exception as e:
            logger.error("Failed to delete old outputs: %s", str(e))
            return 0

    def get_bucket_usage(self) -> Dict[str, Any]:
        """
        Get bucket usage statistics.

        Returns:
            Dict: Usage statistics
        """
        try:
            # Get object count and total size for voices/ and output/
            stats = {
                "voices": {"count": 0, "size_bytes": 0},
                "output": {"count": 0, "size_bytes": 0},
                "total": {"count": 0, "size_bytes": 0},
            }

            for prefix in ["voices/", "output/"]:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=prefix
                )

                category = prefix.rstrip("/")
                for obj in response.get("Contents", []):
                    if not obj["Key"].endswith("/"):  # Skip directories
                        stats[category]["count"] += 1
                        stats[category]["size_bytes"] += obj["Size"]

            # Calculate totals
            stats["total"]["count"] = (
                stats["voices"]["count"] + stats["output"]["count"]
            )
            stats["total"]["size_bytes"] = (
                stats["voices"]["size_bytes"] + stats["output"]["size_bytes"]
            )

            # Add human-readable sizes
            for category, category_stats in stats.items():
                size_bytes = category_stats["size_bytes"]
                if size_bytes >= 1024**3:  # GB
                    category_stats["size_human"] = f"{size_bytes / (1024**3):.2f} GB"
                elif size_bytes >= 1024**2:  # MB
                    category_stats["size_human"] = f"{size_bytes / (1024**2):.2f} MB"
                elif size_bytes >= 1024:  # KB
                    category_stats["size_human"] = f"{size_bytes / 1024:.2f} KB"
                else:
                    category_stats["size_human"] = f"{size_bytes} bytes"

            logger.info(
                "Bucket usage: %d files, %s", stats['total']['count'], stats['total']['size_human']
            )
            return stats

        except Exception as e:
            logger.error("Failed to get bucket usage: %s", str(e))
            return {}


# Convenience functions for common operations
async def download_voice_sample(url: str, local_path: str) -> None:
    """Download voice sample from S3."""
    s3_manager = S3Manager()
    await s3_manager.download_file(url, local_path)


async def upload_generated_audio(local_path: str, filename: str) -> str:
    """Upload generated audio to S3 and return pre-signed URL."""
    s3_manager = S3Manager()
    s3_key = f"output/{filename}"
    return await s3_manager.upload_file(local_path, s3_key)


def cleanup_old_files(max_age_hours: int = 24) -> int:
    """Clean up old output files."""
    s3_manager = S3Manager()
    return s3_manager.delete_old_outputs(max_age_hours)
