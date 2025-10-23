#!/usr/bin/env python3
"""
测试修复后的视频下载功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.ai import VideoAISummarizer

async def test_video_download():
    """测试视频下载功能"""
    # 使用一个测试URL（请替换为实际的抖音视频链接）
    test_url = "https://v.douyin.com/xxxxx"  # 请替换为实际的链接
    
    print("开始测试视频下载功能...")
    
    async with VideoAISummarizer() as summarizer:
        try:
            # 测试下载视频
            video_path, detail_data = await summarizer.video_processor.download_video(
                test_url, 
                force_download=True  # 强制重新下载
            )
            
            if video_path:
                print(f"✅ 视频下载成功: {video_path}")
                return True
            else:
                print("❌ 视频下载失败")
                return False
                
        except Exception as e:
            print(f"❌ 测试失败: {str(e)}")
            return False

if __name__ == "__main__":
    print("请先替换test_url为实际的抖音视频链接，然后运行测试")
    print("或者直接使用命令行工具测试:")
    print("python video_ai_summarizer.py <视频链接> --force-download")
