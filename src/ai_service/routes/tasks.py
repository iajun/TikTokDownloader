"""
任务相关路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional
from datetime import datetime, timedelta
import os

from ..models import Task, TaskStatus, VideoSummary, EmailSubscription, Video
from ..db import get_db, get_db_session
from ..services import AISummarizer, EmailService, TranscriptionService, ObsidianService
from .schemas import TaskCreateRequest, BatchTaskCreateRequest, ResummarizeRequest, BatchDeleteRequest
from ..utils.task_queue import run_coro_blocking, run_io_blocking
from ..utils import S3Client
from ..utils.url_detector import analyze_url
from .dependencies import _extract_video_urls, _delete_task_files
import tempfile
from pathlib import Path

router = APIRouter()


@router.post("/tasks")
def create_task(request: TaskCreateRequest, db: Session = Depends(get_db)):
    """
    创建新的视频处理任务
    
    Args:
        request: 包含视频URL的请求体
    """
    try:
        # 创建新任务（video_id将在worker中提取并检查）
        task = Task(
            url=request.url,
            status=TaskStatus.PENDING.value,
            progress=0
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        return {
            "success": True,
            "message": "Task created successfully",
            "duplicate": False,
            "data": task.to_dict()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/analyze")
def analyze_task_url(url: str = Query(..., description="要分析的视频链接")):
    """
    分析视频链接，返回平台和类型信息
    
    Args:
        url: 视频链接
    """
    try:
        analysis = analyze_url(url)
        return {
            "success": True,
            "data": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析链接失败: {str(e)}")


@router.post("/tasks/batch")
def create_batch_tasks(request: BatchTaskCreateRequest, db: Session = Depends(get_db)):
    """
    批量创建视频处理任务
    
    Args:
        request: 包含合集/作者URL和类型的请求体
    """
    try:
        # 提取所有视频URL
        video_urls = run_coro_blocking(_extract_video_urls,
            request.url,
            request.type,
            request.max_count or 100
        )
        
        if not video_urls:
            return {
                "success": False,
                "message": "未能从链接中提取到视频URL",
                "data": {"total": 0, "created": 0, "urls": []}
            }
        
        # 批量创建多个任务（优化：使用bulk_insert提升性能）
        now = datetime.utcnow()
        tasks_data = [
            {
                "url": video_url,
                "status": TaskStatus.PENDING.value,
                "progress": 0,
                "created_at": now,
                "updated_at": now
            }
            for video_url in video_urls
        ]
        
        # 使用bulk_insert_mappings进行批量插入，性能更好
        db.bulk_insert_mappings(Task, tasks_data)
        db.commit()
        
        # 查询刚创建的任务以获取ID和完整信息
        # 使用order_by和limit获取最近创建的任务
        created_tasks = db.query(Task).options(joinedload(Task.video)).filter(
            Task.url.in_(video_urls),
            Task.status == TaskStatus.PENDING.value,
            Task.created_at >= now - timedelta(seconds=5)  # 只获取刚刚创建的（5秒内）
        ).order_by(desc(Task.created_at)).limit(len(video_urls)).all()
        
        # 转换为字典列表
        created_tasks = [task.to_dict() for task in created_tasks]
        
        return {
            "success": True,
            "message": f"成功创建 {len(created_tasks)} 个任务",
            "data": {
                "total": len(video_urls),
                "created": len(created_tasks),
                "urls": video_urls[:10],  # 只返回前10个URL作为示例
                "tasks": created_tasks[:10]  # 只返回前10个任务作为示例
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# S3客户端单例，避免重复创建
_s3_client = None

def _get_s3_client():
    """获取S3客户端单例"""
    global _s3_client
    if _s3_client is None:
        from ..utils import S3Client
        _s3_client = S3Client()
    return _s3_client


def _add_s3_urls(task_dict, task):
    """为任务添加S3预签名URL（优化：使用单例客户端，在线程池中生成URL）"""
    s3 = _get_s3_client()
    
    # 为所有文件路径生成预签名URL（有效期24小时）
    # 批量处理所有路径，减少重复调用
    paths_to_generate = []
    if task.video_path and task.video_path.startswith("videos/"):
        paths_to_generate.append(("video_url", task.video_path))
    if task.audio_path and task.audio_path.startswith("videos/"):
        paths_to_generate.append(("audio_url", task.audio_path))
    if task.transcription_path and task.transcription_path.startswith("videos/"):
        paths_to_generate.append(("transcription_url", task.transcription_path))
    if task.summary_path and task.summary_path.startswith("videos/"):
        paths_to_generate.append(("summary_url", task.summary_path))
    
    # 批量生成URL（在线程池中执行，避免阻塞主线程）
    def _generate_url(url_key, s3_path):
        try:
            return (url_key, s3.get_file_url(s3_path, expires_seconds=86400))
        except Exception as e:
            print(f"Error generating {url_key} URL: {e}")
            return (url_key, None)
    
    # 对于单个任务，URL生成很快，直接执行即可
    # 如果后续需要批量处理多个任务，可以考虑在线程池中执行
    for url_key, s3_path in paths_to_generate:
        _, url = _generate_url(url_key, s3_path)
        if url:
            task_dict[url_key] = url


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    """
    获取任务详情
    
    Args:
        task_id: 任务ID
    """
    # 使用 joinedload 预加载 video 关联，避免额外查询
    task = db.query(Task).options(joinedload(Task.video)).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 使用 join 查询以包含视频信息
    task_dict = task.to_dict(include_video=True)
    
    # 添加S3预签名URL
    _add_s3_urls(task_dict, task)
    
    return {
        "success": True,
        "data": task_dict
    }


@router.get("/tasks")
def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    获取任务列表
    
    Args:
        status: 任务状态筛选
        limit: 每页数量
        offset: 偏移量
    """
    # 使用 joinedload 预加载 video 关联，避免 N+1 查询
    query = db.query(Task).options(joinedload(Task.video))
    
    # 状态筛选
    if status:
        query = query.filter(Task.status == status)
    
    # 先获取总数（优化：只在需要时计算，如果不需要total可以省略）
    total = query.count()
    
    # 排序和分页（已经包含了预加载的video）
    tasks = query.order_by(desc(Task.created_at)).offset(offset).limit(limit).all()
    
    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [task.to_dict(include_video=True) for task in tasks]
    }


@router.get("/tasks/current/list")
def get_current_tasks(db: Session = Depends(get_db)):
    """
    获取当前正在处理的任务列表
    """
    current_statuses = [
        TaskStatus.PENDING.value,
        TaskStatus.DOWNLOADING.value,
        TaskStatus.EXTRACTING_AUDIO.value,
        TaskStatus.TRANSCRIBING.value,
        TaskStatus.SUMMARIZING.value
    ]
    
    # 使用 joinedload 预加载 video 关联，避免 N+1 查询
    tasks = db.query(Task).options(joinedload(Task.video)).filter(
        Task.status.in_(current_statuses)
    ).order_by(desc(Task.created_at)).all()
    
    return {
        "success": True,
        "data": [task.to_dict(include_video=True) for task in tasks]
    }


@router.get("/history")
def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    获取历史记录
    
    Args:
        limit: 每页数量
        offset: 偏移量
    """
    # 使用 joinedload 预加载 video 关联，避免 N+1 查询
    query = db.query(Task).options(joinedload(Task.video)).filter(
        Task.status.in_([TaskStatus.COMPLETED.value, TaskStatus.FAILED.value])
    )
    
    # 先获取总数（复用同一查询）
    total = query.count()
    
    # 查询已完成或失败的任务作为历史记录
    tasks = query.order_by(desc(Task.updated_at)).offset(offset).limit(limit).all()
    
    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [task.to_dict(include_video=True) for task in tasks]
    }


@router.get("/history/{task_id}")
def get_history_detail(task_id: int, db: Session = Depends(get_db)):
    """
    获取历史记录详情
    
    Args:
        task_id: 任务ID
    """
    # 使用 joinedload 预加载 video 关联，避免额外查询
    task = db.query(Task).options(joinedload(Task.video)).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="History record not found")
    
    # 生成预签名URL
    task_dict = task.to_dict(include_video=True)
    _add_s3_urls(task_dict, task)
    
    return {
        "success": True,
        "data": task_dict
    }


@router.delete("/tasks/batch")
def batch_delete_tasks(request: BatchDeleteRequest, db: Session = Depends(get_db)):
    """
    批量删除任务
    
    Args:
        request: 包含任务ID列表的请求体
    """
    if not request.task_ids:
        raise HTTPException(status_code=400, detail="task_ids cannot be empty")
    
    # 查询所有要删除的任务
    tasks = db.query(Task).filter(Task.id.in_(request.task_ids)).all()
    
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found")
    
    deleted_count = 0
    not_found_ids = []
    
    # 删除每个任务的文件和记录
    for task in tasks:
        try:
            # 删除S3文件
            _delete_task_files(task, db)
            
            # 删除数据库记录
            db.delete(task)
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting task {task.id}: {e}")
            # 继续删除其他任务，即使某个任务失败
    
    # 检查是否有未找到的任务ID
    found_ids = {task.id for task in tasks}
    not_found_ids = [task_id for task_id in request.task_ids if task_id not in found_ids]
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Successfully deleted {deleted_count} task(s)",
        "data": {
            "deleted_count": deleted_count,
            "requested_count": len(request.task_ids),
            "not_found_ids": not_found_ids
        }
    }


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """
    删除任务
    
    Args:
        task_id: 任务ID
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 删除S3文件
    _delete_task_files(task, db)
    
    # 删除数据库记录
    db.delete(task)
    db.commit()
    
    return {
        "success": True,
        "message": "Task deleted successfully"
    }


def _resummarize_background_task_sync(task_id: int, custom_prompt: Optional[str] = None):
    """后台任务：重新生成总结（同步，内部使用线程池执行重任务）"""
    try:
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not deepseek_api_key:
            print("DEEPSEEK_API_KEY not configured")
            return
        
        # 第一步：获取任务信息和转录内容，并更新状态为 SUMMARIZING
        with get_db_session() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            
            if not task:
                print(f"Task {task_id} not found")
                return
            
            # 检查是否有转录内容
            if not task.transcription:
                print(f"No transcription available for task {task_id}")
                return
            
            # 更新状态为 SUMMARIZING
            task.status = TaskStatus.SUMMARIZING.value
            task.progress = 90
            
            # 保存关键信息到局部变量（避免会话绑定问题）
            transcription = task.transcription
            video_id = task.video_id
        
        print(f"Starting to resummarize task {task_id}")
        
        # 第二步：执行 AI 总结（在线程池中执行，避免阻塞主线程）
        ai_summarizer = AISummarizer(deepseek_api_key)
        summary = run_io_blocking(
            ai_summarizer.summarize_with_ai,
            transcription,
            video_id,
            True,
            custom_prompt
        )
        
        # 第三步：更新任务状态为完成，并创建 VideoSummary 记录
        with get_db_session() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                if summary:
                    # 更新任务的 summary 字段（保持向后兼容）
                    task.summary = summary
                    task.summary_path = f"videos/{video_id}_summary.txt"
                    task.status = TaskStatus.COMPLETED.value
                    task.progress = 100
                    task.updated_at = datetime.utcnow()
                    
                    # 创建新的 VideoSummary 记录
                    # 获取当前总结数量，用于排序
                    summary_count = db.query(VideoSummary).filter(VideoSummary.task_id == task_id).count()
                    
                    # 生成总结名称
                    if custom_prompt:
                        # 如果使用自定义提示词，使用"自定义提示词总结"
                        summary_name = "自定义提示词总结"
                    else:
                        # 获取默认提示词名称
                        prompt_info = ai_summarizer._get_default_prompt_info()
                        summary_name = prompt_info['name'] if prompt_info else f"总结 {summary_count + 1}"
                    
                    video_summary = VideoSummary(
                        task_id=task_id,
                        name=summary_name,
                        content=summary,
                        custom_prompt=custom_prompt,
                        sort_order=summary_count
                    )
                    db.add(video_summary)
                    db.commit()
                    print(f"Summary regenerated successfully for task {task_id}, created VideoSummary record with name: {summary_name}")
                    
                    # 同步到 Obsidian
                    try:
                        # 获取视频信息
                        video = db.query(Video).filter(Video.video_id == video_id).first()
                        if video:
                            video_info = {
                                'video_id': video_id,
                                'platform': video.platform or 'douyin',
                                'desc': video.desc or '无标题',
                                'nickname': video.nickname or '未知',
                                'url': video.share_url or '',
                                'share_url': video.share_url or '',
                                'digg_count': video.digg_count or 0,
                                'comment_count': video.comment_count or 0,
                                'share_count': video.share_count or 0,
                            }
                            
                            obsidian_service = ObsidianService()
                            if obsidian_service.is_configured():
                                file_path = obsidian_service.save_summary_to_obsidian(
                                    video_info,
                                    summary,
                                    summary_name
                                )
                                if file_path:
                                    print(f"Summary synced to Obsidian: {file_path}")
                        else:
                            # 如果没有视频记录，使用任务信息
                            video_info = {
                                'video_id': video_id,
                                'platform': task.platform or 'douyin',
                                'desc': '无标题',
                                'nickname': '未知',
                                'url': task.url or '',
                                'share_url': task.url or '',
                                'digg_count': 0,
                                'comment_count': 0,
                                'share_count': 0,
                            }
                            
                            obsidian_service = ObsidianService()
                            if obsidian_service.is_configured():
                                file_path = obsidian_service.save_summary_to_obsidian(
                                    video_info,
                                    summary,
                                    summary_name
                                )
                                if file_path:
                                    print(f"Summary synced to Obsidian: {file_path}")
                    except Exception as e:
                        print(f"Failed to sync summary to Obsidian: {str(e)}")
                        # 不影响主流程
                
                else:
                    task.status = TaskStatus.COMPLETED.value
                    task.progress = 100
                    task.updated_at = datetime.utcnow()
                    print(f"Failed to generate summary for task {task_id}")
                
    except Exception as e:
        print(f"Error resummarizing task {task_id}: {str(e)}")
        # 更新状态为失败
        with get_db_session() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.progress = 100
                task.error_message = str(e)
                task.updated_at = datetime.utcnow()


@router.post("/tasks/{task_id}/resummarize")
def resummarize_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    request: Optional[ResummarizeRequest] = None,
    db: Session = Depends(get_db)
):
    """
    重新生成总结（异步后台处理）
    
    Args:
        task_id: 任务ID
        background_tasks: FastAPI 后台任务
        request: 请求体，包含可选的 custom_prompt
    """
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 检查任务是否已完成
        if task.status != TaskStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Task is not completed yet")
        
        # 检查是否有转录内容
        if not task.transcription:
            raise HTTPException(status_code=400, detail="No transcription available")
        
        # 检查是否配置了API密钥
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not deepseek_api_key:
            raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY not configured")
        
        # 获取自定义提示词
        custom_prompt = request.custom_prompt if request and request.custom_prompt else None
        
        # 创建后台任务（不等待完成）
        background_tasks.add_task(_resummarize_background_task_sync, task_id, custom_prompt)
        
        return {
            "success": True,
            "message": "Summary regeneration started in background",
            "data": task.to_dict(include_video=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _retranscribe_background_task_sync(task_id: int, model_name: Optional[str] = None):
    """后台任务：重新转录音频（同步，内部使用进程池执行CPU密集型任务）"""
    try:
        # 第一步：获取任务信息和音频文件路径，并更新状态为 TRANSCRIBING
        with get_db_session() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            
            if not task:
                print(f"Task {task_id} not found")
                return
            
            # 检查是否有音频文件路径
            if not task.audio_path:
                print(f"No audio file available for task {task_id}")
                return
            
            # 检查音频文件是否存在于S3
            s3_client = S3Client()
            if not s3_client.file_exists(task.audio_path):
                print(f"Audio file not found in S3: {task.audio_path}")
                return
            
            # 更新状态为 TRANSCRIBING
            task.status = TaskStatus.TRANSCRIBING.value
            task.progress = 60
            
            # 保存关键信息到局部变量（避免会话绑定问题）
            audio_path_s3 = task.audio_path
            video_id = task.video_id
        
        print(f"Starting to retranscribe task {task_id}")
        
        # 第二步：从S3下载音频文件到本地临时文件
        temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
        temp_dir.mkdir(exist_ok=True)
        local_audio_path = temp_dir / f"{video_id}_retranscribe_audio.wav"
        
        if not s3_client.download_file(audio_path_s3, str(local_audio_path)):
            print(f"Failed to download audio file from S3: {audio_path_s3}")
            return
        
        try:
            # 第三步：执行转录（在CPU进程池中执行，避免阻塞主线程）
            transcription_service = TranscriptionService(model_name or "base")
            transcription = transcription_service.transcribe(str(local_audio_path), video_id)
            
            if not transcription:
                print(f"Failed to transcribe audio for task {task_id}")
                return
            
            # 第四步：更新任务状态为完成，更新转录内容
            with get_db_session() as db:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    # 更新转录内容
                    task.transcription = transcription
                    task.transcription_path = f"videos/{video_id}_transcription.txt"
                    task.status = TaskStatus.COMPLETED.value
                    task.progress = 100
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    print(f"Transcription regenerated successfully for task {task_id}")
                    
                    # 可选：上传转录文本到S3（如果需要）
                    try:
                        s3_client.upload_from_memory(
                            transcription.encode('utf-8'),
                            task.transcription_path,
                            content_type="text/plain; charset=utf-8"
                        )
                    except Exception as e:
                        print(f"Failed to upload transcription to S3: {e}")
        
        finally:
            # 清理临时文件
            try:
                if local_audio_path.exists():
                    local_audio_path.unlink()
            except Exception as e:
                print(f"Failed to clean up temporary audio file: {e}")
                
    except Exception as e:
        print(f"Error retranscribing task {task_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        # 更新状态为失败
        with get_db_session() as db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value
                task.progress = 100
                task.error_message = str(e)
                task.updated_at = datetime.utcnow()
                db.commit()


@router.post("/tasks/{task_id}/retranscribe")
def retranscribe_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    model_name: Optional[str] = Query(None, description="可选的Whisper模型名称（默认: base）"),
    db: Session = Depends(get_db)
):
    """
    重新转录音频（异步后台处理）
    
    Args:
        task_id: 任务ID
        background_tasks: FastAPI 后台任务
        model_name: 可选的Whisper模型名称（默认: base）
    """
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 检查任务是否已完成
        if task.status != TaskStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Task is not completed yet")
        
        # 检查是否有音频文件
        if not task.audio_path:
            raise HTTPException(status_code=400, detail="No audio file available")
        
        # 检查音频文件是否存在于S3
        s3_client = S3Client()
        if not s3_client.file_exists(task.audio_path):
            raise HTTPException(status_code=404, detail="Audio file not found in S3")
        
        # 创建后台任务（不等待完成）
        background_tasks.add_task(_retranscribe_background_task_sync, task_id, model_name)
        
        return {
            "success": True,
            "message": "Transcription regeneration started in background",
            "data": task.to_dict(include_video=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: int, db: Session = Depends(get_db)):
    """
    重新执行失败的任务
    
    Args:
        task_id: 任务ID
    """
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 检查任务是否失败
        if task.status == TaskStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Task is already completed")
        
        # 重置任务状态
        task.status = TaskStatus.PENDING.value
        task.progress = 0
        task.error_message = None
        task.updated_at = datetime.utcnow()
        task.completed_at = None
        db.commit()
        
        return {
            "success": True,
            "message": "Task retry initiated successfully",
            "data": task.to_dict(include_video=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/refresh-urls")
def refresh_urls(task_id: int, db: Session = Depends(get_db)):
    """
    刷新任务的预签名URL
    
    Args:
        task_id: 任务ID
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 生成新的预签名URL
    task_dict = task.to_dict(include_video=True)
    _add_s3_urls(task_dict, task)
    
    return {
        "success": True,
        "data": task_dict
    }


@router.post("/tasks/{task_id}/send-email")
def send_task_email(task_id: int, db: Session = Depends(get_db)):
    """
    发送任务邮件到所有激活的订阅邮箱
    
    Args:
        task_id: 任务ID
    """
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 检查任务是否已完成且有总结
        if task.status != TaskStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Task is not completed yet")
        
        if not task.summary:
            raise HTTPException(status_code=400, detail="Task has no summary available")
        
        # 检查邮件服务是否配置
        email_service = EmailService()
        if not email_service.is_configured():
            raise HTTPException(status_code=500, detail="Email service is not configured")
        
        # 获取所有激活的订阅邮箱
        emails = []
        with get_db_session() as session:
            subscriptions = session.query(EmailSubscription).filter(
                EmailSubscription.is_active == True
            ).all()
            # 在会话内提取所有邮件地址，避免会话关闭后访问属性
            emails = [sub.email for sub in subscriptions]
        
        if not emails:
            raise HTTPException(status_code=400, detail="No active email subscriptions found")
        
        # 构建视频信息字典
        video_info = {
            'video_id': task.video_id or 'unknown',
            'platform': task.platform or 'douyin',
            'desc': task.video.desc if task.video and task.video.desc else '无标题',
            'nickname': task.video.nickname if task.video and task.video.nickname else '未知',
            'url': task.url,
            'share_url': task.video.share_url if task.video and task.video.share_url else task.url,
            'digg_count': task.video.digg_count if task.video and task.video.digg_count else 0,
            'comment_count': task.video.comment_count if task.video and task.video.comment_count else 0,
            'share_count': task.video.share_count if task.video and task.video.share_count else 0,
        }
        
        # 发送邮件到所有订阅邮箱
        results = email_service.send_batch_summary_emails(
            emails,
            video_info,
            task.summary
        )
        
        # 统计发送结果
        success_count = sum(1 for success in results.values() if success)
        failed_count = len(results) - success_count
        
        return {
            "success": True,
            "message": f"Email sent to {success_count} subscriber(s)",
            "data": {
                "task_id": task_id,
                "total_emails": len(emails),
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/obsidian/status")
def get_obsidian_status():
    """检查 Obsidian 服务是否已配置"""
    try:
        obsidian_service = ObsidianService()
        is_configured = obsidian_service.is_configured()
        
        return {
            "success": True,
            "data": {
                "is_configured": is_configured,
                "vault_path": str(obsidian_service.vault_path) if obsidian_service.vault_path else None,
                "summaries_folder": obsidian_service.summaries_folder
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "data": {
                "is_configured": False
            }
        }


@router.post("/tasks/{task_id}/send-to-obsidian")
def send_task_to_obsidian(task_id: int, db: Session = Depends(get_db)):
    """
    手动发送任务总结到 Obsidian
    
    Args:
        task_id: 任务ID
    """
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 检查任务是否已完成且有总结
        if task.status != TaskStatus.COMPLETED.value:
            raise HTTPException(status_code=400, detail="Task is not completed yet")
        
        # 获取最新的总结
        latest_summary = db.query(VideoSummary).filter(
            VideoSummary.task_id == task_id
        ).order_by(VideoSummary.created_at.desc()).first()
        
        summary_content = None
        summary_name = "总结"
        
        if latest_summary:
            summary_content = latest_summary.content
            summary_name = latest_summary.name or "总结"
        elif task.summary:
            summary_content = task.summary
        else:
            raise HTTPException(status_code=400, detail="Task has no summary available")
        
        # 检查 Obsidian 服务是否配置
        obsidian_service = ObsidianService()
        if not obsidian_service.is_configured():
            raise HTTPException(status_code=500, detail="Obsidian service is not configured")
        
        # 构建视频信息字典
        video_info = {
            'video_id': task.video_id or 'unknown',
            'platform': task.platform or 'douyin',
            'desc': task.video.desc if task.video and task.video.desc else '无标题',
            'nickname': task.video.nickname if task.video and task.video.nickname else '未知',
            'url': task.url,
            'share_url': task.video.share_url if task.video and task.video.share_url else task.url,
            'digg_count': task.video.digg_count if task.video and task.video.digg_count else 0,
            'comment_count': task.video.comment_count if task.video and task.video.comment_count else 0,
            'share_count': task.video.share_count if task.video and task.video.share_count else 0,
        }
        
        # 保存到 Obsidian
        file_path = obsidian_service.save_summary_to_obsidian(
            video_info,
            summary_content,
            summary_name
        )
        
        if not file_path:
            raise HTTPException(status_code=500, detail="Failed to save summary to Obsidian")
        
        return {
            "success": True,
            "message": "Summary saved to Obsidian successfully",
            "data": {
                "task_id": task_id,
                "file_path": file_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

