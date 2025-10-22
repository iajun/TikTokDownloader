#!/usr/bin/env python3
"""
抖音视频AI总结Web应用启动脚本
"""

import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from web_app import WebApp

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="抖音视频AI总结Web应用")
    parser.add_argument("--host", default="127.0.0.1", help="服务器地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口 (默认: 8000)")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎬 抖音视频AI总结Web应用")
    print("=" * 60)
    print(f"服务器地址: http://{args.host}:{args.port}")
    print(f"API文档: http://{args.host}:{args.port}/docs")
    print("=" * 60)
    
    # 检查必要的依赖
    try:
        import whisper
        import requests
        from openai import OpenAI
        print("✅ 依赖检查通过")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install openai-whisper requests openai fastapi uvicorn jinja2 python-multipart")
        return 1
    
    # 检查ffmpeg
    try:
        import subprocess
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("✅ FFmpeg 已安装")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  警告: FFmpeg 未安装或不在PATH中")
        print("请安装 FFmpeg 以支持音频提取功能")
    
    print("\n🚀 启动Web应用...")
    print("按 Ctrl+C 停止服务器")
    print("-" * 60)
    
    try:
        # 创建并运行Web应用
        app = WebApp()
        app.run(host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\n👋 服务器已停止")
        return 0
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
