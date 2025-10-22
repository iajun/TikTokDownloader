"""
任务相关路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime
import os

from ..models import Task, TaskStatus, VideoSummary
from ..db import get_db, get_db_session
from ..services import AISummarizer
from .schemas import TaskCreateRequest, BatchTaskCreateRequest, ResummarizeRequest, BatchDeleteRequest
from ..utils.task_queue import run_coro_blocking, run_io_blocking
from .dependencies import _extract_video_urls, _delete_task_files

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
        
        # 创建多个任务
        created_tasks = []
        for video_url in video_urls:
            task = Task(
                url=video_url,
                status=TaskStatus.PENDING.value,
                progress=0
            )
            db.add(task)
            created_tasks.append(task.to_dict())
        
        db.commit()
        
        # 刷新所有任务ID
        for i, task in enumerate(created_tasks):
            task['id'] = task.get('id', i + 1)
        
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


def _add_s3_urls(task_dict, task):
    """为任务添加S3预签名URL"""
    from ..utils import S3Client
    s3 = S3Client()
    
    # 为所有文件路径生成预签名URL（有效期24小时）
    if task.video_path and task.video_path.startswith("videos/"):
        try:
            task_dict["video_url"] = s3.get_file_url(task.video_path, expires_seconds=86400)
        except Exception as e:
            print(f"Error generating video URL: {e}")
    if task.audio_path and task.audio_path.startswith("videos/"):
        try:
            task_dict["audio_url"] = s3.get_file_url(task.audio_path, expires_seconds=86400)
        except Exception as e:
            print(f"Error generating audio URL: {e}")
    if task.transcription_path and task.transcription_path.startswith("videos/"):
        try:
            task_dict["transcription_url"] = s3.get_file_url(task.transcription_path, expires_seconds=86400)
        except Exception as e:
            print(f"Error generating transcription URL: {e}")
    if task.summary_path and task.summary_path.startswith("videos/"):
        try:
            task_dict["summary_url"] = s3.get_file_url(task.summary_path, expires_seconds=86400)
        except Exception as e:
            print(f"Error generating summary URL: {e}")


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    """
    获取任务详情
    
    Args:
        task_id: 任务ID
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    
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
    query = db.query(Task)
    
    # 状态筛选
    if status:
        query = query.filter(Task.status == status)
    
    # 排序和分页
    total = query.count()
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
    
    tasks = db.query(Task).filter(Task.status.in_(current_statuses)).order_by(desc(Task.created_at)).all()
    
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
    # 查询已完成或失败的任务作为历史记录
    tasks = db.query(Task).filter(
        Task.status.in_([TaskStatus.COMPLETED.value, TaskStatus.FAILED.value])
    ).order_by(desc(Task.updated_at)).offset(offset).limit(limit).all()
    
    total = db.query(Task).filter(
        Task.status.in_([TaskStatus.COMPLETED.value, TaskStatus.FAILED.value])
    ).count()
    
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
    task = db.query(Task).filter(Task.id == task_id).first()
    
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

