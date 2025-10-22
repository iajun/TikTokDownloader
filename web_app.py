#!/usr/bin/env python3
"""
抖音视频AI总结Web应用
功能：
1. 提供Web界面输入抖音链接
2. 下载视频并提取音频
3. 使用Whisper进行语音转文字
4. 使用DeepSeek AI进行内容总结
5. 持久化存储所有内容（视频、音频、文字、总结）
6. 提供历史记录查看功能

依赖安装：
pip install fastapi uvicorn jinja2 python-multipart
"""

import asyncio
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import json
import re

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
    from pydantic import BaseModel
except ImportError as e:
    print(f"缺少依赖包: {e}")
    print("请运行: pip install fastapi uvicorn jinja2 python-multipart")
    sys.exit(1)

from video_ai_summarizer import VideoAISummarizer, load_api_key_from_settings


def extract_douyin_url(text: str) -> Optional[str]:
    """从文本中提取抖音链接"""
    try:
        # 抖音链接的正则表达式模式
        patterns = [
            r'https://v\.douyin\.com/[a-zA-Z0-9]+/?',  # 标准短链接
            r'https://www\.douyin\.com/video/\d+',     # 完整链接
            r'https://www\.iesdouyin\.com/share/video/\d+',  # 另一种格式
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # 返回第一个匹配的链接
                url = matches[0]
                # 确保链接完整
                if not url.endswith('/'):
                    url += '/'
                return url
        
        return None
        
    except Exception as e:
        print(f"提取抖音链接失败: {str(e)}")
        return None


class VideoProcessRequest(BaseModel):
    url: str
    api_key: Optional[str] = None


class VideoRecord(BaseModel):
    id: str
    url: str
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    transcription: Optional[str] = None
    summary: Optional[str] = None
    transcription_file: Optional[str] = None
    summary_file: Optional[str] = None
    video_folder: Optional[str] = None
    created_at: str
    status: str  # processing, completed, failed


class WebApp:
    def __init__(self):
        self.app = FastAPI(
            title="抖音视频AI总结工具",
            description="输入抖音链接，自动下载视频、提取音频、转文字并AI总结",
            version="1.0.0"
        )
        
        # 创建必要的目录
        self.static_dir = Path("static")
        self.templates_dir = Path("templates")
        self.data_dir = Path("downloads/Data")  # 使用与video_ai_summarizer一致的路径
        self.downloads_dir = Path("downloads")
        
        for dir_path in [self.static_dir, self.templates_dir, self.data_dir, self.downloads_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # 数据库文件路径
        self.db_file = self.data_dir / "video_records.json"
        
        # 检查API key配置状态
        self.api_key_configured = self._check_api_key_config()
        
        # 初始化数据库
        self._init_database()
        
        # 设置路由
        self._setup_routes()
        
        # 挂载静态文件
        self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
        self.app.mount("/downloads", StaticFiles(directory=str(self.downloads_dir)), name="downloads")
    
    def _check_api_key_config(self) -> bool:
        """检查API key是否已配置"""
        api_key = load_api_key_from_settings()
        return api_key is not None and api_key.strip() != ""
    
    def _init_database(self):
        """初始化数据库"""
        # 确保目录存在
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_file.exists():
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    def _load_records(self) -> List[dict]:
        """加载所有记录"""
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    
    def _save_records(self, records: List[dict]):
        """保存记录"""
        # 确保目录存在
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    
    def _add_record(self, record: dict):
        """添加新记录"""
        records = self._load_records()
        records.append(record)
        self._save_records(records)
    
    def _update_record(self, record_id: str, updates: dict):
        """更新记录"""
        records = self._load_records()
        for i, record in enumerate(records):
            if record['id'] == record_id:
                records[i].update(updates)
                break
        self._save_records(records)
    
    def _get_record(self, record_id: str) -> Optional[dict]:
        """获取单个记录"""
        records = self._load_records()
        for record in records:
            if record['id'] == record_id:
                return record
        return None
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            """主页"""
            return self._render_template("index.html", {
                "request": request,
                "api_key_configured": self.api_key_configured
            })
        
        @self.app.get("/history", response_class=HTMLResponse)
        async def history(request: Request):
            """历史记录页面"""
            records = self._load_records()
            # 按创建时间倒序排列
            records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return self._render_template("history.html", {
                "request": request,
                "records": records
            })
        
        @self.app.post("/api/process")
        async def process_video(request: VideoProcessRequest, background_tasks: BackgroundTasks):
            """处理视频API"""
            try:
                # 尝试从输入文本中提取抖音链接
                extracted_url = extract_douyin_url(request.url)
                
                if extracted_url:
                    # 如果提取到链接，使用提取的链接
                    final_url = extracted_url
                    extraction_message = f"已从文本中提取到抖音链接: {extracted_url}"
                else:
                    # 如果没有提取到链接，检查输入是否已经是有效的URL
                    if request.url.startswith(('http://', 'https://')):
                        final_url = request.url
                        extraction_message = "使用输入的链接"
                    else:
                        return JSONResponse({
                            "success": False,
                            "message": "未找到有效的抖音链接，请检查输入内容"
                        }, status_code=400)
                
                # 生成记录ID
                record_id = f"video_{int(datetime.now().timestamp())}"
                
                # 创建初始记录
                record = VideoRecord(
                    id=record_id,
                    url=final_url,
                    created_at=datetime.now().isoformat(),
                    status="processing"
                )
                self._add_record(record.dict())
                
                # 在后台处理视频
                background_tasks.add_task(
                    self._process_video_background,
                    record_id,
                    final_url,
                    request.api_key
                )
                
                return JSONResponse({
                    "success": True,
                    "message": f"视频处理已开始 - {extraction_message}",
                    "record_id": record_id,
                    "extracted_url": extracted_url,
                    "final_url": final_url
                })
                
            except Exception as e:
                return JSONResponse({
                    "success": False,
                    "message": f"处理失败: {str(e)}"
                }, status_code=500)
        
        @self.app.get("/api/status/{record_id}")
        async def get_status(record_id: str):
            """获取处理状态"""
            record = self._get_record(record_id)
            if not record:
                raise HTTPException(status_code=404, detail="记录不存在")
            
            return JSONResponse({
                "success": True,
                "record": record
            })
        
        @self.app.get("/api/records")
        async def get_records():
            """获取所有记录"""
            records = self._load_records()
            return JSONResponse({
                "success": True,
                "records": records
            })
        
        @self.app.get("/api/record/{record_id}")
        async def get_record(record_id: str):
            """获取单个记录详情"""
            record = self._get_record(record_id)
            if not record:
                raise HTTPException(status_code=404, detail="记录不存在")
            
            return JSONResponse({
                "success": True,
                "record": record
            })
    
    def _render_template(self, template_name: str, context: dict):
        """渲染模板"""
        templates = Jinja2Templates(directory=str(self.templates_dir))
        return templates.TemplateResponse(template_name, context)
    
    async def _process_video_background(self, record_id: str, url: str, api_key: Optional[str] = None):
        """后台处理视频"""
        try:
            print(f"开始处理视频: {url}")
            
            # 更新状态为处理中
            self._update_record(record_id, {"status": "processing"})
            
            # 设置输出目录为downloads
            output_dir = str(self.downloads_dir)
            
            # 确定使用的API key，优先级：传入参数 > settings.json > None
            final_api_key = api_key
            if not final_api_key:
                final_api_key = load_api_key_from_settings()
            
            # 创建总结器实例
            async with VideoAISummarizer(final_api_key) as summarizer:
                # 处理视频
                result = await summarizer.process_video(
                    url=url,
                    output_dir=output_dir,
                    keep_files=True
                )
                
                if result["success"]:
                    # 更新记录
                    updates = {
                        "status": "completed",
                        "video_path": result.get("video_path"),
                        "audio_path": result.get("audio_path"),
                        "transcription": result.get("transcription"),
                        "summary": result.get("summary"),
                        "transcription_file": result.get("transcription_file"),
                        "summary_file": result.get("summary_file"),
                        "video_folder": result.get("video_folder")
                    }
                    self._update_record(record_id, updates)
                    print(f"视频处理完成: {record_id}")
                else:
                    # 更新状态为失败
                    self._update_record(record_id, {"status": "failed"})
                    print(f"视频处理失败: {record_id}")
                    
        except Exception as e:
            print(f"处理视频时出错: {str(e)}")
            self._update_record(record_id, {"status": "failed"})
    
    def run(self, host: str = "127.0.0.1", port: int = 8000):
        """运行应用"""
        print(f"Web应用启动中...")
        print(f"访问地址: http://{host}:{port}")
        print(f"API文档: http://{host}:{port}/docs")
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="抖音视频AI总结Web应用")
    parser.add_argument("--host", default="127.0.0.1", help="服务器地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    
    args = parser.parse_args()
    
    # 创建并运行Web应用
    app = WebApp()
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
