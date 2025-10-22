#!/usr/bin/env python3
"""
抖音视频AI总结工具
功能：
1. 下载抖音视频
2. 提取音频并转换为文字
3. 使用DeepSeek AI进行内容总结

依赖安装：
pip install openai-whisper requests openai
"""

import argparse
import asyncio
import os
import sys
import tempfile
import json
from pathlib import Path
from typing import Optional

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import whisper
    import requests
    from openai import OpenAI
except ImportError as e:
    print(f"缺少依赖包: {e}")
    print("请运行: pip install openai-whisper requests openai")
    sys.exit(1)

from src.application import TikTokDownloader
from src.application.main_terminal import TikTok


def load_api_key_from_settings() -> Optional[str]:
    """从Volume/settings.json中读取DeepSeek API key"""
    try:
        # 查找Volume目录
        volume_paths = [
            Path(__file__).parent / "Volume" / "settings.json",
            Path(__file__).parent.parent / "Volume" / "settings.json",
            Path.cwd() / "Volume" / "settings.json"
        ]
        
        settings_file = None
        for path in volume_paths:
            if path.exists():
                settings_file = path
                break
        
        if not settings_file:
            print("未找到Volume/settings.json文件")
            return None
        
        print(f"读取设置文件: {settings_file}")
        
        # 读取设置文件
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # 获取API key
        api_key = settings.get("deepseek_api_key", "")
        if api_key:
            print("从settings.json中读取到DeepSeek API key")
            return api_key
        else:
            print("settings.json中未配置deepseek_api_key")
            return None
            
    except Exception as e:
        print(f"读取settings.json失败: {str(e)}")
        return None


class VideoAISummarizer:
    """视频AI总结器"""
    
    def __init__(self, deepseek_api_key: Optional[str] = None):
        self.downloader = None
        self.tiktok_instance = None
        self.whisper_model = None
        self.deepseek_client = None
        
        # 初始化Whisper模型
        print("正在加载Whisper模型...")
        self.whisper_model = whisper.load_model("base")
        
        # 初始化DeepSeek客户端
        if deepseek_api_key:
            self.deepseek_client = OpenAI(
                api_key=deepseek_api_key,
                base_url="https://api.deepseek.com"
            )
        else:
            print("警告: 未提供DeepSeek API密钥，将跳过AI总结功能")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.downloader = TikTokDownloader()
        await self.downloader.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.downloader:
            await self.downloader.__aexit__(exc_type, exc_val, exc_tb)
    
    def detect_platform(self, url: str) -> str:
        """检测URL所属平台"""
        url_lower = url.lower()
        if 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'douyin.com' in url_lower:
            return 'douyin'
        else:
            return 'douyin'  # 默认抖音
    
    async def download_video(self, url: str, output_dir: Optional[str] = None, force_download: bool = False) -> tuple[Optional[str], Optional[list]]:
        """下载视频并返回视频文件路径"""
        try:
            print(f"开始下载视频: {url}")
            
            # 检测平台
            platform = self.detect_platform(url)
            print(f"检测到平台: {platform}")
            
            # 初始化设置
            self.downloader.project_info()
            self.downloader.check_config()
            await self.downloader.check_settings(False)
            
            # 设置输出目录
            if output_dir:
                self.downloader.parameter.root = Path(output_dir)
                print(f"输出目录: {output_dir}")
            
            # 创建TikTok实例
            self.tiktok_instance = TikTok(
                self.downloader.parameter, 
                self.downloader.database
            )
            
            # 提取视频ID
            if platform == 'tiktok':
                ids = await self.tiktok_instance.links_tiktok.run(url)
            else:
                ids = await self.tiktok_instance.links.run(url)
            
            if not ids:
                raise Exception(f"无法从URL提取视频ID: {url}")
            
            print(f"提取到视频ID: {ids}")
            
            # 创建记录器并获取视频详情
            root, params, logger = self.tiktok_instance.record.run(self.downloader.parameter)
            async with logger(root, console=self.downloader.console, **params) as record:
                # 使用正常的下载流程，但跳过已下载检查（如果force_download=True）
                if force_download:
                    # 强制下载模式：先获取detail_data，然后手动下载
                    detail_data = await self.tiktok_instance._handle_detail(ids, platform == 'tiktok', record, api=True)
                else:
                    # 正常模式：使用完整的下载流程
                    detail_data = await self.tiktok_instance._handle_detail(ids, platform == 'tiktok', record, api=True)
            
            # 从detail_data中提取视频名称
            video_name = self._get_video_name_from_detail_data(detail_data, ids)
            
            # 检查视频是否已经下载过（除非强制下载）
            if not force_download and await self._is_video_downloaded(ids):
                print(f"视频 {ids} 已经下载过，跳过下载步骤")
                # 查找已下载的视频文件
                video_path = await self._find_downloaded_video(ids, platform == 'tiktok', video_name)
                if video_path:
                    print(f"找到已下载的视频: {video_path}")
                    return video_path, detail_data
                else:
                    print("警告: 数据库中记录已下载，但未找到视频文件")
            
            # 首先尝试查找已下载的视频文件（除非强制下载）
            if not force_download:
                video_path = await self._find_downloaded_video(ids, platform == 'tiktok', video_name)
                if video_path:
                    print(f"视频下载成功: {video_path}")
                    return video_path, detail_data
            else:
                print("强制下载模式：忽略已存在的视频文件")
            
            # 如果没找到文件，使用正常的下载流程
            if detail_data and len(detail_data) > 0:
                print(f"获取到detail_data，长度: {len(detail_data)}")
                
                # 如果是强制下载模式，先清理已存在的文件和记录
                if force_download:
                    print("强制下载模式：清理已存在的文件和记录...")
                    await self._clean_existing_files_and_records(ids, platform == 'tiktok', video_name)
                
                # 使用正常的下载流程
                print("使用正常的下载流程下载视频...")
                await self.tiktok_instance.downloader.run(detail_data, "detail", tiktok=(platform == 'tiktok'))
                
                # 下载完成后，再次查找视频文件
                video_path = await self._find_downloaded_video(ids, platform == 'tiktok', video_name)
                if video_path:
                    print(f"视频下载成功: {video_path}")
                    return video_path, detail_data
                else:
                    print("下载完成但未找到视频文件")
            else:
                print("detail_data为空或长度为0")
            
            raise Exception("未找到下载的视频文件")
            
        except Exception as e:
            print(f"下载视频失败: {str(e)}")
            return None, None
    
    async def _is_video_downloaded(self, ids: str) -> bool:
        """检查视频是否已经在数据库中记录为已下载"""
        try:
            return await self.downloader.database.has_download_data(ids)
        except Exception as e:
            print(f"检查下载记录失败: {str(e)}")
            return False
    
    def _get_video_name_from_detail_data(self, detail_data: list, ids: str) -> str:
        """从detail_data中提取视频名称，使用与download.py相同的命名规则"""
        try:
            if detail_data and len(detail_data) > 0:
                video_data = detail_data[0]
                if isinstance(video_data, dict):
                    # 使用与download.py相同的命名逻辑
                    name = self._generate_detail_name(video_data)
                    print(f"使用name_format生成视频名称: {name}")
                    return name
                else:
                    print(f"detail_data[0] 不是字典格式: {type(video_data)}")
                    return ids
            else:
                print("detail_data为空")
                return ids
        except Exception as e:
            print(f"提取视频名称失败: {str(e)}")
            return ids
    
    def _generate_detail_name(self, data: dict) -> str:
        """生成作品文件名称，使用与download.py相同的逻辑"""
        try:
            # 获取name_format配置
            name_format = self.downloader.parameter.name_format
            split = self.downloader.parameter.split
            name_length = self.downloader.parameter.name_length
            
            print(f"name_format: {name_format}")
            print(f"split: {split}")
            print(f"name_length: {name_length}")
            
            # 根据name_format生成名称
            name_parts = []
            for field in name_format:
                if field in data:
                    value = str(data[field])
                    # 如果是create_time，需要格式化
                    if field == "create_time" and value:
                        try:
                            from datetime import datetime
                            # 假设create_time是时间戳
                            if value.isdigit():
                                dt = datetime.fromtimestamp(int(value))
                                value = dt.strftime(self.downloader.parameter.date_format)
                        except:
                            pass
                    name_parts.append(value)
                else:
                    print(f"字段 {field} 不存在于数据中")
            
            # 使用split连接
            name = split.join(name_parts)
            
            # 使用cleaner过滤名称
            name = self.downloader.parameter.CLEANER.filter_name(name, data.get("id", ""))
            
            # 使用beautify_string处理
            from src.tools import beautify_string
            name = beautify_string(name, name_length)
            
            print(f"生成的视频名称: {name}")
            return name
            
        except Exception as e:
            print(f"生成视频名称失败: {str(e)}")
            return data.get("id", "unknown")
    
    async def _clean_existing_files_and_records(self, ids: str, is_tiktok: bool = False, video_name: str = None):
        """清理已存在的文件和数据库记录"""
        try:
            print(f"清理视频 {ids} 的已存在文件和记录...")
            
            # 1. 删除数据库记录
            try:
                await self.downloader.database.delete_download_data(ids)
                print(f"已删除数据库记录: {ids}")
            except Exception as e:
                print(f"删除数据库记录失败: {str(e)}")
            
            # 2. 删除已存在的视频文件
            video_path = await self._find_downloaded_video(ids, is_tiktok, video_name)
            if video_path:
                try:
                    os.remove(video_path)
                    print(f"已删除视频文件: {video_path}")
                except Exception as e:
                    print(f"删除视频文件失败: {str(e)}")
            
            # 3. 删除相关的音频和文本文件
            download_dir = Path(self.downloader.parameter.root) / "Download"
            
            # 如果有视频名称，优先按名称清理
            if video_name:
                video_folder = download_dir / video_name
                if video_folder.exists():
                    try:
                        # 删除文件夹中的所有文件
                        for file_path in video_folder.iterdir():
                            if file_path.is_file():
                                file_path.unlink()
                                print(f"已删除文件: {file_path}")
                        
                        # 删除空文件夹
                        if not any(video_folder.iterdir()):
                            video_folder.rmdir()
                            print(f"已删除空文件夹: {video_folder}")
                    except Exception as e:
                        print(f"清理文件夹失败: {str(e)}")
            
            # 4. 也尝试按ID清理（兼容旧文件）
            video_folder_by_id = download_dir / ids
            if video_folder_by_id.exists():
                try:
                    # 删除文件夹中的所有文件
                    for file_path in video_folder_by_id.iterdir():
                        if file_path.is_file():
                            file_path.unlink()
                            print(f"已删除文件: {file_path}")
                    
                    # 删除空文件夹
                    if not any(video_folder_by_id.iterdir()):
                        video_folder_by_id.rmdir()
                        print(f"已删除空文件夹: {video_folder_by_id}")
                except Exception as e:
                    print(f"清理文件夹失败: {str(e)}")
            
            print("清理完成")
            
        except Exception as e:
            print(f"清理文件和记录失败: {str(e)}")
    
    def _get_video_folder_path(self, video_name: str) -> Path:
        """获取视频文件夹路径，根据folder_mode配置决定是否创建子文件夹"""
        download_dir = Path(self.downloader.parameter.root) / "Download"
        
        if self.downloader.parameter.folder_mode:
            # 文件夹模式：为每个视频创建子文件夹
            video_folder = download_dir / video_name
            video_folder.mkdir(parents=True, exist_ok=True)
            return video_folder
        else:
            # 非文件夹模式：直接在下载目录中
            download_dir.mkdir(parents=True, exist_ok=True)
            return download_dir
    
    def _check_file_exists(self, file_path: str) -> bool:
        """检查文件是否存在且不为空"""
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except:
            return False
    
    async def _find_downloaded_video(self, ids: str, is_tiktok: bool = False, video_name: str = None) -> Optional[str]:
        """查找已下载的视频文件"""
        try:
            # 获取下载目录
            download_dir = Path(self.downloader.parameter.root) / "Download"
            
            # 如果有视频名称，优先按名称查找
            if video_name:
                print(f"按视频名称查找: {video_name}")
                
                # 根据folder_mode决定查找位置
                if self.downloader.parameter.folder_mode:
                    # 文件夹模式：在子文件夹中查找
                    video_folder = download_dir / video_name
                    if video_folder.exists():
                        video_patterns = [
                            f"{video_name}.mp4",
                            f"{video_name}.mov",
                            f"{video_name}.avi"
                        ]
                        
                        for pattern in video_patterns:
                            video_file = video_folder / pattern
                            if video_file.exists() and video_file.stat().st_size > 0:
                                print(f"在文件夹中找到视频文件: {video_file}")
                                return str(video_file)
                    
                    # 也尝试查找文件夹中的其他视频文件
                    for video_file in video_folder.glob("*.mp4"):
                        if video_file.exists() and video_file.stat().st_size > 0:
                            print(f"在文件夹中找到视频文件: {video_file}")
                            return str(video_file)
                else:
                    # 非文件夹模式：直接在下载目录中查找
                    video_patterns = [
                        f"{video_name}.mp4",
                        f"{video_name}.mov",
                        f"{video_name}.avi",
                        f"*{video_name}*.mp4",
                        f"*{video_name}*.mov",
                        f"*{video_name}*.avi"
                    ]
                    
                    for pattern in video_patterns:
                        for video_file in download_dir.glob(pattern):
                            if video_file.exists() and video_file.stat().st_size > 0:
                                print(f"找到视频文件: {video_file}")
                                return str(video_file)
            
            # 如果按名称没找到，尝试按ID查找
            print(f"按视频ID查找: {ids}")
            video_patterns = [
                f"*{ids}*.mp4",
                f"*{ids}*.mov",
                f"*{ids}*.avi"
            ]
            
            # 在下载目录中查找视频文件
            for pattern in video_patterns:
                for video_file in download_dir.glob(pattern):
                    if video_file.exists() and video_file.stat().st_size > 0:
                        print(f"找到视频文件: {video_file}")
                        return str(video_file)
            
            # 如果还是没找到，尝试查找最近下载的文件
            print("查找最近下载的视频文件...")
            video_files = []
            for ext in ['*.mp4', '*.mov', '*.avi']:
                video_files.extend(download_dir.glob(ext))
            
            if video_files:
                # 按修改时间排序，返回最新的
                latest_file = max(video_files, key=lambda f: f.stat().st_mtime)
                if latest_file.stat().st_size > 0:
                    print(f"找到最新视频文件: {latest_file}")
                    return str(latest_file)
            
            print("未找到视频文件")
            return None
            
        except Exception as e:
            print(f"查找视频文件失败: {str(e)}")
            return None
    
    async def _download_video_from_url(self, video_url: str, output_path: str) -> bool:
        """从URL下载视频文件"""
        try:
            print(f"正在从URL下载视频: {video_url}")
            
            # 创建输出目录
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 使用requests下载视频
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(video_url, headers=headers, stream=True)
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            
            with open(output_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r下载进度: {percent:.1f}%", end='', flush=True)
            
            print(f"\n视频下载完成: {output_path}")
            return True
            
        except Exception as e:
            print(f"从URL下载视频失败: {str(e)}")
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
            if self._check_file_exists(str(audio_path)):
                print(f"音频文件已存在，跳过提取: {audio_path}")
                return str(audio_path)
            
            print("正在提取音频...")
            
            # 使用ffmpeg提取音频
            import subprocess
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
    
    def save_text_to_file(self, text: str, filename: str, video_folder: Path, video_name: str = None, force: bool = False) -> Optional[str]:
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
            if self._check_file_exists(str(text_path)) and not force:
                print(f"文本文件已存在，跳过保存: {text_path}")
                return str(text_path)
            
            # 保存文本
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            if force and self._check_file_exists(str(text_path)):
                print(f"文本已覆盖保存: {text_path}")
            else:
                print(f"文本已保存: {text_path}")
            return str(text_path)
            
        except Exception as e:
            print(f"保存文本失败: {str(e)}")
            return None
    
    def transcribe_audio(self, audio_path: str, transcription_file_path: str = None) -> Optional[str]:
        """将音频转换为文字"""
        try:
            # 如果提供了转录文件路径，先检查文件是否已存在
            if transcription_file_path and self._check_file_exists(transcription_file_path):
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
    
    def summarize_with_ai(self, text: str) -> Optional[str]:
        """使用DeepSeek AI进行内容总结"""
        if not self.deepseek_client:
            print("未配置DeepSeek API，跳过AI总结")
            return None
        
        try:
            print("正在使用AI进行内容总结...")
            
            prompt = f"""
清单体笔记法的常见技巧包括：
1. 简洁备忘：省略无关信息，只记录关键点。
2. 条理清晰：使用有序和无序列表进行逻辑分点。
3. 层级分明：最多分三层，确保信息结构清晰。
4. 高信息密度：每行只表达一个含义，避免多行叙述。
5. 标题明确：每个要点附上简短标题，方便快速浏览。
6. 产品化思维：结构清晰，注意排班、总分总、目录式结构。
7. 视觉优化：使用加粗、斜体、底色、颜色、表情符号等方式进行适当美化。
8. 理清脉络：按时间顺序、操作步骤、事实认知、STAR原则等方式理清思路。


请对以下抖音视频的文字内容进行总结，要求总结分为3部分：

第一部分：知识点列表（这里要求尽可能全，不要有任何遗漏）

第二部分：核心观点和要点
1. 提取核心观点和要点
2. 分析内容的主要价值

第三部分：你的客观辩证性评论和问题

视频文字内容：
{text}
"""
            
            response = self.deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的内容分析师，擅长总结和分析视频内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            print("AI总结完成")
            return summary
            
        except Exception as e:
            print(f"AI总结失败: {str(e)}")
            return None
    
    async def process_video(self, url: str, output_dir: Optional[str] = None, 
                          keep_files: bool = False, force_download: bool = False) -> dict:
        """处理视频的完整流程"""
        result = {
            "url": url,
            "video_path": None,
            "audio_path": None,
            "transcription": None,
            "summary": None,
            "transcription_file": None,
            "summary_file": None,
            "video_folder": None,
            "success": False
        }
        
        try:
            # 1. 下载视频并获取detail数据
            video_path, detail_data = await self.download_video(url, output_dir, force_download)
            if not video_path:
                return result
            result["video_path"] = video_path
            
            # 提取视频ID和名称用于文件命名
            platform = self.detect_platform(url)
            if platform == 'tiktok':
                ids = await self.tiktok_instance.links_tiktok.run(url)
            else:
                ids = await self.tiktok_instance.links.run(url)
            
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            
            # 从detail_data中提取视频名称
            video_name = self._get_video_name_from_detail_data(detail_data, video_id)
            
            # 使用视频名称作为文件夹名
            video_folder = self._get_video_folder_path(video_name)
            result["video_folder"] = str(video_folder)
            
            print(f"视频文件夹: {video_folder}")
            
            # 2. 提取音频
            audio_path = self.extract_audio(video_path, video_folder, video_name)
            if not audio_path:
                return result
            result["audio_path"] = audio_path
            
            # 3. 语音转文字
            # 先生成转录文件路径
            transcription_file = video_folder / f"{video_name}_transcription.txt"
            
            # 传递转录文件路径给transcribe_audio方法
            transcription = self.transcribe_audio(audio_path, str(transcription_file))
            if not transcription:
                return result
            result["transcription"] = transcription
            
            # 如果转录文件不存在，保存转录文本到文件
            if not self._check_file_exists(str(transcription_file)):
                transcription_file = self.save_text_to_file(transcription, "transcription", video_folder, video_name)
            result["transcription_file"] = str(transcription_file)
            
            # 4. AI总结
            summary = self.summarize_with_ai(transcription)
            result["summary"] = summary
            
            # 保存总结文本到文件（强制覆盖已存在的文件）
            if summary:
                summary_file = self.save_text_to_file(summary, "summary", video_folder, video_name, force=True)
                result["summary_file"] = summary_file
            
            result["success"] = True
            
            # 清理临时文件（如果不需要保留）
            if not keep_files and audio_path and audio_path.startswith(tempfile.gettempdir()):
                try:
                    os.remove(audio_path)
                    os.rmdir(os.path.dirname(audio_path))
                except:
                    pass
            
            return result
            
        except Exception as e:
            print(f"处理视频失败: {str(e)}")
            return result


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="抖音视频AI总结工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python video_ai_summarizer.py https://v.douyin.com/xxxxx --api-key your_deepseek_key
  python video_ai_summarizer.py https://v.douyin.com/xxxxx --output ./downloads
  python video_ai_summarizer.py https://v.douyin.com/xxxxx --keep-files
  python video_ai_summarizer.py https://v.douyin.com/xxxxx --force-download

API密钥配置方式（按优先级）:
  1. --api-key 命令行参数
  2. Volume/settings.json 中的 deepseek_api_key 字段
  3. DEEPSEEK_API_KEY 环境变量

推荐在 Volume/settings.json 中配置:
  {
    "deepseek_api_key": "your_deepseek_api_key_here",
    ...
  }
        """
    )
    
    parser.add_argument(
        'url', 
        help='要处理的抖音视频链接'
    )
    
    parser.add_argument(
        '--api-key', 
        help='DeepSeek API密钥'
    )
    
    parser.add_argument(
        '--output', 
        '-o', 
        help='指定输出目录'
    )
    
    parser.add_argument(
        '--keep-files', 
        action='store_true', 
        help='保留临时文件'
    )
    
    parser.add_argument(
        '--save-result', 
        help='保存结果到文件'
    )
    
    parser.add_argument(
        '--force-download', 
        action='store_true', 
        help='强制重新下载视频，即使视频已存在'
    )

    args = parser.parse_args()
    
    # 检查API密钥，优先级：命令行参数 > settings.json > 环境变量
    api_key = None
    if args.api_key:
        api_key = args.api_key
        print("使用命令行参数提供的API key")
    else:
        # 尝试从settings.json读取
        api_key = load_api_key_from_settings()
        if not api_key:
            # 最后尝试环境变量
            api_key = os.getenv('DEEPSEEK_API_KEY')
            if api_key:
                print("使用环境变量DEEPSEEK_API_KEY")
    
    if not api_key:
        print("警告: 未提供DeepSeek API密钥，将跳过AI总结功能")
        print("可以通过以下方式提供API密钥:")
        print("1. --api-key 命令行参数")
        print("2. 在Volume/settings.json中配置 deepseek_api_key")
        print("3. DEEPSEEK_API_KEY 环境变量")
    
    # 创建总结器实例
    async with VideoAISummarizer(api_key) as summarizer:
        try:
            print("=" * 60)
            print("开始处理视频...")
            print("=" * 60)
            
            # 处理视频
            result = await summarizer.process_video(
                url=args.url,
                output_dir=args.output,
                keep_files=args.keep_files,
                force_download=args.force_download
            )
            
            # 显示结果
            print("\n" + "=" * 60)
            print("处理结果:")
            print("=" * 60)
            
            if result["success"]:
                print("✅ 处理成功!")
                print(f"视频文件夹: {result['video_folder']}")
                print(f"视频路径: {result['video_path']}")
                
                if result["audio_path"]:
                    print(f"音频路径: {result['audio_path']}")
                
                if result["transcription_file"]:
                    print(f"转录文本文件: {result['transcription_file']}")
                
                if result["summary_file"]:
                    print(f"AI总结文件: {result['summary_file']}")
                
                if result["transcription"]:
                    print(f"\n📝 语音转文字:")
                    print("-" * 40)
                    print(result["transcription"])
                
                if result["summary"]:
                    print(f"\n🤖 AI总结:")
                    print("-" * 40)
                    print(result["summary"])
                
                # 保存结果到文件
                if args.save_result:
                    save_result_to_file(result, args.save_result)
                    print(f"\n💾 结果已保存到: {args.save_result}")
                
            else:
                print("❌ 处理失败")
                return 1
            
            return 0
            
        except KeyboardInterrupt:
            print("\n用户中断处理")
            return 1
        except Exception as e:
            print(f"程序错误: {str(e)}")
            return 1


def save_result_to_file(result: dict, file_path: str):
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


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
