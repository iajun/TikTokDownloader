"""
数据库模型模块
导出所有模型，保持向后兼容
"""
# 导入基础类和枚举
from .base import Base, TaskStatus

# 导入所有模型
from .video import Video
from .task import Task
from .history import HistoryRecord
from .setting import Setting, Prompt
from .ai_method import AIMethod
from .collection import CollectionFolder, CollectionTask
from .video_summary import VideoSummary
from .email_subscription import EmailSubscription

# 导出所有内容，保持向后兼容
__all__ = [
    'Base',
    'TaskStatus',
    'Video',
    'Task',
    'HistoryRecord',
    'Setting',
    'Prompt',
    'AIMethod',
    'CollectionFolder',
    'CollectionTask',
    'VideoSummary',
    'EmailSubscription',
]

