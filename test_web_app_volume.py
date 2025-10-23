#!/usr/bin/env python3
"""
测试Web应用的Volume目录扫描功能
"""

import sys
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from web_app import WebApp

def test_volume_scan():
    """测试Volume目录扫描功能"""
    print("测试Volume目录扫描功能...")
    
    # 创建WebApp实例
    app = WebApp()
    
    # 测试扫描现有文件
    existing_records = app._scan_existing_files()
    
    print(f"扫描到 {len(existing_records)} 个现有视频文件:")
    for record in existing_records:
        print(f"  - ID: {record['id']}")
        print(f"    视频: {record['video_path']}")
        print(f"    音频: {record['audio_path']}")
        print(f"    转录: {record['transcription_file']}")
        print(f"    总结: {record['summary_file']}")
        print(f"    状态: {record['status']}")
        print(f"    来源: {record['source']}")
        print(f"    创建时间: {record['created_at']}")
        print()
    
    # 测试获取所有记录
    all_records = app._get_all_records()
    print(f"总共 {len(all_records)} 个记录（包括数据库和Volume目录）")
    
    return len(existing_records) > 0

if __name__ == "__main__":
    success = test_volume_scan()
    if success:
        print("✅ Volume目录扫描功能测试成功！")
    else:
        print("❌ Volume目录扫描功能测试失败！")
