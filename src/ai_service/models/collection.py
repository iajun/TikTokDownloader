"""
收藏夹模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .base import Base


class CollectionFolder(Base):
    """收藏夹文件夹表 - 支持树状结构"""
    __tablename__ = "collection_folders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)  # 文件夹名称
    parent_id = Column(Integer, ForeignKey('collection_folders.id'), nullable=True, index=True)  # 父文件夹ID，支持树状结构
    sort_order = Column(Integer, default=0, index=True)  # 排序顺序
    description = Column(Text)  # 描述
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系：父子关系
    parent = relationship("CollectionFolder", remote_side=[id], backref="children")
    # 关系：收藏的任务
    tasks = relationship("CollectionTask", back_populates="folder", cascade="all, delete-orphan")
    
    def to_dict(self, include_children=False, include_task_count=False):
        """转换为字典
        
        Args:
            include_children: 是否包含子文件夹列表
            include_task_count: 是否包含任务数量
        """
        result = {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "sort_order": self.sort_order,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_children and hasattr(self, 'children'):
            result["children"] = [child.to_dict(include_children=True) for child in sorted(self.children, key=lambda x: x.sort_order)]
        
        if include_task_count:
            result["task_count"] = len(self.tasks)
        
        return result


class CollectionTask(Base):
    """收藏任务关联表"""
    __tablename__ = "collection_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    folder_id = Column(Integer, ForeignKey('collection_folders.id'), nullable=False, index=True)  # 收藏夹ID
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False, index=True)  # 任务ID
    
    # 唯一约束：同一任务不能在同一文件夹中重复收藏
    __table_args__ = (
        UniqueConstraint('folder_id', 'task_id', name='unique_folder_task'),
    )
    
    # 备注
    notes = Column(Text)  # 用户添加的备注
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 关系
    folder = relationship("CollectionFolder", back_populates="tasks")
    task = relationship("Task")
    
    def to_dict(self, include_task=True):
        """转换为字典
        
        Args:
            include_task: 是否包含任务详情
        """
        result = {
            "id": self.id,
            "folder_id": self.folder_id,
            "task_id": self.task_id,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_task and self.task:
            result["task"] = self.task.to_dict(include_video=True)
        
        return result

