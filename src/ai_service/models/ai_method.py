"""
AI方法配置模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from .base import Base


class AIMethod(Base):
    """AI方法配置表 - 存储不同的AI总结方法配置"""
    __tablename__ = "ai_methods"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)  # 方法名称: deepseek, chatgpt, yuanbao
    display_name = Column(String(128), nullable=False)  # 显示名称
    is_active = Column(Integer, default=1)  # 是否启用（0=否，1=是）
    api_key = Column(Text)  # API密钥（用于token方式）
    cookies = Column(Text)  # Cookies（用于浏览器方式）
    base_url = Column(String(512))  # 基础URL（如果需要）
    description = Column(Text)  # 描述
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "api_key": self.api_key,
            "cookies": self.cookies,
            "base_url": self.base_url,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

