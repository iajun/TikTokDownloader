"""
MinIO S3客户端
用于存储下载的音视频文件
"""

from minio import Minio
from minio.error import S3Error
from pathlib import Path
import os
from typing import Optional, BinaryIO
import io
from datetime import timedelta
from dotenv import load_dotenv

# 加载 .env 文件
BASE_DIR = Path(__file__).parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)


class S3Client:
    """MinIO S3客户端"""
    
    def __init__(self):
        """初始化S3客户端"""
        self.endpoint = os.getenv("S3_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
        self.secure = os.getenv("S3_SECURE", "false").lower() == "true"
        self.bucket_name = os.getenv("S3_BUCKET", "ai-service")
        
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # 确保bucket存在
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """确保bucket存在"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"Created bucket: {self.bucket_name}")
        except S3Error as e:
            print(f"Error creating bucket: {e}")
    
    def upload_file(self, local_path: str, s3_path: str) -> bool:
        """上传文件到S3"""
        try:
            if not os.path.exists(local_path):
                print(f"Local file not found: {local_path}")
                return False
            
            file_size = os.path.getsize(local_path)
            
            with open(local_path, "rb") as file_data:
                self.client.put_object(
                    self.bucket_name,
                    s3_path,
                    file_data,
                    length=file_size
                )
            
            print(f"Uploaded {local_path} to s3://{self.bucket_name}/{s3_path}")
            return True
            
        except S3Error as e:
            print(f"Error uploading file: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
    
    def download_file(self, s3_path: str, local_path: str) -> bool:
        """从S3下载文件"""
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            self.client.fget_object(self.bucket_name, s3_path, local_path)
            
            print(f"Downloaded s3://{self.bucket_name}/{s3_path} to {local_path}")
            return True
            
        except S3Error as e:
            print(f"Error downloading file: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
    
    def delete_file(self, s3_path: str) -> bool:
        """从S3删除文件"""
        try:
            self.client.remove_object(self.bucket_name, s3_path)
            print(f"Deleted s3://{self.bucket_name}/{s3_path}")
            return True
            
        except S3Error as e:
            print(f"Error deleting file: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False
    
    def get_file_url(self, s3_path: str, expires_seconds: int = 3600) -> Optional[str]:
        """获取文件的预签名URL"""
        try:
            # MinIO 需要 timedelta 对象而不是整数
            expires = timedelta(seconds=expires_seconds)
            url = self.client.presigned_get_object(
                self.bucket_name,
                s3_path,
                expires=expires
            )
            return url
            
        except S3Error as e:
            print(f"Error generating presigned URL: {e}")
            return None
    
    def file_exists(self, s3_path: str) -> bool:
        """检查文件是否存在"""
        try:
            self.client.stat_object(self.bucket_name, s3_path)
            return True
        except S3Error:
            return False
        except Exception as e:
            print(f"Error checking file existence: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> list:
        """列出bucket中的文件"""
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"Error listing files: {e}")
            return []
    
    def upload_from_memory(self, data: bytes, s3_path: str, content_type: str = "application/octet-stream") -> bool:
        """从内存上传文件"""
        try:
            data_stream = io.BytesIO(data)
            self.client.put_object(
                self.bucket_name,
                s3_path,
                data_stream,
                length=len(data),
                content_type=content_type
            )
            print(f"Uploaded to s3://{self.bucket_name}/{s3_path}")
            return True
        except S3Error as e:
            print(f"Error uploading from memory: {e}")
            return False
