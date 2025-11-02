"""
语音转文字服务模块
负责将音频文件转换为文字
使用S3存储，video_id作为文件名
"""

import whisper
import tempfile
from pathlib import Path
from typing import Optional
from ..utils import S3Client
import json
from ..utils.task_queue import run_cpu_blocking


# 进程内 Whisper 模型缓存，确保每个子进程仅加载一次模型
_CPU_MODELS = {}


def _cpu_whisper_transcribe(audio_path: str, model_name: str) -> str:
    """在子进程中执行 Whisper 转录，并在该进程内缓存模型。"""
    model = _CPU_MODELS.get(model_name)
    if model is None:
        model = whisper.load_model(model_name)
        _CPU_MODELS[model_name] = model
    result = model.transcribe(audio_path, language="zh", initial_prompt="")
    return result.get("text", "").strip()


class TranscriptionService:
    """语音转文字服务"""
    
    def __init__(self, model_name: str = "large-v3-turbo"):
        """初始化语音转文字服务"""
        self.whisper_model = None
        self.model_name = model_name
        self.s3_client = S3Client()
        self._load_model()
    
    def _load_model(self):
        """加载Whisper模型"""
        try:
            print(f"正在加载Whisper模型: {self.model_name}")
            self.whisper_model = whisper.load_model(self.model_name)
            print("Whisper模型加载成功")
        except Exception as e:
            print(f"加载Whisper模型失败: {str(e)}")
            raise
    
    def transcribe(self, audio_path: str, video_id: str) -> Optional[str]:
        """同步语音转文字（使用 CPU 进程池执行 Whisper 转录）"""
        try:
            print(f"正在转换音频为文字(进程池): {audio_path}")
            raw_text = run_cpu_blocking(_cpu_whisper_transcribe, audio_path, self.model_name)
            text = (raw_text or "").strip()
            if text:
                print("语音转文字成功")
                return text
            print("未识别到有效内容")
            return None
        except Exception as e:
            print(f"语音转文字失败: {str(e)}")
            return None

