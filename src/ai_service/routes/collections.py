"""
收藏夹管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import List, Optional

from ..models import CollectionFolder, CollectionTask, Task
from ..db import get_db
from .schemas import (
    CollectionFolderCreateRequest,
    CollectionFolderUpdateRequest,
    AddTasksToCollectionRequest,
    BatchDeleteRequest
)

router = APIRouter()


def _build_collection_tree(folders: List[CollectionFolder], parent_id: Optional[int] = None) -> List[dict]:
    """构建收藏夹树结构"""
    result = []
    children = [f for f in folders if f.parent_id == parent_id]
    for folder in sorted(children, key=lambda x: x.sort_order):
        folder_dict = folder.to_dict(include_children=False, include_task_count=True)
        folder_dict["children"] = _build_collection_tree(folders, folder.id)
        result.append(folder_dict)
    return result


@router.get("/collections/tree")
async def get_collection_tree(db: Session = Depends(get_db)):
    """获取收藏夹树结构"""
    folders = db.query(CollectionFolder).all()
    tree = _build_collection_tree(folders)
    
    return {
        "success": True,
        "data": tree
    }


@router.post("/collections")
async def create_collection_folder(request: CollectionFolderCreateRequest, db: Session = Depends(get_db)):
    """创建收藏夹"""
    try:
        # 如果指定了父文件夹，检查是否存在
        if request.parent_id:
            parent = db.query(CollectionFolder).filter(CollectionFolder.id == request.parent_id).first()
            if not parent:
                raise HTTPException(status_code=404, detail="父文件夹不存在")
        
        # 获取同一父文件夹下的最大排序值
        max_sort = db.query(CollectionFolder).filter(
            CollectionFolder.parent_id == request.parent_id
        ).order_by(CollectionFolder.sort_order.desc()).first()
        
        sort_order = (max_sort.sort_order + 1) if max_sort else 0
        
        folder = CollectionFolder(
            name=request.name,
            parent_id=request.parent_id,
            sort_order=sort_order,
            description=request.description
        )
        
        db.add(folder)
        db.commit()
        db.refresh(folder)
        
        return {
            "success": True,
            "message": "收藏夹创建成功",
            "data": folder.to_dict(include_children=True, include_task_count=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/collections/{folder_id}")
async def update_collection_folder(
    folder_id: int,
    request: CollectionFolderUpdateRequest,
    db: Session = Depends(get_db)
):
    """更新收藏夹（重命名、移动位置等）"""
    try:
        folder = db.query(CollectionFolder).filter(CollectionFolder.id == folder_id).first()
        
        if not folder:
            raise HTTPException(status_code=404, detail="收藏夹不存在")
        
        # 更新名称
        if request.name is not None:
            folder.name = request.name
        
        # 更新描述
        if request.description is not None:
            folder.description = request.description
        
        # 更新父文件夹（移动）
        if request.parent_id is not None:
            # 不能将文件夹移动到自己的子文件夹中
            if request.parent_id == folder_id:
                raise HTTPException(status_code=400, detail="不能将文件夹移动到自身")
            
            # 检查是否会形成循环引用
            if request.parent_id:
                parent = db.query(CollectionFolder).filter(CollectionFolder.id == request.parent_id).first()
                if not parent:
                    raise HTTPException(status_code=404, detail="父文件夹不存在")
                
                # 检查父文件夹是否是当前文件夹的子文件夹
                def is_descendant(parent_id: int, child_id: int) -> bool:
                    if parent_id == child_id:
                        return True
                    children = db.query(CollectionFolder).filter(CollectionFolder.parent_id == parent_id).all()
                    for child in children:
                        if is_descendant(child.id, child_id):
                            return True
                    return False
                
                if is_descendant(folder_id, request.parent_id):
                    raise HTTPException(status_code=400, detail="不能将文件夹移动到其子文件夹中")
            
            folder.parent_id = request.parent_id
        
        # 更新排序
        if request.sort_order is not None:
            folder.sort_order = request.sort_order
        
        folder.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(folder)
        
        return {
            "success": True,
            "message": "收藏夹更新成功",
            "data": folder.to_dict(include_children=True, include_task_count=True)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{folder_id}")
async def delete_collection_folder(folder_id: int, db: Session = Depends(get_db)):
    """删除收藏夹（级联删除子文件夹和任务关联）"""
    try:
        folder = db.query(CollectionFolder).filter(CollectionFolder.id == folder_id).first()
        
        if not folder:
            raise HTTPException(status_code=404, detail="收藏夹不存在")
        
        # 递归删除子文件夹
        def delete_folder_recursive(folder_id: int):
            children = db.query(CollectionFolder).filter(CollectionFolder.parent_id == folder_id).all()
            for child in children:
                delete_folder_recursive(child.id)
            # 删除当前文件夹的任务关联
            db.query(CollectionTask).filter(CollectionTask.folder_id == folder_id).delete()
            # 删除文件夹
            db.query(CollectionFolder).filter(CollectionFolder.id == folder_id).delete()
        
        delete_folder_recursive(folder_id)
        db.commit()
        
        return {
            "success": True,
            "message": "收藏夹删除成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections/{folder_id}/tasks")
async def add_tasks_to_collection(
    folder_id: int,
    request: AddTasksToCollectionRequest,
    db: Session = Depends(get_db)
):
    """添加任务到收藏夹"""
    try:
        folder = db.query(CollectionFolder).filter(CollectionFolder.id == folder_id).first()
        
        if not folder:
            raise HTTPException(status_code=404, detail="收藏夹不存在")
        
        if not request.task_ids:
            raise HTTPException(status_code=400, detail="task_ids不能为空")
        
        added_count = 0
        skipped_count = 0
        
        for task_id in request.task_ids:
            # 检查任务是否存在
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                skipped_count += 1
                continue
            
            # 检查是否已经收藏
            existing = db.query(CollectionTask).filter(
                CollectionTask.folder_id == folder_id,
                CollectionTask.task_id == task_id
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # 添加收藏
            collection_task = CollectionTask(
                folder_id=folder_id,
                task_id=task_id
            )
            db.add(collection_task)
            added_count += 1
        
        db.commit()
        
        return {
            "success": True,
            "message": f"成功添加 {added_count} 个任务，跳过 {skipped_count} 个任务",
            "data": {
                "added_count": added_count,
                "skipped_count": skipped_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{folder_id}/tasks/{task_id}")
async def remove_task_from_collection(folder_id: int, task_id: int, db: Session = Depends(get_db)):
    """从收藏夹移除任务"""
    try:
        collection_task = db.query(CollectionTask).filter(
            CollectionTask.folder_id == folder_id,
            CollectionTask.task_id == task_id
        ).first()
        
        if not collection_task:
            raise HTTPException(status_code=404, detail="任务不在该收藏夹中")
        
        db.delete(collection_task)
        db.commit()
        
        return {
            "success": True,
            "message": "任务已从收藏夹移除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{folder_id}/tasks/batch")
async def batch_remove_tasks_from_collection(
    folder_id: int,
    request: BatchDeleteRequest,
    db: Session = Depends(get_db)
):
    """批量从收藏夹移除任务"""
    try:
        if not request.task_ids:
            raise HTTPException(status_code=400, detail="task_ids不能为空")
        
        deleted_count = db.query(CollectionTask).filter(
            CollectionTask.folder_id == folder_id,
            CollectionTask.task_id.in_(request.task_ids)
        ).delete(synchronize_session=False)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"成功移除 {deleted_count} 个任务",
            "data": {
                "deleted_count": deleted_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{folder_id}/tasks")
async def get_collection_tasks(
    folder_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """获取收藏夹中的任务列表"""
    folder = db.query(CollectionFolder).filter(CollectionFolder.id == folder_id).first()
    
    if not folder:
        raise HTTPException(status_code=404, detail="收藏夹不存在")
    
    query = db.query(CollectionTask).filter(CollectionTask.folder_id == folder_id)
    
    total = query.count()
    collection_tasks = query.order_by(desc(CollectionTask.created_at)).offset(offset).limit(limit).all()
    
    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [ct.to_dict(include_task=True) for ct in collection_tasks]
    }

