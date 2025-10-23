#!/usr/bin/env python3
"""
抖音视频AI总结工具 - 入口文件
功能：
1. 下载抖音视频
2. 提取音频并转换为文字
3. 使用DeepSeek AI进行内容总结

依赖安装：
pip install openai-whisper requests openai
"""

import sys
import asyncio
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入AI模块
from src.ai import main

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)