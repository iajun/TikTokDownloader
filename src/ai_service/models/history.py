"""
历史记录模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from .base import Base


class HistoryRecord(Base):
    """历史记录表（与tasks表合并或独立）"""
    __tablename__ = "history_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, nullable=False, index=True)  # 关联的task ID
    url = Column(String(512), nullable=False, index=True)
    video_id = Column(String(128), index=True)
    platform = Column(String(32))
    
    # 存储路径
    video_path = Column(String(512))
    audio_path = Column(String(512))
    transcription_path = Column(String(512))
    summary_path = Column(String(512))
    
    # 内容预览（截取前500字符）
    transcription_preview = Column(Text)
    summary_preview = Column(Text)
    
    # 视频信息
    video_title = Column(String(512))
    video_description = Column(Text)
    
    # 时间戳
    processed_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "url": self.url,
            "video_id": self.video_id,
            "platform": self.platform,
            "video_path": self.video_path,
            "audio_path": self.audio_path,
            "transcription_path": self.transcription_path,
            "summary_path": self.summary_path,
            "transcription_preview": self.transcription_preview,
            "summary_preview": self.summary_preview,
            "video_title": self.video_title,
            "video_description": self.video_description,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }

