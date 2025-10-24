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
from typing import Optional, List, Dict, Any
import json
import re
import uuid
from enum import Enum
from dataclasses import dataclass, asdict

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

from src.ai import VideoAISummarizer
from src.ai.main_cli import load_api_key_from_settings
from src.ai.video_processor import VideoProcessor
from src.ai.file_manager import FileManager
from src.application import TikTokDownloader


def extract_douyin_url(text: str) -> Optional[str]:
    """从文本中提取抖音链接"""
    try:
        # 抖音链接的正则表达式模式
        patterns = [
            r'https://v\.douyin\.com/[a-zA-Z0-9_]+/?',  # 标准短链接，包含下划线
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


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    DOWNLOADING = "downloading"  # 下载中
    PROCESSING = "processing"    # 处理中（音频提取、转录、总结）
    COMPLETED = "completed"      # 完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"      # 已取消


@dataclass
class TaskInfo:
    """任务信息"""
    id: str
    url: str
    status: TaskStatus
    progress: int = 0  # 进度百分比 0-100
    message: str = ""
    error: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    api_key: Optional[str] = None
    extracted_url: Optional[str] = None
    final_url: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    transcription: Optional[str] = None
    summary: Optional[str] = None
    transcription_file: Optional[str] = None
    summary_file: Optional[str] = None
    video_folder: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


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


class TaskManager:
    """任务管理器，支持并行任务处理"""
    
    def __init__(self, max_concurrent_tasks: int = 3):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.tasks: Dict[str, TaskInfo] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._lock = asyncio.Lock()
    
    async def create_task(self, url: str, api_key: Optional[str] = None) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        task_info = TaskInfo(
            id=task_id,
            url=url,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            api_key=api_key
        )
        
        async with self._lock:
            self.tasks[task_id] = task_info
        
        return task_id
    
    async def start_task(self, task_id: str, task_func, *args, **kwargs):
        """启动任务（非阻塞）"""
        async with self.semaphore:
            async with self._lock:
                if task_id not in self.tasks:
                    return
                
                task_info = self.tasks[task_id]
                task_info.status = TaskStatus.DOWNLOADING
                task_info.started_at = datetime.now().isoformat()
                task_info.message = "任务已开始"
            
            # 创建异步任务并添加回调处理
            running_task = asyncio.create_task(
                self._run_task_with_callback(task_id, task_func, *args, **kwargs)
            )
            
            async with self._lock:
                self.running_tasks[task_id] = running_task
    
    async def _run_task_with_callback(self, task_id: str, task_func, *args, **kwargs):
        """运行任务并处理回调"""
        try:
            await task_func(task_id, *args, **kwargs)
        except asyncio.CancelledError:
            async with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].status = TaskStatus.CANCELLED
                    self.tasks[task_id].message = "任务已取消"
            raise
        except Exception as e:
            async with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].status = TaskStatus.FAILED
                    self.tasks[task_id].error = str(e)
                    self.tasks[task_id].message = f"任务失败: {str(e)}"
        finally:
            async with self._lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                if task_id in self.tasks:
                    self.tasks[task_id].completed_at = datetime.now().isoformat()
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            if task_id in self.running_tasks:
                running_task = self.running_tasks[task_id]
                running_task.cancel()
                return True
            elif task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.CANCELLED
                self.tasks[task_id].message = "任务已取消"
                return True
        return False
    
    async def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息"""
        async with self._lock:
            return self.tasks.get(task_id)
    
    async def get_all_tasks(self) -> List[TaskInfo]:
        """获取所有任务"""
        async with self._lock:
            return list(self.tasks.values())
    
    async def update_task_status(self, task_id: str, status: TaskStatus, 
                               progress: int = None, message: str = None, error: str = None):
        """更新任务状态"""
        async with self._lock:
            if task_id in self.tasks:
                task_info = self.tasks[task_id]
                task_info.status = status
                if progress is not None:
                    task_info.progress = progress
                if message is not None:
                    task_info.message = message
                if error is not None:
                    task_info.error = error
    
    async def update_task_result(self, task_id: str, **kwargs):
        """更新任务结果"""
        async with self._lock:
            if task_id in self.tasks:
                task_info = self.tasks[task_id]
                for key, value in kwargs.items():
                    if hasattr(task_info, key):
                        setattr(task_info, key, value)
    
    def get_running_count(self) -> int:
        """获取正在运行的任务数量"""
        return len(self.running_tasks)
    
    def get_pending_count(self) -> int:
        """获取等待中的任务数量"""
        return sum(1 for task in self.tasks.values() if task.status == TaskStatus.PENDING)


class WebApp:
    def __init__(self, max_concurrent_tasks: int = 3):
        self.app = FastAPI(
            title="抖音视频AI总结工具",
            description="输入抖音链接，自动下载视频、提取音频、转文字并AI总结",
            version="1.0.0"
        )
        
        # 创建必要的目录
        self.static_dir = Path("static")
        self.templates_dir = Path("templates")
        self.volume_download_dir = Path("Volume/Download")  # 使用Volume目录
        
        for dir_path in [self.static_dir, self.templates_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # 确保Volume/Download目录存在
        self.volume_download_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化任务管理器
        self.task_manager = TaskManager(max_concurrent_tasks)
        
        # 初始化TikTok下载器（不创建VideoProcessor，每个任务独立创建）
        self.downloader = TikTokDownloader()
        
        # 初始化文件管理器
        self.file_manager = FileManager()
        
        # 异步初始化下载器配置
        self._downloader_initialized = False
        
        # 检查API key配置状态
        self.api_key_configured = self._check_api_key_config()
        
        # 设置路由
        self._setup_routes()
        
        # 挂载静态文件
        self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
        self.app.mount("/downloads", StaticFiles(directory=str(self.volume_download_dir)), name="downloads")
    
    def _check_api_key_config(self) -> bool:
        """检查API key是否已配置"""
        api_key = load_api_key_from_settings()
        return api_key is not None and api_key.strip() != ""
    
    async def _ensure_downloader_initialized(self):
        """确保下载器已正确初始化"""
        if not self._downloader_initialized:
            try:
                # 手动设置配置（Web应用不需要数据库）
                self.downloader.config = {
                    "Record": False,  # 禁用数据库记录
                    "Logger": 1
                }
                self.downloader.check_config()
                await self.downloader.check_settings(False)
                # 设置输出目录为Volume（让folder_name自动添加Download子目录）
                self.downloader.parameter.root = Path("Volume")
                print(f"初始化成功，设置下载目录: {self.downloader.parameter.root}")
                self._downloader_initialized = True
            except Exception as e:
                print(f"初始化下载器失败: {str(e)}")
                raise e
    
    async def _initialize_task_downloader(self, downloader: TikTokDownloader):
        """为任务初始化独立的下载器"""
        try:
            # 手动设置配置（Web应用不需要数据库）
            downloader.config = {
                "Record": False,  # 禁用数据库记录
                "Logger": 1
            }
            downloader.check_config()
            await downloader.check_settings(False)
            # 设置输出目录为Volume（让folder_name自动添加Download子目录）
            downloader.parameter.root = Path("Volume")
            print(f"任务下载器初始化成功，设置下载目录: {downloader.parameter.root}")
        except Exception as e:
            print(f"任务下载器初始化失败: {str(e)}")
            raise e
    
    async def _get_record(self, record_id: str) -> Optional[dict]:
        """获取单个记录"""
        # 从Volume目录中查找现有文件
        volume_records = await self._scan_existing_files()
        for record in volume_records:
            if record['id'] == record_id:
                return record
        
        return None
    
    def _normalize_filename(self, filename: str) -> str:
        """规范化文件名，移除或替换特殊字符"""
        import re
        # 移除或替换可能导致问题的特殊字符
        # 保留中文字符、英文字母、数字、连字符、下划线
        normalized = re.sub(r'[^\w\u4e00-\u9fff\-_]', '_', filename)
        # 移除连续的下划线
        normalized = re.sub(r'_+', '_', normalized)
        # 移除开头和结尾的下划线
        normalized = normalized.strip('_')
        return normalized
    
    def _generate_safe_id(self, video_name: str, timestamp: int) -> str:
        """生成安全的记录ID"""
        safe_name = self._normalize_filename(video_name)
        # 限制ID长度，避免过长
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        return f"existing_{safe_name}_{timestamp}"
    
    async def _scan_existing_files(self) -> List[dict]:
        """扫描Volume/Download目录中的现有文件"""
        existing_records = []
        
        if not self.volume_download_dir.exists():
            return existing_records
        
        try:
            # 扫描所有视频文件
            video_files = []
            for ext in ['*.mp4', '*.mov', '*.avi']:
                video_files.extend(self.volume_download_dir.glob(ext))
            
            for video_file in video_files:
                video_name = video_file.stem  # 不带扩展名的文件名
                
                # 使用FileManager的前缀匹配查找对应的音频、转录和总结文件
                audio_file = self.file_manager.find_audio_file(
                    self.volume_download_dir, 
                    video_name
                )
                transcription_file = self.file_manager.find_transcription_file(
                    self.volume_download_dir, 
                    video_name
                )
                summary_file = self.file_manager.find_summary_file(
                    self.volume_download_dir, 
                    video_name
                )
                
                # 读取文件内容
                transcription = None
                summary = None
                
                if transcription_file and transcription_file.exists():
                    try:
                        with open(transcription_file, 'r', encoding='utf-8') as f:
                            transcription = f.read().strip()
                    except:
                        pass
                
                if summary_file and summary_file.exists():
                    try:
                        with open(summary_file, 'r', encoding='utf-8') as f:
                            summary = f.read().strip()
                    except:
                        pass
                
                # 获取文件修改时间作为创建时间
                file_time = datetime.fromtimestamp(video_file.stat().st_mtime)
                
                # 创建记录
                record = {
                    "id": self._generate_safe_id(video_name, int(file_time.timestamp())),
                    "url": f"Volume/Download/{video_name}",  # 使用相对路径
                    "video_path": str(video_file),
                    "video_name": video_name,  # 添加原始文件名
                    "audio_path": str(audio_file) if audio_file and audio_file.exists() else None,
                    "transcription": transcription,
                    "summary": summary,
                    "transcription_file": str(transcription_file) if transcription_file and transcription_file.exists() else None,
                    "summary_file": str(summary_file) if summary_file and summary_file.exists() else None,
                    "video_folder": str(self.volume_download_dir),
                    "created_at": file_time.isoformat(),
                    "status": "completed",
                    "source": "volume"  # 标记来源
                }
                
                existing_records.append(record)
            
            print(f"扫描到 {len(existing_records)} 个现有视频文件")
            return existing_records
            
        except Exception as e:
            print(f"扫描现有文件失败: {str(e)}")
            return existing_records
    
    async def _get_all_records(self) -> List[dict]:
        """获取所有记录（从Volume目录中）"""
        # 获取Volume目录中的现有文件
        volume_records = await self._scan_existing_files()
        
        # 按创建时间倒序排列
        volume_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return volume_records
    
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
            records = await self._get_all_records()
            return self._render_template("history.html", {
                "request": request,
                "records": records
            })
        
        @self.app.get("/tasks", response_class=HTMLResponse)
        async def tasks(request: Request):
            """任务管理页面"""
            return self._render_template("tasks.html", {
                "request": request
            })
        
        @self.app.get("/detail/{record_id}", response_class=HTMLResponse)
        async def detail(request: Request, record_id: str):
            """详情页面"""
            # 对record_id进行URL解码
            import urllib.parse
            decoded_record_id = urllib.parse.unquote(record_id)
            return self._render_template("detail.html", {
                "request": request,
                "record_id": decoded_record_id
            })
        
        @self.app.post("/api/process")
        async def process_video(request: VideoProcessRequest):
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
                
                # 创建任务
                task_id = await self.task_manager.create_task(final_url, request.api_key)
                
                # 更新任务信息
                await self.task_manager.update_task_result(
                    task_id,
                    extracted_url=extracted_url,
                    final_url=final_url
                )
                
                # 启动任务
                asyncio.create_task(
                    self.task_manager.start_task(
                        task_id,
                        self._process_video_background,
                        final_url,
                        request.api_key
                    )
                )
                
                return JSONResponse({
                    "success": True,
                    "message": f"视频处理已开始 - {extraction_message}",
                    "task_id": task_id,
                    "extracted_url": extracted_url,
                    "final_url": final_url
                })
                
            except Exception as e:
                return JSONResponse({
                    "success": False,
                    "message": f"处理失败: {str(e)}"
                }, status_code=500)
        
        @self.app.get("/api/task/{task_id}")
        async def get_task_status(task_id: str):
            """获取任务状态"""
            task = await self.task_manager.get_task(task_id)
            if not task:
                raise HTTPException(status_code=404, detail="任务不存在")
            
            return JSONResponse({
                "success": True,
                "task": task.to_dict()
            })
        
        @self.app.post("/api/task/{task_id}/cancel")
        async def cancel_task(task_id: str):
            """取消任务"""
            success = await self.task_manager.cancel_task(task_id)
            if not success:
                raise HTTPException(status_code=404, detail="任务不存在或无法取消")
            
            return JSONResponse({
                "success": True,
                "message": "任务已取消"
            })
        
        @self.app.get("/api/tasks")
        async def get_all_tasks():
            """获取所有任务"""
            tasks = await self.task_manager.get_all_tasks()
            return JSONResponse({
                "success": True,
                "tasks": [task.to_dict() for task in tasks],
                "running_count": self.task_manager.get_running_count(),
                "pending_count": self.task_manager.get_pending_count()
            })
        
        @self.app.get("/api/status/{record_id}")
        async def get_status(record_id: str):
            """获取处理状态（兼容旧接口）"""
            record = await self._get_record(record_id)
            if not record:
                raise HTTPException(status_code=404, detail="记录不存在")
            
            return JSONResponse({
                "success": True,
                "record": record
            })
        
        @self.app.get("/api/records")
        async def get_records():
            """获取所有记录"""
            records = await self._get_all_records()
            return JSONResponse({
                "success": True,
                "records": records
            })
        
        @self.app.get("/api/record/{record_id}")
        async def get_record(record_id: str):
            """获取单个记录详情"""
            # 对record_id进行URL解码
            import urllib.parse
            decoded_record_id = urllib.parse.unquote(record_id)
            record = await self._get_record(decoded_record_id)
            if not record:
                raise HTTPException(status_code=404, detail="记录不存在")
            
            return JSONResponse({
                "success": True,
                "record": record
            })
        
        @self.app.post("/api/resummarize/{record_id}")
        async def resummarize_video(record_id: str, request: Request):
            """重新总结视频"""
            try:
                # 对record_id进行URL解码
                import urllib.parse
                decoded_record_id = urllib.parse.unquote(record_id)
                
                # 获取记录信息
                record = await self._get_record(decoded_record_id)
                if not record:
                    raise HTTPException(status_code=404, detail="记录不存在")
                
                # 检查是否有音频文件
                if not record.get('audio_path'):
                    raise HTTPException(status_code=400, detail="没有找到音频文件，无法重新总结")
                
                # 检查API key配置
                api_key = load_api_key_from_settings()
                if not api_key:
                    raise HTTPException(status_code=400, detail="未配置API密钥，无法进行AI总结")
                
                # 创建重新总结任务
                task_id = await self.task_manager.create_task(record['url'], api_key)
                
                # 更新任务信息
                await self.task_manager.update_task_result(
                    task_id,
                    extracted_url=record['url'],
                    final_url=record['url'],
                    video_path=record.get('video_path'),
                    audio_path=record.get('audio_path'),
                    transcription=record.get('transcription'),
                    transcription_file=record.get('transcription_file'),
                    video_folder=record.get('video_folder')
                )
                
                # 启动重新总结任务
                asyncio.create_task(
                    self.task_manager.start_task(
                        task_id,
                        self._resummarize_video_background,
                        record,
                        api_key
                    )
                )
                
                return JSONResponse({
                    "success": True,
                    "message": "重新总结任务已开始",
                    "task_id": task_id
                })
                
            except HTTPException:
                raise
            except Exception as e:
                return JSONResponse({
                    "success": False,
                    "message": f"重新总结失败: {str(e)}"
                }, status_code=500)
        
        @self.app.get("/download/{file_path:path}")
        async def download_file(file_path: str):
            """下载文件"""
            try:
                # 构建完整的文件路径
                full_path = Path(file_path)
                
                # 安全检查：确保文件路径在允许的目录内
                if not full_path.exists():
                    raise HTTPException(status_code=404, detail="文件不存在")
                
                # 检查文件是否在允许的目录内
                allowed_dirs = [
                    self.volume_download_dir,
                    Path("Volume")
                ]
                
                is_allowed = False
                for allowed_dir in allowed_dirs:
                    try:
                        full_path.resolve().relative_to(allowed_dir.resolve())
                        is_allowed = True
                        break
                    except ValueError:
                        continue
                
                if not is_allowed:
                    raise HTTPException(status_code=403, detail="访问被拒绝")
                
                return FileResponse(
                    path=str(full_path),
                    filename=full_path.name,
                    media_type='application/octet-stream'
                )
                
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")
    
    def _render_template(self, template_name: str, context: dict):
        """渲染模板"""
        templates = Jinja2Templates(directory=str(self.templates_dir))
        return templates.TemplateResponse(template_name, context)
    
    async def _process_video_background(self, task_id: str, url: str, api_key: Optional[str] = None):
        """后台处理视频"""
        try:
            print(f"开始处理视频任务 {task_id}: {url}")
            
            # 更新任务状态为下载中
            await self.task_manager.update_task_status(
                task_id, 
                TaskStatus.DOWNLOADING, 
                progress=10, 
                message="正在下载视频..."
            )
            
            # 为每个任务创建独立的下载器和VideoProcessor实例
            task_downloader = TikTokDownloader()
            await self._initialize_task_downloader(task_downloader)
            video_processor = VideoProcessor(task_downloader)
            
            # 设置输出目录为Volume（让folder_name自动添加Download子目录）
            output_dir = str(Path("Volume"))
            
            # 使用VideoProcessor下载视频
            video_path, detail_data = await video_processor.download_video(
                url=url,
                output_dir=output_dir,
                force_download=False
            )
            
            if video_path and detail_data:
                print(f"视频下载成功: {video_path}")
                
                # 更新任务状态为处理中
                await self.task_manager.update_task_status(
                    task_id, 
                    TaskStatus.PROCESSING, 
                    progress=50, 
                    message="正在处理视频..."
                )
                
                # 更新任务结果
                await self.task_manager.update_task_result(
                    task_id,
                    video_path=video_path,
                    video_folder=str(Path(video_path).parent)
                )
                
                # 确定使用的API key
                final_api_key = api_key
                if not final_api_key:
                    final_api_key = load_api_key_from_settings()
                
                # 如果有API key，进行AI总结
                if final_api_key:
                    try:
                        await self.task_manager.update_task_status(
                            task_id, 
                            TaskStatus.PROCESSING, 
                            progress=70, 
                            message="正在进行AI总结..."
                        )
                        
                        async with VideoAISummarizer(final_api_key) as summarizer:
                            # 处理视频（音频提取、转录、总结）
                            result = await summarizer.process_video(
                                url=url,
                                output_dir=output_dir,
                                keep_files=True
                            )
                            
                            if result["success"]:
                                print(f"AI总结完成: {task_id}")
                                
                                # 更新任务结果
                                await self.task_manager.update_task_result(
                                    task_id,
                                    audio_path=result.get("audio_path"),
                                    transcription=result.get("transcription"),
                                    summary=result.get("summary"),
                                    transcription_file=result.get("transcription_file"),
                                    summary_file=result.get("summary_file")
                                )
                                
                                # 更新任务状态为完成
                                await self.task_manager.update_task_status(
                                    task_id, 
                                    TaskStatus.COMPLETED, 
                                    progress=100, 
                                    message="处理完成"
                                )
                            else:
                                print(f"AI总结失败: {task_id}")
                                await self.task_manager.update_task_status(
                                    task_id, 
                                    TaskStatus.FAILED, 
                                    progress=70, 
                                    message="AI总结失败",
                                    error=result.get("error", "未知错误")
                                )
                    except Exception as e:
                        print(f"AI总结过程中出错: {str(e)}")
                        await self.task_manager.update_task_status(
                            task_id, 
                            TaskStatus.FAILED, 
                            progress=70, 
                            message="AI总结过程中出错",
                            error=str(e)
                        )
                else:
                    print("未配置API key，跳过AI总结")
                    # 更新任务状态为完成（仅下载）
                    await self.task_manager.update_task_status(
                        task_id, 
                        TaskStatus.COMPLETED, 
                        progress=100, 
                        message="视频下载完成（未配置API key，跳过AI总结）"
                    )
                
                print(f"视频处理完成: {task_id}")
            else:
                print(f"视频下载失败: {task_id}")
                await self.task_manager.update_task_status(
                    task_id, 
                    TaskStatus.FAILED, 
                    progress=10, 
                    message="视频下载失败",
                    error="无法下载视频或获取视频详情"
                )
                    
        except asyncio.CancelledError:
            print(f"任务 {task_id} 被取消")
            await self.task_manager.update_task_status(
                task_id, 
                TaskStatus.CANCELLED, 
                message="任务已取消"
            )
            raise
        except Exception as e:
            print(f"处理视频时出错: {str(e)}")
            await self.task_manager.update_task_status(
                task_id, 
                TaskStatus.FAILED, 
                message="处理过程中出错",
                error=str(e)
            )
    
    async def _resummarize_video_background(self, task_id: str, record: dict, api_key: str):
        """后台重新总结视频"""
        try:
            print(f"开始重新总结任务 {task_id}")
            
            # 更新任务状态为处理中
            await self.task_manager.update_task_status(
                task_id, 
                TaskStatus.PROCESSING, 
                progress=20, 
                message="正在重新进行AI总结..."
            )
            
            # 检查音频文件是否存在
            audio_path = record.get('audio_path')
            if not audio_path or not Path(audio_path).exists():
                await self.task_manager.update_task_status(
                    task_id, 
                    TaskStatus.FAILED, 
                    progress=20, 
                    message="音频文件不存在",
                    error="无法找到音频文件进行重新总结"
                )
                return
            
            # 设置输出目录为音频文件所在的目录（即Volume/Download下的视频文件夹）
            output_dir = str(Path(audio_path).parent)
            
            # 使用VideoAISummarizer进行重新总结
            async with VideoAISummarizer(api_key) as summarizer:
                # 只进行AI总结，不重新下载和处理视频
                result = await summarizer.summarize_audio_only(
                    audio_path=audio_path,
                    output_dir=output_dir,
                    keep_files=True
                )
                
                if result["success"]:
                    print(f"重新总结完成: {task_id}")
                    
                    # 更新任务结果
                    await self.task_manager.update_task_result(
                        task_id,
                        summary=result.get("summary"),
                        summary_file=result.get("summary_file")
                    )
                    
                    # 更新任务状态为完成
                    await self.task_manager.update_task_status(
                        task_id, 
                        TaskStatus.COMPLETED, 
                        progress=100, 
                        message="重新总结完成"
                    )
                else:
                    print(f"重新总结失败: {task_id}")
                    await self.task_manager.update_task_status(
                        task_id, 
                        TaskStatus.FAILED, 
                        progress=20, 
                        message="重新总结失败",
                        error=result.get("error", "未知错误")
                    )
                    
        except asyncio.CancelledError:
            print(f"重新总结任务 {task_id} 被取消")
            await self.task_manager.update_task_status(
                task_id, 
                TaskStatus.CANCELLED, 
                message="任务已取消"
            )
            raise
        except Exception as e:
            print(f"重新总结时出错: {str(e)}")
            await self.task_manager.update_task_status(
                task_id, 
                TaskStatus.FAILED, 
                message="重新总结过程中出错",
                error=str(e)
            )
    
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
    parser.add_argument("--max-concurrent", type=int, default=3, help="最大并发任务数")
    
    args = parser.parse_args()
    
    # 创建并运行Web应用
    app = WebApp(max_concurrent_tasks=args.max_concurrent)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
