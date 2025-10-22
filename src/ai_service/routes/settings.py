"""
设置管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..models import Setting
from ..db import get_db
from .schemas import SettingUpdateRequest

router = APIRouter()


@router.get("/settings")
async def list_settings(db: Session = Depends(get_db)):
    """获取所有设置"""
    settings = db.query(Setting).order_by(Setting.key).all()
    
    return {
        "success": True,
        "data": [setting.to_dict() for setting in settings]
    }


@router.get("/settings/{key}")
async def get_setting(key: str, db: Session = Depends(get_db)):
    """获取单个设置"""
    setting = db.query(Setting).filter(Setting.key == key).first()
    
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    
    return {
        "success": True,
        "data": setting.to_dict()
    }


@router.get("/settings/prompt/template")
async def get_prompt_template(db: Session = Depends(get_db)):
    """获取AI提示词模板"""
    setting = db.query(Setting).filter(Setting.key == "ai_prompt_template").first()
    
    if not setting:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    
    return {
        "success": True,
        "data": setting.to_dict()
    }


@router.put("/settings/{key}")
async def update_setting(key: str, request: SettingUpdateRequest, db: Session = Depends(get_db)):
    """更新设置"""
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        
        if not setting:
            raise HTTPException(status_code=404, detail="Setting not found")
        
        # 更新字段
        if request.value is not None:
            setting.value = request.value
        if request.description is not None:
            setting.description = request.description
        
        setting.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(setting)
        
        return {
            "success": True,
            "message": "Setting updated successfully",
            "data": setting.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

