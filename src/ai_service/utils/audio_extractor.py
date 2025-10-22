"""
音频提取模块
负责从视频中提取音频文件
使用S3存储，video_id作为文件名
"""

import os
import subprocess
import tempfile
import asyncio
from pathlib import Path
from typing import Optional
from .s3_client import S3Client  # 同一目录，不需要修改
from .task_queue import run_io_blocking, run_io_bound


class AudioExtractor:
    """音频提取器"""
    
    def __init__(self):
        self.s3_client = S3Client()
    
    def check_file_exists(self, file_path: str) -> bool:
        """检查文件是否存在且不为空"""
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except:
            return False
    
    def extract_audio(self, video_path: str, video_id: str, force_extract: bool = False) -> Optional[str]:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件本地路径
            video_id: 视频ID，用作文件名
            force_extract: 是否强制重新提取
            
        Returns:
            音频文件本地路径
        """
        try:
            # S3中的音频路径
            s3_audio_path = f"videos/{video_id}_audio.wav"
            
            # 检查S3中是否已存在音频文件
            if not force_extract and self.s3_client.file_exists(s3_audio_path):
                print(f"S3中已存在音频文件，下载到临时目录: {s3_audio_path}")
                local_audio_path = self._download_from_s3_to_temp(s3_audio_path, video_id)
                if local_audio_path:
                    return local_audio_path
            
            # 本地临时音频文件
            temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
            temp_dir.mkdir(exist_ok=True)
            audio_path = temp_dir / f"{video_id}_audio.wav"
            
            print(f"正在提取音频: {video_path} -> {audio_path}")
            
            # 使用ffmpeg提取音频
            cmd = [
                "ffmpeg", "-i", video_path, 
                "-vn", "-acodec", "pcm_s16le", 
                "-ar", "16000", "-ac", "1", 
                "-y", str(audio_path)
            ]
            
            # 为 ffmpeg 添加超时，防止卡死
            result = run_io_blocking(subprocess.run, cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"音频提取失败: {result.stderr}")
                return None
            
            print(f"音频提取成功: {audio_path}")
            
            # 上传到S3
            if run_io_blocking(self.s3_client.upload_file, str(audio_path), s3_audio_path):
                print(f"音频已上传到S3: {s3_audio_path}")
            
            return str(audio_path)
            
        except Exception as e:
            print(f"音频提取失败: {str(e)}")
            return None
    
    def _download_from_s3_to_temp(self, s3_path: str, video_id: str) -> Optional[str]:
        """从S3下载音频文件到临时目录"""
        import tempfile
        
        temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
        temp_dir.mkdir(exist_ok=True)
        
        local_path = temp_dir / f"{video_id}_audio.wav"
        
        if run_io_blocking(self.s3_client.download_file, s3_path, str(local_path)):
            return str(local_path)
        else:
            return None

    async def extract_audio_async(self, video_path: str, video_id: str, force_extract: bool = False) -> Optional[str]:
        """异步版本：在共享 IO 线程池中执行阻塞步骤，避免阻塞事件循环。"""
        try:
            s3_audio_path = f"videos/{video_id}_audio.wav"
            
            # S3 命中则直接下载
            exists = await run_io_bound(self.s3_client.file_exists, s3_audio_path)
            if not force_extract and exists:
                print(f"S3中已存在音频文件，下载到临时目录: {s3_audio_path}")
                local_audio_path = await self._download_from_s3_to_temp_async(s3_audio_path, video_id)
                if local_audio_path:
                    return local_audio_path
            
            temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
            temp_dir.mkdir(exist_ok=True)
            audio_path = temp_dir / f"{video_id}_audio.wav"
            
            print(f"正在提取音频: {video_path} -> {audio_path}")
            cmd = [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                "-y", str(audio_path)
            ]
            # 在线程池中运行阻塞的 subprocess.run
            # 为 ffmpeg 添加超时，防止卡死
            result = await run_io_bound(subprocess.run, cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"音频提取失败: {result.stderr}")
                return None
            
            print(f"音频提取成功: {audio_path}")
            uploaded = await run_io_bound(self.s3_client.upload_file, str(audio_path), s3_audio_path)
            if uploaded:
                print(f"音频已上传到S3: {s3_audio_path}")
            return str(audio_path)
        except Exception as e:
            print(f"音频提取失败: {str(e)}")
            return None

    async def _download_from_s3_to_temp_async(self, s3_path: str, video_id: str) -> Optional[str]:
        """异步：从S3下载音频文件到临时目录"""
        try:
            temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
            temp_dir.mkdir(exist_ok=True)
            local_path = temp_dir / f"{video_id}_audio.wav"
            ok = await run_io_bound(self.s3_client.download_file, s3_path, str(local_path))
            return str(local_path) if ok else None
        except Exception:
            return None

