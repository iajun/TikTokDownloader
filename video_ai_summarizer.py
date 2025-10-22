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
    
    async def download_video(self, url: str, output_dir: Optional[str] = None) -> tuple[Optional[str], Optional[list]]:
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
                self.downloader.parameter.root = output_dir
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
                # 使用与cli_downloader.py相同的下载逻辑
                detail_data = await self.tiktok_instance._handle_detail(ids, platform == 'tiktok', record)
            
            # 检查视频是否已经下载过
            if await self._is_video_downloaded(ids):
                print(f"视频 {ids} 已经下载过，跳过下载步骤")
                # 查找已下载的视频文件
                video_path = await self._find_downloaded_video(ids, platform == 'tiktok')
                if video_path:
                    print(f"找到已下载的视频: {video_path}")
                    return video_path, detail_data
                else:
                    print("警告: 数据库中记录已下载，但未找到视频文件")
            
            # 首先尝试查找已下载的视频文件
            video_path = await self._find_downloaded_video(ids, platform == 'tiktok')
            if video_path:
                print(f"视频下载成功: {video_path}")
                return video_path, detail_data
            
            # 如果没找到文件，尝试从detail数据中获取视频URL并下载
            if detail_data and len(detail_data) > 0:
                video_data = detail_data[0]
                if video_data.get("type") == "视频":
                    # 尝试从downloads字段获取视频URL
                    downloads = video_data.get("downloads", [])
                    if downloads:
                        for download_url in downloads:
                            if download_url and isinstance(download_url, str) and download_url.startswith(('http://', 'https://')):
                                print(f"检测到视频URL，尝试直接下载: {download_url}")
                                # 生成输出文件名
                                download_dir = Path(self.downloader.parameter.root) / "Download"
                                output_filename = f"{ids}.mp4"
                                output_path = download_dir / output_filename
                                
                                # 下载视频
                                if await self._download_video_from_url(download_url, str(output_path)):
                                    return str(output_path), detail_data
            
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
    
    def _get_video_folder_path(self, video_title: str) -> Path:
        """获取视频文件夹路径"""
        download_dir = Path(self.downloader.parameter.root) / "Download"
        video_folder = download_dir / video_title
        video_folder.mkdir(parents=True, exist_ok=True)
        return video_folder
    
    def _check_file_exists(self, file_path: str) -> bool:
        """检查文件是否存在且不为空"""
        try:
            return os.path.exists(file_path) and os.path.getsize(file_path) > 0
        except:
            return False
    
    async def _find_downloaded_video(self, ids: str, is_tiktok: bool = False) -> Optional[str]:
        """查找已下载的视频文件"""
        try:
            # 获取下载目录
            download_dir = Path(self.downloader.parameter.root) / "Download"
            
            # 根据平台和ID查找视频文件
            if is_tiktok:
                # TikTok视频文件命名规则
                video_patterns = [
                    f"*{ids}*.mp4",
                    f"*{ids}*.mov",
                    f"*{ids}*.avi"
                ]
            else:
                # 抖音视频文件命名规则
                video_patterns = [
                    f"*{ids}*.mp4",
                    f"*{ids}*.mov", 
                    f"*{ids}*.avi"
                ]
            
            # 在下载目录中查找视频文件
            for pattern in video_patterns:
                for video_file in download_dir.glob(pattern):
                    if video_file.exists() and video_file.stat().st_size > 0:
                        return str(video_file)
            
            # 如果没找到，尝试查找最近下载的文件
            video_files = []
            for ext in ['*.mp4', '*.mov', '*.avi']:
                video_files.extend(download_dir.glob(ext))
            
            if video_files:
                # 按修改时间排序，返回最新的
                latest_file = max(video_files, key=lambda f: f.stat().st_mtime)
                if latest_file.stat().st_size > 0:
                    return str(latest_file)
            
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
    
    def extract_audio(self, video_path: str, video_folder: Path, video_ids: str = None) -> Optional[str]:
        """从视频中提取音频"""
        try:
            # 生成音频文件名
            if video_ids:
                # 确保video_ids是字符串，如果是列表则取第一个元素
                if isinstance(video_ids, list):
                    video_ids = video_ids[0]
                audio_filename = f"{video_ids}_audio.wav"
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
    
    def save_text_to_file(self, text: str, filename: str, video_folder: Path, video_ids: str = None) -> Optional[str]:
        """保存文本到文件"""
        try:
            # 生成文件名
            if video_ids:
                # 确保video_ids是字符串，如果是列表则取第一个元素
                if isinstance(video_ids, list):
                    video_ids = video_ids[0]
                text_filename = f"{video_ids}_{filename}.txt"
            else:
                text_filename = f"{filename}.txt"
            
            text_path = video_folder / text_filename
            
            # 检查文件是否已存在
            if self._check_file_exists(str(text_path)):
                print(f"文本文件已存在，跳过保存: {text_path}")
                return str(text_path)
            
            # 保存文本
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
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
请对以下抖音视频的文字内容进行总结，要求：
1. 提取核心观点和要点
2. 分析内容的主要价值
3. 用简洁的语言概括主要内容
4. 如果内容有教育意义，请指出学习要点

视频文字内容：
{text}

请提供结构化的总结：
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
                          keep_files: bool = False) -> dict:
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
            video_path, detail_data = await self.download_video(url, output_dir)
            if not video_path:
                return result
            result["video_path"] = video_path
            
            # 提取视频ID用于文件命名
            platform = self.detect_platform(url)
            if platform == 'tiktok':
                ids = await self.tiktok_instance.links_tiktok.run(url)
            else:
                ids = await self.tiktok_instance.links.run(url)
            
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            
            # 使用视频ID作为文件夹名
            video_folder = self._get_video_folder_path(video_id)
            result["video_folder"] = str(video_folder)
            
            print(f"视频文件夹: {video_folder}")
            
            # 2. 提取音频
            audio_path = self.extract_audio(video_path, video_folder, video_id)
            if not audio_path:
                return result
            result["audio_path"] = audio_path
            
            # 3. 语音转文字
            transcription = self.transcribe_audio(audio_path)
            if not transcription:
                return result
            result["transcription"] = transcription
            
            # 保存转录文本到文件
            transcription_file = self.save_text_to_file(transcription, "transcription", video_folder, video_id)
            result["transcription_file"] = transcription_file
            
            # 4. AI总结
            summary = self.summarize_with_ai(transcription)
            result["summary"] = summary
            
            # 保存总结文本到文件
            if summary:
                summary_file = self.save_text_to_file(summary, "summary", video_folder, video_id)
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

    args = parser.parse_args()
    
    # 检查API密钥
    api_key = args.api_key or os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("警告: 未提供DeepSeek API密钥，将跳过AI总结功能")
        print("可以通过 --api-key 参数或 DEEPSEEK_API_KEY 环境变量提供")
    
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
                keep_files=args.keep_files
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
