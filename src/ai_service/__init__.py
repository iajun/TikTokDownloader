"""
AI Service Module - FastAPI服务化
提供视频AI总结的HTTP API接口
"""

from .utils import VideoProcessor, AudioExtractor, S3Client
from .services import TranscriptionService, AISummarizer
from .api import app
from .workers import TaskWorker, get_worker, background_task_processor
from .models import Task, TaskStatus, Video
from .db import get_db, get_db_session, init_db

__all__ = [
    'VideoProcessor',
    'AudioExtractor',
    'TranscriptionService',
    'AISummarizer',
    'app',
    'TaskWorker',
    'get_worker',
    'background_task_processor',
    'Task',
    'TaskStatus',
    'Video',
    'S3Client',
    'get_db',
    'get_db_session',
    'init_db',
]
