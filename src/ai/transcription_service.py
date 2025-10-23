"""
语音转文字服务模块
负责将音频文件转换为文字
"""

import whisper
from typing import Optional


class TranscriptionService:
    """语音转文字服务"""
    
    def __init__(self, model_name: str = "base"):
        """初始化语音转文字服务"""
        self.whisper_model = None
        self.model_name = model_name
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
    
    def check_file_exists(self, file_path: str) -> bool:
        """检查文件是否存在且不为空"""
        try:
            import os
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except:
            return False
    
    def transcribe_audio(self, audio_path: str, transcription_file_path: str = None) -> Optional[str]:
        """将音频转换为文字"""
        try:
            # 如果提供了转录文件路径，先检查文件是否已存在
            if transcription_file_path and self.check_file_exists(transcription_file_path):
                print(f"转录文本文件已存在，跳过转文字: {transcription_file_path}")
                # 读取已存在的文件内容
                with open(transcription_file_path, 'r', encoding='utf-8') as f:
                    existing_text = f.read().strip()
                if existing_text:
                    print("使用已存在的转录文本")
                    return existing_text
                else:
                    print("已存在的文件为空，重新进行转文字")
            
            print("正在转换音频为文字...")
            
            # 使用Whisper进行语音识别
            result = self.whisper_model.transcribe(audio_path, language="zh")
            text = result["text"].strip()
            
            if text:
                print("语音转文字成功")
                print(f"识别内容: {text}")
                return text
            else:
                print("未识别到有效内容")
                return None
                
        except Exception as e:
            print(f"语音转文字失败: {str(e)}")
            return None
