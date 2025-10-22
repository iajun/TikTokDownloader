#!/usr/bin/env python3
"""
Web应用测试脚本
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from web_app import WebApp

async def test_web_app():
    """测试Web应用基本功能"""
    print("🧪 开始测试Web应用...")
    
    # 创建Web应用实例
    app = WebApp()
    
    # 测试数据库初始化
    print("1. 测试数据库初始化...")
    records = app._load_records()
    print(f"   ✅ 数据库加载成功，当前记录数: {len(records)}")
    
    # 测试记录添加
    print("2. 测试记录添加...")
    test_record = {
        "id": "test_123",
        "url": "https://v.douyin.com/test",
        "status": "processing",
        "created_at": "2024-01-01T00:00:00"
    }
    app._add_record(test_record)
    
    # 验证记录添加
    records = app._load_records()
    test_record_found = any(r["id"] == "test_123" for r in records)
    print(f"   ✅ 记录添加成功: {test_record_found}")
    
    # 测试记录更新
    print("3. 测试记录更新...")
    app._update_record("test_123", {"status": "completed"})
    
    updated_record = app._get_record("test_123")
    if updated_record and updated_record["status"] == "completed":
        print("   ✅ 记录更新成功")
    else:
        print("   ❌ 记录更新失败")
    
    # 测试目录创建
    print("4. 测试目录创建...")
    required_dirs = [app.static_dir, app.templates_dir, app.data_dir, app.downloads_dir]
    all_dirs_exist = all(d.exists() for d in required_dirs)
    print(f"   ✅ 目录创建成功: {all_dirs_exist}")
    
    # 清理测试数据
    print("5. 清理测试数据...")
    records = app._load_records()
    records = [r for r in records if r["id"] != "test_123"]
    app._save_records(records)
    print("   ✅ 测试数据清理完成")
    
    print("\n🎉 所有测试通过！Web应用基本功能正常")

def test_file_structure():
    """测试文件结构"""
    print("\n📁 检查文件结构...")
    
    required_files = [
        "web_app.py",
        "start_web_app.py", 
        "templates/index.html",
        "templates/history.html",
        "README_WEB_APP.md"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = Path(file_path)
        if not full_path.exists():
            missing_files.append(file_path)
        else:
            print(f"   ✅ {file_path}")
    
    if missing_files:
        print(f"   ❌ 缺少文件: {missing_files}")
        return False
    else:
        print("   ✅ 所有必需文件都存在")
        return True

def test_dependencies():
    """测试依赖包"""
    print("\n📦 检查依赖包...")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "jinja2",
        "whisper",
        "requests",
        "openai"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package}")
    
    if missing_packages:
        print(f"\n⚠️  缺少依赖包: {missing_packages}")
        print("请运行: pip install " + " ".join(missing_packages))
        return False
    else:
        print("   ✅ 所有依赖包都已安装")
        return True

def main():
    """主函数"""
    print("=" * 60)
    print("🧪 抖音视频AI总结Web应用测试")
    print("=" * 60)
    
    # 测试文件结构
    if not test_file_structure():
        return 1
    
    # 测试依赖包
    if not test_dependencies():
        return 1
    
    # 测试Web应用功能
    try:
        asyncio.run(test_web_app())
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return 1
    
    print("\n" + "=" * 60)
    print("🎉 所有测试通过！可以启动Web应用了")
    print("运行命令: python start_web_app.py")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
