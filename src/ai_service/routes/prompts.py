"""
提示词管理路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..models import Prompt
from ..db import get_db
from .schemas import PromptCreateRequest, PromptUpdateRequest

router = APIRouter()


@router.get("/prompts")
async def list_prompts(db: Session = Depends(get_db)):
    """获取所有提示词"""
    prompts = db.query(Prompt).order_by(Prompt.is_default.desc(), Prompt.created_at.desc()).all()
    
    return {
        "success": True,
        "data": [prompt.to_dict() for prompt in prompts]
    }


@router.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """获取单个提示词"""
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    return {
        "success": True,
        "data": prompt.to_dict()
    }


@router.post("/prompts")
async def create_prompt(request: PromptCreateRequest, db: Session = Depends(get_db)):
    """创建新提示词"""
    try:
        # 检查名称是否已存在
        existing = db.query(Prompt).filter(Prompt.name == request.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="提示词名称已存在")
        
        prompt = Prompt(
            name=request.name,
            content=request.content,
            description=request.description,
            is_default=0
        )
        
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        
        return {
            "success": True,
            "message": "Prompt created successfully",
            "data": prompt.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/prompts/{prompt_id}")
async def update_prompt(prompt_id: int, request: PromptUpdateRequest, db: Session = Depends(get_db)):
    """更新提示词"""
    try:
        prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
        
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # 更新字段
        if request.name is not None:
            # 检查名称是否被其他提示词使用
            existing = db.query(Prompt).filter(Prompt.name == request.name, Prompt.id != prompt_id).first()
            if existing:
                raise HTTPException(status_code=400, detail="提示词名称已被使用")
            prompt.name = request.name
        
        if request.content is not None:
            prompt.content = request.content
        
        if request.description is not None:
            prompt.description = request.description
        
        prompt.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(prompt)
        
        return {
            "success": True,
            "message": "Prompt updated successfully",
            "data": prompt.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """删除提示词"""
    try:
        prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
        
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # 如果删除的是默认提示词，不允许删除
        if prompt.is_default == 1:
            raise HTTPException(status_code=400, detail="不能删除默认提示词，请先设置其他提示词为默认")
        
        db.delete(prompt)
        db.commit()
        
        return {
            "success": True,
            "message": "Prompt deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompts/{prompt_id}/set-default")
async def set_default_prompt(prompt_id: int, db: Session = Depends(get_db)):
    """设置默认提示词"""
    try:
        # 检查提示词是否存在
        prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first()
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        
        # 先取消所有默认状态
        all_prompts = db.query(Prompt).all()
        for p in all_prompts:
            p.is_default = 0
        
        # 设置新的默认提示词
        prompt.is_default = 1
        prompt.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(prompt)
        
        return {
            "success": True,
            "message": "Default prompt set successfully",
            "data": prompt.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompts/default")
async def get_default_prompt(db: Session = Depends(get_db)):
    """获取默认提示词"""
    prompt = db.query(Prompt).filter(Prompt.is_default == 1).first()
    
    if not prompt:
        raise HTTPException(status_code=404, detail="Default prompt not found")
    
    return {
        "success": True,
        "data": prompt.to_dict()
    }

