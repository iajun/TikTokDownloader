"""
邮箱订阅模型定义
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from .base import Base


class EmailSubscription(Base):
    """邮箱订阅表 - 存储用户邮箱订阅信息"""
    __tablename__ = "email_subscriptions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(256), nullable=False, unique=True, index=True)  # 邮箱地址，唯一
    is_active = Column(Boolean, default=True, index=True)  # 是否激活
    verified = Column(Boolean, default=False)  # 是否已验证（预留）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "email": self.email,
            "is_active": self.is_active,
            "verified": self.verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

