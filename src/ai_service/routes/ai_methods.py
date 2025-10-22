"""
AI方法管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..models import AIMethod
from ..db import get_db
from .schemas import AIMethodCreateRequest, AIMethodUpdateRequest

router = APIRouter()


@router.get("/ai-methods")
async def list_ai_methods(db: Session = Depends(get_db)):
    """获取所有AI方法"""
    methods = db.query(AIMethod).order_by(AIMethod.id).all()
    
    return {
        "success": True,
        "data": [method.to_dict() for method in methods]
    }


@router.get("/ai-methods/{method_id}")
async def get_ai_method(method_id: int, db: Session = Depends(get_db)):
    """获取单个AI方法"""
    method = db.query(AIMethod).filter(AIMethod.id == method_id).first()
    
    if not method:
        raise HTTPException(status_code=404, detail="AI method not found")
    
    return {
        "success": True,
        "data": method.to_dict()
    }


@router.post("/ai-methods")
async def create_ai_method(request: AIMethodCreateRequest, db: Session = Depends(get_db)):
    """创建AI方法"""
    try:
        # 检查名称是否已存在
        existing = db.query(AIMethod).filter(AIMethod.name == request.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="AI方法名称已存在")
        
        method = AIMethod(
            name=request.name,
            display_name=request.display_name,
            api_key=request.api_key,
            cookies=request.cookies,
            base_url=request.base_url,
            description=request.description,
            is_active=1
        )
        
        db.add(method)
        db.commit()
        db.refresh(method)
        
        return {
            "success": True,
            "message": "AI方法创建成功",
            "data": method.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/ai-methods/{method_id}")
async def update_ai_method(method_id: int, request: AIMethodUpdateRequest, db: Session = Depends(get_db)):
    """更新AI方法"""
    try:
        method = db.query(AIMethod).filter(AIMethod.id == method_id).first()
        
        if not method:
            raise HTTPException(status_code=404, detail="AI方法未找到")
        
        # 更新字段
        if request.display_name is not None:
            method.display_name = request.display_name
        if request.is_active is not None:
            method.is_active = request.is_active
        if request.api_key is not None:
            method.api_key = request.api_key
        if request.cookies is not None:
            method.cookies = request.cookies
        if request.base_url is not None:
            method.base_url = request.base_url
        if request.description is not None:
            method.description = request.description
        
        method.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(method)
        
        return {
            "success": True,
            "message": "AI方法更新成功",
            "data": method.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/ai-methods/{method_id}")
async def delete_ai_method(method_id: int, db: Session = Depends(get_db)):
    """删除AI方法"""
    try:
        method = db.query(AIMethod).filter(AIMethod.id == method_id).first()
        
        if not method:
            raise HTTPException(status_code=404, detail="AI方法未找到")
        
        db.delete(method)
        db.commit()
        
        return {
            "success": True,
            "message": "AI方法删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-methods/active")
async def get_active_ai_method(db: Session = Depends(get_db)):
    """获取当前活跃的AI方法"""
    method = db.query(AIMethod).filter(AIMethod.is_active == 1).first()
    
    if not method:
        # 返回默认方法
        return {
            "success": True,
            "data": {
                "name": "deepseek",
                "display_name": "DeepSeek API",
                "method_type": "api"
            }
        }
    
    # 根据方法名称判断类型
    method_type = "browser" if method.name in ["chatgpt", "yuanbao"] else "api"
    
    return {
        "success": True,
        "data": {
            "name": method.name,
            "display_name": method.display_name,
            "method_type": method_type,
            "config": method.to_dict()
        }
    }


@router.post("/ai-methods/{method_id}/set-active")
async def set_active_ai_method(method_id: int, db: Session = Depends(get_db)):
    """设置活跃的AI方法"""
    try:
        # 检查方法是否存在
        method = db.query(AIMethod).filter(AIMethod.id == method_id).first()
        if not method:
            raise HTTPException(status_code=404, detail="AI方法未找到")
        
        # 取消所有活跃状态
        all_methods = db.query(AIMethod).all()
        for m in all_methods:
            m.is_active = 0
        
        # 设置新的活跃方法
        method.is_active = 1
        method.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(method)
        
        return {
            "success": True,
            "message": "活跃AI方法设置成功",
            "data": method.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

