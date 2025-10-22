"""
视频总结相关路由
提供总结的增删改查、排序等功能
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..models import VideoSummary, Task
from ..db import get_db
from .schemas import SummaryCreateRequest, SummaryUpdateRequest, SummaryReorderRequest

router = APIRouter()


@router.get("/tasks/{task_id}/summaries")
async def get_task_summaries(task_id: int, db: Session = Depends(get_db)):
    """
    获取指定任务的所有总结列表
    
    Args:
        task_id: 任务ID
    """
    try:
        # 验证任务是否存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 获取所有总结，按 sort_order 排序
        summaries = db.query(VideoSummary).filter(
            VideoSummary.task_id == task_id
        ).order_by(VideoSummary.sort_order, VideoSummary.created_at).all()
        
        return {
            "success": True,
            "data": [summary.to_dict() for summary in summaries]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/summaries")
async def create_summary(task_id: int, request: SummaryCreateRequest, db: Session = Depends(get_db)):
    """
    创建新的总结记录
    
    Args:
        task_id: 任务ID
        request: 包含总结名称和内容的请求体
    """
    try:
        # 验证任务是否存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 获取当前总结数量，用于排序
        summary_count = db.query(VideoSummary).filter(VideoSummary.task_id == task_id).count()
        
        # 创建新的总结记录
        video_summary = VideoSummary(
            task_id=task_id,
            name=request.name or "新总结",
            content=request.content,
            custom_prompt=request.custom_prompt,
            sort_order=summary_count
        )
        
        db.add(video_summary)
        db.commit()
        db.refresh(video_summary)
        
        return {
            "success": True,
            "message": "Summary created successfully",
            "data": video_summary.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/summaries/{summary_id}")
async def update_summary(summary_id: int, request: SummaryUpdateRequest, db: Session = Depends(get_db)):
    """
    更新总结（重命名、更新内容等）
    
    Args:
        summary_id: 总结ID
        request: 更新请求体
    """
    try:
        video_summary = db.query(VideoSummary).filter(VideoSummary.id == summary_id).first()
        
        if not video_summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        
        # 更新字段
        if request.name is not None:
            video_summary.name = request.name
        if request.content is not None:
            video_summary.content = request.content
        if request.sort_order is not None:
            video_summary.sort_order = request.sort_order
        
        video_summary.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(video_summary)
        
        return {
            "success": True,
            "message": "Summary updated successfully",
            "data": video_summary.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/summaries/{summary_id}")
async def delete_summary(summary_id: int, db: Session = Depends(get_db)):
    """
    删除总结
    
    Args:
        summary_id: 总结ID
    """
    try:
        video_summary = db.query(VideoSummary).filter(VideoSummary.id == summary_id).first()
        
        if not video_summary:
            raise HTTPException(status_code=404, detail="Summary not found")
        
        task_id = video_summary.task_id
        db.delete(video_summary)
        db.commit()
        
        # 重新排序剩余的总结
        remaining_summaries = db.query(VideoSummary).filter(
            VideoSummary.task_id == task_id
        ).order_by(VideoSummary.sort_order, VideoSummary.created_at).all()
        
        for index, summary in enumerate(remaining_summaries):
            summary.sort_order = index
        
        db.commit()
        
        return {
            "success": True,
            "message": "Summary deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/summaries/reorder")
async def reorder_summaries(task_id: int, request: SummaryReorderRequest, db: Session = Depends(get_db)):
    """
    重新排序总结
    
    Args:
        task_id: 任务ID
        request: 包含总结ID列表的请求体，按顺序排列
    """
    try:
        # 验证任务是否存在
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 验证所有总结都属于该任务
        summaries = db.query(VideoSummary).filter(
            VideoSummary.id.in_(request.summary_ids),
            VideoSummary.task_id == task_id
        ).all()
        
        if len(summaries) != len(request.summary_ids):
            raise HTTPException(status_code=400, detail="Some summaries not found or don't belong to this task")
        
        # 更新排序
        for index, summary_id in enumerate(request.summary_ids):
            summary = next((s for s in summaries if s.id == summary_id), None)
            if summary:
                summary.sort_order = index
        
        db.commit()
        
        # 返回更新后的总结列表
        updated_summaries = db.query(VideoSummary).filter(
            VideoSummary.task_id == task_id
        ).order_by(VideoSummary.sort_order, VideoSummary.created_at).all()
        
        return {
            "success": True,
            "message": "Summaries reordered successfully",
            "data": [summary.to_dict() for summary in updated_summaries]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

