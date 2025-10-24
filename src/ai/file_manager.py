"""
文件管理模块
负责文件保存、检查、清理等操作
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, List


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
    
    def find_file_by_prefix(self, directory: Path, prefix: str, extensions: List[str]) -> Optional[Path]:
        """根据前缀查找文件（通用方法）"""
        try:
            # 首先尝试精确前缀匹配
            for ext in extensions:
                pattern = f"{prefix}*{ext}"
                matches = list(directory.glob(pattern))
                if matches:
                    # 返回第一个匹配的文件
                    return matches[0]
            
            # 如果精确匹配失败，尝试智能匹配
            return self._smart_file_match(directory, prefix, extensions)
            
        except Exception as e:
            print(f"前缀匹配查找失败: {str(e)}")
            return None
    
    def _smart_file_match(self, directory: Path, prefix: str, extensions: List[str]) -> Optional[Path]:
        """智能文件匹配，处理文件名被截断的情况"""
        try:
            # 获取所有相关扩展名的文件
            all_files = []
            for ext in extensions:
                all_files.extend(directory.glob(f"*{ext}"))
            
            # 计算前缀的相似度，找到最匹配的文件
            best_match = None
            best_score = 0
            
            for file_path in all_files:
                file_stem = file_path.stem
                
                # 移除文件后缀（如_audio, _transcription等）
                clean_stem = self._clean_file_stem(file_stem)
                
                # 计算相似度
                score = self._calculate_similarity(prefix, clean_stem)
                
                if score > best_score and score > 0.7:  # 相似度阈值
                    best_score = score
                    best_match = file_path
            
            return best_match
            
        except Exception as e:
            print(f"智能匹配失败: {str(e)}")
            return None
    
    def _clean_file_stem(self, file_stem: str) -> str:
        """清理文件名，移除常见的后缀"""
        # 移除常见的后缀
        suffixes_to_remove = ['_audio', '_transcription', '_summary']
        for suffix in suffixes_to_remove:
            if file_stem.endswith(suffix):
                file_stem = file_stem[:-len(suffix)]
                break
        return file_stem
    
    def _calculate_similarity(self, prefix: str, target: str) -> float:
        """计算两个字符串的相似度"""
        if not prefix or not target:
            return 0.0
        
        # 如果目标字符串以前缀开头，返回高相似度
        if target.startswith(prefix):
            return 1.0
        
        # 如果前缀以目标字符串开头，返回较高相似度
        if prefix.startswith(target):
            return 0.9
        
        # 计算最长公共子序列的长度
        common_length = self._longest_common_subsequence_length(prefix, target)
        
        # 计算相似度
        max_length = max(len(prefix), len(target))
        similarity = common_length / max_length if max_length > 0 else 0.0
        
        return similarity
    
    def _longest_common_subsequence_length(self, s1: str, s2: str) -> int:
        """计算两个字符串的最长公共子序列长度"""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        return dp[m][n]
    
    def find_audio_file(self, directory: Path, video_name: str) -> Optional[Path]:
        """查找音频文件"""
        return self.find_file_by_prefix(directory, video_name, ['.wav'])
    
    def find_transcription_file(self, directory: Path, video_name: str) -> Optional[Path]:
        """查找转录文件"""
        return self.find_file_by_prefix(directory, video_name, ['_transcription.txt'])
    
    def find_summary_file(self, directory: Path, video_name: str) -> Optional[Path]:
        """查找总结文件"""
        return self.find_file_by_prefix(directory, video_name, ['_summary.txt'])
    
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
