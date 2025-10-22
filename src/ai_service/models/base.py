"""
数据库模型基类和枚举
"""
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()


class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"        # 等待处理
    DOWNLOADING = "downloading"  # 下载中
    EXTRACTING_AUDIO = "extracting_audio"  # 提取音频中
    TRANSCRIBING = "transcribing"  # 转文字中
    SUMMARIZING = "summarizing"    # AI总结中
    COMPLETED = "completed"        # 完成
    FAILED = "failed"              # 失败

