#!/usr/bin/env python3
"""
S3 Utilities for Spark-TTS Runpod Serverless
Handles file uploads/downloads with pre-signed URLs
"""

import os
import logging
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from typing import Optional
from datetime import timedelta

logger = logging.getLogger(__name__)


class S3Handler:
    """Handle S3 operations for voice references and audio output"""
    
    def __init__(self, bucket_name: str, access_key: str, secret_key: str, region: str = 'us-east-1', endpoint_url: str = None):
        """
        Initialize S3 client
        
        Args:
            bucket_name: S3 bucket name
            access_key: AWS access key ID
            secret_key: AWS secret access key
            region: AWS region
            endpoint_url: Custom S3 endpoint URL (for Backblaze B2 or other S3-compatible services)
        """
        self.bucket_name = bucket_name
        self.region = region
        
        try:
            # Configure S3 client with optional custom endpoint
            client_config = {
                'aws_access_key_id': access_key,
                'aws_secret_access_key': secret_key,
                'region_name': region
            }
            
            # Add endpoint URL if provided (for Backblaze B2 or other S3-compatible services)
            if endpoint_url:
                client_config['endpoint_url'] = endpoint_url
                
            self.s3_client = boto3.client('s3', **client_config)
            logger.info(f"S3 client initialized for bucket: {bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def upload_file(self, local_path: str, s3_key: str, expiration: int = 3600) -> str:
        """
        Upload file to S3 and return pre-signed URL
        
        Args:
            local_path: Path to local file
            s3_key: S3 object key
            expiration: URL expiration time in seconds
            
        Returns:
            Pre-signed URL for the uploaded file
        """
        try:
            # Upload file
            self.s3_client.upload_file(local_path, self.bucket_name, s3_key)
            logger.info(f"File uploaded to s3://{self.bucket_name}/{s3_key}")
            
            # Generate pre-signed URL
            url = self.generate_presigned_url(s3_key, 'get_object', expiration)
            return url
            
        except FileNotFoundError:
            logger.error(f"File not found: {local_path}")
            raise
        except NoCredentialsError:
            logger.error("AWS credentials not available")
            raise
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise
    
    def download_file(self, s3_url: str, local_path: str) -> str:
        """
        Download file from S3 URL or S3 path
        
        Args:
            s3_url: S3 URL or s3:// path
            local_path: Local path to save file
            
        Returns:
            Path to downloaded file
        """
        try:
            # Parse S3 URL to get bucket and key
            if s3_url.startswith('s3://'):
                # Direct S3 path
                parts = s3_url[5:].split('/', 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ''
            elif s3_url.startswith('http'):
                # Pre-signed URL - download directly
                import urllib.request
                urllib.request.urlretrieve(s3_url, local_path)
                logger.info(f"File downloaded from URL to: {local_path}")
                return local_path
            else:
                # Assume it's just the key
                bucket = self.bucket_name
                key = s3_url
            
            # Download from S3
            self.s3_client.download_file(bucket, key, local_path)
            logger.info(f"File downloaded from s3://{bucket}/{key} to: {local_path}")
            return local_path
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"Object not found: {s3_url}")
            else:
                logger.error(f"Failed to download file: {e}")
            raise
        except Exception as e:
            logger.error(f"Download error: {e}")
            raise
    
    def generate_presigned_url(self, s3_key: str, operation: str = 'get_object', 
                               expiration: int = 3600) -> Optional[str]:
        """
        Generate a pre-signed URL for S3 object
        
        Args:
            s3_key: S3 object key
            operation: S3 operation (get_object or put_object)
            expiration: URL expiration time in seconds
            
        Returns:
            Pre-signed URL or None if error
        """
        try:
            params = {'Bucket': self.bucket_name, 'Key': s3_key}
            
            url = self.s3_client.generate_presigned_url(
                ClientMethod=operation,
                Params=params,
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated pre-signed URL for {s3_key} (expires in {expiration}s)")
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate pre-signed URL: {e}")
            return None
    
    def list_voice_references(self, prefix: str = 'voices/') -> list:
        """
        List available voice reference files
        
        Args:
            prefix: S3 prefix for voice files
            
        Returns:
            List of voice reference files
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'url': self.generate_presigned_url(obj['Key'])
                    })
            
            logger.info(f"Found {len(files)} voice reference files")
            return files
            
        except ClientError as e:
            logger.error(f"Failed to list voice references: {e}")
            return []
    
    def check_bucket_access(self) -> bool:
        """
        Check if bucket is accessible
        
        Returns:
            True if accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} is accessible")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"Bucket {self.bucket_name} not found")
            elif error_code == '403':
                logger.error(f"Access denied to bucket {self.bucket_name}")
            else:
                logger.error(f"Bucket access check failed: {e}")
            return False
    
    def create_bucket_structure(self):
        """Create standard bucket structure for Spark-TTS"""
        prefixes = ['voices/', 'output/', 'output/subtitles/']
        
        for prefix in prefixes:
            try:
                # Create a placeholder object to establish the prefix
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=f"{prefix}.placeholder",
                    Body=b'',
                    ContentType='text/plain'
                )
                logger.info(f"Created prefix: {prefix}")
            except Exception as e:
                logger.error(f"Failed to create prefix {prefix}: {e}")