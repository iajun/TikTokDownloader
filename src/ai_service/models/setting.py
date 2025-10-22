"""
设置和提示词模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from .base import Base


class Setting(Base):
    """项目设置表 - 存储系统配置"""
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), nullable=False, unique=True, index=True)  # 配置键
    value = Column(Text)  # 配置值（JSON格式）
    description = Column(Text)  # 配置描述
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Prompt(Base):
    """提示词表 - 存储多个提示词模板"""
    __tablename__ = "prompts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)  # 提示词名称
    content = Column(Text, nullable=False)  # 提示词内容
    description = Column(Text)  # 描述
    is_default = Column(Integer, default=0)  # 是否为默认提示词（0=否，1=是）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "description": self.description,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

