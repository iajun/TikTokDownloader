"""
语音转文字服务模块
负责将音频文件转换为文字
"""

import whisper
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List
from pathlib import Path
from .file_manager import FileManager


class TranscriptionService:
    """语音转文字服务"""
    
    def __init__(self, model_name: str = "base"):
        """初始化语音转文字服务"""
        self.whisper_model = None
        self.model_name = model_name
        self.executor = ThreadPoolExecutor(max_workers=2)  # 限制并发转文字任务数
        self.file_manager = FileManager()
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
    
    def convert_punctuation_to_chinese(self, text: str) -> str:
        """将英文标点符号转换为中文标点符号"""
        # 使用字符串替换方法，避免特殊字符问题
        result = text
        result = result.replace(',', '，')
        result = result.replace('.', '。')
        result = result.replace('!', '！')
        result = result.replace('?', '？')
        result = result.replace(':', '：')
        result = result.replace(';', '；')
        result = result.replace('"', '"')
        result = result.replace("'", '\u2019')
        result = result.replace('(', '（')
        result = result.replace(')', '）')
        result = result.replace('[', '【')
        result = result.replace(']', '】')
        result = result.replace('{', '{')
        result = result.replace('}', '}')
        result = result.replace('-', '—')
        result = result.replace('...', '……')
        
        return result
    
    def segment_text_by_period(self, text: str, min_length: int = 20, max_length: int = 200) -> str:
        """根据句号进行分段，每段最少min_length字，最多max_length字"""
        # 先按句号分割
        sentences = text.split('。')
        
        segments = []
        current_segment = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 如果当前句子加上当前段落会超过最大长度，先保存当前段落
            if current_segment and len(current_segment + sentence + '。') > max_length:
                if len(current_segment) >= min_length:
                    segments.append(current_segment)
                    current_segment = sentence + '。'
                else:
                    # 如果当前段落太短，继续添加句子
                    current_segment += sentence + '。'
            else:
                # 添加句子到当前段落
                if current_segment:
                    current_segment += sentence + '。'
                else:
                    current_segment = sentence
        
        # 处理最后一个段落
        if current_segment:
            # 移除末尾多余的句号
            if current_segment.endswith('。'):
                current_segment = current_segment[:-1]
            if len(current_segment) >= min_length:
                segments.append(current_segment)
            elif segments:
                # 如果最后一段太短，合并到前一段
                segments[-1] += current_segment
        
        # 用换行符连接各段
        return '\n\n'.join(segments)
    
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
            elif transcription_file_path:
                # 如果提供的路径不存在，尝试前缀匹配查找
                audio_file = Path(audio_path)
                audio_name = audio_file.stem.replace('_audio', '')  # 移除_audio后缀
                directory = audio_file.parent
                
                existing_transcription = self.file_manager.find_transcription_file(
                    directory, 
                    audio_name
                )
                
                if existing_transcription and self.check_file_exists(str(existing_transcription)):
                    print(f"通过前缀匹配找到转录文件: {existing_transcription}")
                    with open(existing_transcription, 'r', encoding='utf-8') as f:
                        existing_text = f.read().strip()
                    if existing_text:
                        print("使用前缀匹配找到的转录文本")
                        return existing_text
            
            print("正在转换音频为文字...")
            
            # 使用Whisper进行语音识别（同步方法）
            result = self.whisper_model.transcribe(audio_path, language="zh", initial_prompt="语音转文本，请在合适位置断句、分段，每段不要超过100字，并加上中文标点标号。")
            text = result["text"].strip()
            
            if text:
                print("语音转文字成功")
                print(f"原始识别内容: {text}")
                
                # 转换英文标点为中文标点
                text = self.convert_punctuation_to_chinese(text)
                print("已转换英文标点为中文标点")
                
                # 根据句号进行分段
                text = self.segment_text_by_period(text, min_length=20, max_length=200)
                print("已根据句号进行分段处理")
                
                print(f"最终处理内容: {text}")
                return text
            else:
                print("未识别到有效内容")
                return None
                
        except Exception as e:
            print(f"语音转文字失败: {str(e)}")
            return None
    
    async def transcribe_async(self, audio_path: str, transcription_file_path: Optional[str] = None) -> Optional[str]:
        """异步语音转文字（在线程池中执行）"""
        try:
            # 在线程池中执行同步的转文字操作
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                self.executor, 
                self.transcribe_audio, 
                audio_path, 
                transcription_file_path
            )
            return text
        except Exception as e:
            print(f"异步语音转文字失败: {str(e)}")
            return None
    
    def __del__(self):
        """清理资源"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)