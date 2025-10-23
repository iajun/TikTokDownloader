"""
文件管理模块
负责文件保存、检查、清理等操作
"""

import os
import tempfile
from pathlib import Path
from typing import Optional


class FileManager:
    """文件管理器"""
    
    def __init__(self):
        pass
    
    def check_file_exists(self, file_path: str) -> bool:
        """检查文件是否存在且不为空"""
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except:
            return False
    
    def save_text_to_file(self, text: str, filename: str, video_folder: Path, 
                         video_name: str = None, force: bool = False) -> Optional[str]:
        """保存文本到文件"""
        try:
            # 生成文件名
            if video_name:
                # 确保video_name是字符串，如果是列表则取第一个元素
                if isinstance(video_name, list):
                    video_name = video_name[0]
                text_filename = f"{video_name}_{filename}.txt"
            else:
                text_filename = f"{filename}.txt"
            
            text_path = video_folder / text_filename
            
            # 检查文件是否已存在
            if self.check_file_exists(str(text_path)) and not force:
                print(f"文本文件已存在，跳过保存: {text_path}")
                return str(text_path)
            
            # 保存文本
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            if force and self.check_file_exists(str(text_path)):
                print(f"文本已覆盖保存: {text_path}")
            else:
                print(f"文本已保存: {text_path}")
            return str(text_path)
            
        except Exception as e:
            print(f"保存文本失败: {str(e)}")
            return None
    
    def save_result_to_file(self, result: dict, file_path: str):
        """保存结果到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("抖音视频AI总结结果\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"视频链接: {result['url']}\n")
                f.write(f"视频路径: {result['video_path']}\n\n")
                
                if result["transcription"]:
                    f.write("语音转文字:\n")
                    f.write("-" * 30 + "\n")
                    f.write(result["transcription"] + "\n\n")
                
                if result["summary"]:
                    f.write("AI总结:\n")
                    f.write("-" * 30 + "\n")
                    f.write(result["summary"] + "\n")
        except Exception as e:
            print(f"保存结果失败: {str(e)}")
    
    def cleanup_temp_files(self, file_paths: list, keep_files: bool = False):
        """清理临时文件"""
        if keep_files:
            return
        
        for file_path in file_paths:
            if file_path and file_path.startswith(tempfile.gettempdir()):
                try:
                    os.remove(file_path)
                    # 尝试删除空目录
                    dir_path = os.path.dirname(file_path)
                    if os.path.exists(dir_path) and not os.listdir(dir_path):
                        os.rmdir(dir_path)
                except:
                    pass
