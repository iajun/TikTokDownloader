"""
主CLI入口模块
负责命令行参数解析和主流程控制
"""

import argparse
import asyncio
import os
import sys
import json
from pathlib import Path
from typing import Optional

from src.application import TikTokDownloader
from .video_processor import VideoProcessor
from .audio_extractor import AudioExtractor
from .transcription_service import TranscriptionService
from .ai_summarizer import AISummarizer
from .file_manager import FileManager


def load_api_key_from_settings() -> Optional[str]:
    """从Volume/settings.json中读取DeepSeek API key"""
    try:
        # 查找Volume目录
        volume_paths = [
            Path(__file__).parent.parent.parent / "Volume" / "settings.json",
            Path(__file__).parent.parent.parent.parent / "Volume" / "settings.json",
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
    """视频AI总结器 - 主控制器"""
    
    def __init__(self, deepseek_api_key: Optional[str] = None):
        self.downloader = None
        self.video_processor = None
        self.audio_extractor = AudioExtractor()
        self.transcription_service = TranscriptionService()
        self.ai_summarizer = AISummarizer(deepseek_api_key)
        self.file_manager = FileManager()
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.downloader = TikTokDownloader()
        await self.downloader.__aenter__()
        self.video_processor = VideoProcessor(self.downloader)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.downloader:
            await self.downloader.__aexit__(exc_type, exc_val, exc_tb)
    
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
            video_path, detail_data = await self.video_processor.download_video(url, output_dir, force_download)
            if not video_path:
                return result
            result["video_path"] = video_path
            
            # 提取视频ID和名称用于文件命名
            platform = self.video_processor.detect_platform(url)
            if platform == 'tiktok':
                ids = await self.video_processor.tiktok_instance.links_tiktok.run(url)
            else:
                ids = await self.video_processor.tiktok_instance.links.run(url)
            
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            
            # 从detail_data中提取视频名称
            video_name = self.video_processor._get_video_name_from_detail_data(detail_data, video_id)
            
            # 使用视频名称作为文件夹名
            video_folder = self.video_processor._get_video_folder_path(video_name)
            result["video_folder"] = str(video_folder)
            
            print(f"视频文件夹: {video_folder}")
            
            # 2. 提取音频
            audio_path = self.audio_extractor.extract_audio(video_path, video_folder, video_name)
            if not audio_path:
                return result
            result["audio_path"] = audio_path
            
            # 3. 语音转文字
            # 先生成转录文件路径
            transcription_file = video_folder / f"{video_name}_transcription.txt"
            
            # 传递转录文件路径给transcribe_async方法（异步版本）
            transcription = await self.transcription_service.transcribe_async(audio_path, str(transcription_file))
            if not transcription:
                return result
            result["transcription"] = transcription
            
            # 如果转录文件不存在，保存转录文本到文件
            if not self.file_manager.check_file_exists(str(transcription_file)):
                transcription_file = self.file_manager.save_text_to_file(transcription, "transcription", video_folder, video_name)
            result["transcription_file"] = str(transcription_file)
            
            # 4. AI总结
            summary = self.ai_summarizer.summarize_with_ai(transcription)
            result["summary"] = summary
            
            # 保存总结文本到文件（强制覆盖已存在的文件）
            if summary:
                summary_file = self.file_manager.save_text_to_file(summary, "summary", video_folder, video_name, force=True)
                result["summary_file"] = summary_file
            
            result["success"] = True
            
            # 清理临时文件（如果不需要保留）
            self.file_manager.cleanup_temp_files([audio_path], keep_files)
            
            return result
            
        except Exception as e:
            print(f"处理视频失败: {str(e)}")
            return result
    
    async def summarize_audio_only(self, audio_path: str, output_dir: Optional[str] = None, 
                                  keep_files: bool = False) -> dict:
        """仅对音频进行转录和总结（用于重新总结）"""
        result = {
            "audio_path": audio_path,
            "transcription": None,
            "summary": None,
            "transcription_file": None,
            "summary_file": None,
            "success": False
        }
        
        try:
            if not Path(audio_path).exists():
                result["error"] = "音频文件不存在"
                return result
            
            # 生成输出目录和文件名
            audio_file = Path(audio_path)
            audio_name = audio_file.stem.replace('_audio', '')  # 移除_audio后缀
            
            if output_dir:
                output_path = Path(output_dir)
            else:
                output_path = audio_file.parent
            
            # 1. 语音转文字
            transcription_file = output_path / f"{audio_name}_transcription.txt"
            transcription = await self.transcription_service.transcribe_async(audio_path, str(transcription_file))
            if not transcription:
                result["error"] = "语音转文字失败"
                return result
            result["transcription"] = transcription
            result["transcription_file"] = str(transcription_file)
            
            # 2. AI总结
            summary = self.ai_summarizer.summarize_with_ai(transcription)
            if not summary:
                result["error"] = "AI总结失败"
                return result
            result["summary"] = summary
            
            # 3. 保存总结文件
            summary_file = self.file_manager.save_text_to_file(summary, "summary", output_path, audio_name, force=True)
            result["summary_file"] = summary_file
            
            result["success"] = True
            return result
            
        except Exception as e:
            print(f"重新总结失败: {str(e)}")
            result["error"] = str(e)
            return result


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="抖音视频AI总结工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python -m src.ai.main_cli https://v.douyin.com/xxxxx --api-key your_deepseek_key
  python -m src.ai.main_cli https://v.douyin.com/xxxxx --output ./downloads
  python -m src.ai.main_cli https://v.douyin.com/xxxxx --keep-files
  python -m src.ai.main_cli https://v.douyin.com/xxxxx --force-download

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
                    summarizer.file_manager.save_result_to_file(result, args.save_result)
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


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
