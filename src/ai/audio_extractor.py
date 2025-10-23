"""
音频提取模块
负责从视频中提取音频文件
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


class AudioExtractor:
    """音频提取器"""
    
    def __init__(self):
        pass
    
    def check_file_exists(self, file_path: str) -> bool:
        """检查文件是否存在且不为空"""
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except:
            return False
    
    def extract_audio(self, video_path: str, video_folder: Path, video_name: str = None) -> Optional[str]:
        """从视频中提取音频"""
        try:
            # 生成音频文件名
            if video_name:
                # 确保video_name是字符串，如果是列表则取第一个元素
                if isinstance(video_name, list):
                    video_name = video_name[0]
                audio_filename = f"{video_name}_audio.wav"
            else:
                # 从视频文件名生成音频文件名
                video_name = Path(video_path).stem
                audio_filename = f"{video_name}_audio.wav"
            
            audio_path = video_folder / audio_filename
            
            # 检查音频文件是否已存在
            if self.check_file_exists(str(audio_path)):
                print(f"音频文件已存在，跳过提取: {audio_path}")
                return str(audio_path)
            
            print("正在提取音频...")
            
            # 使用ffmpeg提取音频
            cmd = [
                "ffmpeg", "-i", video_path, 
                "-vn", "-acodec", "pcm_s16le", 
                "-ar", "16000", "-ac", "1", 
                "-y", str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"音频提取失败: {result.stderr}")
                return None
            
            print(f"音频提取成功: {audio_path}")
            return str(audio_path)
            
        except Exception as e:
            print(f"音频提取失败: {str(e)}")
            return None
