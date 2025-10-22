"""
视频总结模型定义 - 支持保存多个总结记录
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base


class VideoSummary(Base):
    """视频总结表 - 支持每个任务保存多个总结记录"""
    __tablename__ = "video_summaries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)  # 关联到tasks表
    name = Column(String(256), nullable=False, default="总结")  # 总结名称，用户可以自定义
    content = Column(Text, nullable=False)  # 总结内容
    custom_prompt = Column(Text, nullable=True)  # 使用的自定义提示词（如果有）
    sort_order = Column(Integer, default=0, index=True)  # 排序顺序
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系：总结属于一个任务
    task = relationship("Task", back_populates="summaries")
    
    def to_dict(self, include_task=False):
        """转换为字典
        
        Args:
            include_task: 是否包含任务详情信息
        """
        result = {
            "id": self.id,
            "task_id": self.task_id,
            "name": self.name,
            "content": self.content,
            "custom_prompt": self.custom_prompt,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        # 如果需要，包含任务详情信息
        if include_task and self.task:
            result["task"] = self.task.to_dict(include_video=True)
        
        return result

