"""
健康检查路由
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/task-processor")
async def task_processor_health():
    """任务处理器健康状态"""
    try:
        from ..workers import get_async_processor
        processor = get_async_processor()
        status = processor.get_status()
        return {
            "status": "ok",
            "processor_status": status
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

