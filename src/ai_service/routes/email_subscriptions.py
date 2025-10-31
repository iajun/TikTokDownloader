"""
邮箱订阅管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from ..models import EmailSubscription
from ..db import get_db
from .schemas import EmailSubscriptionCreateRequest, EmailSubscriptionUpdateRequest

router = APIRouter()


@router.get("/email-subscriptions")
async def list_email_subscriptions(db: Session = Depends(get_db)):
    """获取所有邮箱订阅"""
    subscriptions = db.query(EmailSubscription).order_by(EmailSubscription.created_at.desc()).all()
    
    return {
        "success": True,
        "data": [subscription.to_dict() for subscription in subscriptions]
    }


@router.get("/email-subscriptions/{subscription_id}")
async def get_email_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """获取单个邮箱订阅"""
    subscription = db.query(EmailSubscription).filter(EmailSubscription.id == subscription_id).first()
    
    if not subscription:
        raise HTTPException(status_code=404, detail="Email subscription not found")
    
    return {
        "success": True,
        "data": subscription.to_dict()
    }


@router.post("/email-subscriptions")
async def create_email_subscription(request: EmailSubscriptionCreateRequest, db: Session = Depends(get_db)):
    """创建邮箱订阅"""
    try:
        # 检查邮箱是否已存在
        existing = db.query(EmailSubscription).filter(EmailSubscription.email == request.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="邮箱已存在")
        
        subscription = EmailSubscription(
            email=request.email,
            is_active=request.is_active if request.is_active is not None else True,
            verified=False
        )
        
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        
        return {
            "success": True,
            "message": "邮箱订阅创建成功",
            "data": subscription.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/email-subscriptions/{subscription_id}")
async def update_email_subscription(
    subscription_id: int,
    request: EmailSubscriptionUpdateRequest,
    db: Session = Depends(get_db)
):
    """更新邮箱订阅"""
    try:
        subscription = db.query(EmailSubscription).filter(EmailSubscription.id == subscription_id).first()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Email subscription not found")
        
        # 更新字段
        if request.is_active is not None:
            subscription.is_active = request.is_active
        
        subscription.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(subscription)
        
        return {
            "success": True,
            "message": "邮箱订阅更新成功",
            "data": subscription.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/email-subscriptions/{subscription_id}")
async def delete_email_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """删除邮箱订阅"""
    try:
        subscription = db.query(EmailSubscription).filter(EmailSubscription.id == subscription_id).first()
        
        if not subscription:
            raise HTTPException(status_code=404, detail="Email subscription not found")
        
        db.delete(subscription)
        db.commit()
        
        return {
            "success": True,
            "message": "邮箱订阅删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/email-subscriptions/check/{email}")
async def check_email_subscription(email: str, db: Session = Depends(get_db)):
    """检查邮箱是否已订阅"""
    subscription = db.query(EmailSubscription).filter(EmailSubscription.email == email).first()
    
    return {
        "success": True,
        "data": {
            "exists": subscription is not None,
            "subscription": subscription.to_dict() if subscription else None
        }
    }

