"""
任务模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, TaskStatus


class Task(Base):
    """任务表 - 存储任务处理信息"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(512), nullable=False, index=True)  # 创建任务时的URL
    video_id = Column(String(128), index=True)  # 视频ID（冗余字段，方便查询）
    video_db_id = Column(Integer, ForeignKey('videos.id'), nullable=True, index=True)  # 关联到videos表
    platform = Column(String(32))  # 平台类型 (douyin/tiktok)
    
    status = Column(String(32), default=TaskStatus.PENDING.value, index=True)
    progress = Column(Integer, default=0)  # 进度百分比 (0-100)
    
    # 存储路径（S3路径，使用video_id作为文件名）
    video_path = Column(String(512))  # S3路径，格式: videos/{video_id}.mp4
    audio_path = Column(String(512))  # S3路径，格式: videos/{video_id}_audio.wav
    transcription_path = Column(String(512))  # S3路径，格式: videos/{video_id}_transcription.txt
    summary_path = Column(String(512))  # S3路径，格式: videos/{video_id}_summary.txt
    
    # 处理结果
    transcription = Column(Text)
    summary = Column(Text)
    
    # 错误信息
    error_message = Column(Text)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # 关系：任务属于一个视频
    video = relationship("Video", back_populates="tasks")
    # 关系：任务有多个总结记录
    summaries = relationship("VideoSummary", back_populates="task", cascade="all, delete-orphan", order_by="VideoSummary.sort_order")
    
    def to_dict(self, include_video=True):
        """转换为字典
        
        Args:
            include_video: 是否包含视频详情信息
        """
        result = {
            "id": self.id,
            "url": self.url,
            "video_id": self.video_id,
            "video_db_id": self.video_db_id,
            "platform": self.platform,
            "status": self.status,
            "progress": self.progress,
            "video_path": self.video_path,
            "audio_path": self.audio_path,
            "transcription_path": self.transcription_path,
            "summary_path": self.summary_path,
            "transcription": self.transcription,
            "summary": self.summary,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        
        # 如果需要，包含视频详情信息
        if include_video and self.video:
            result["video"] = self.video.to_dict()
        
        return result

