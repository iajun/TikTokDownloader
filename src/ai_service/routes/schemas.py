"""
API 请求和响应模型定义
"""
from pydantic import BaseModel
from typing import Optional, List


# 任务相关
class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    url: str


class BatchTaskCreateRequest(BaseModel):
    """批量创建任务请求"""
    url: str
    type: str  # 'mix', 'account', 'video' 或 'auto'
    max_count: Optional[int] = 100  # 最大提取数量，防止无限提取


class ResummarizeRequest(BaseModel):
    """重新生成总结请求"""
    custom_prompt: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    task_ids: List[int]


# 设置相关
class SettingUpdateRequest(BaseModel):
    """更新设置请求"""
    value: Optional[str] = None
    description: Optional[str] = None


# 提示词相关
class PromptCreateRequest(BaseModel):
    """创建提示词请求"""
    name: str
    content: str
    description: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    """更新提示词请求"""
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None


# AI方法相关
class AIMethodCreateRequest(BaseModel):
    """创建AI方法请求"""
    name: str
    display_name: str
    api_key: Optional[str] = None
    cookies: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None


class AIMethodUpdateRequest(BaseModel):
    """更新AI方法请求"""
    display_name: Optional[str] = None
    is_active: Optional[int] = None
    api_key: Optional[str] = None
    cookies: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None


# 收藏夹相关
class CollectionFolderCreateRequest(BaseModel):
    """创建收藏夹请求"""
    name: str
    parent_id: Optional[int] = None
    description: Optional[str] = None


class CollectionFolderUpdateRequest(BaseModel):
    """更新收藏夹请求"""
    name: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    description: Optional[str] = None


class AddTasksToCollectionRequest(BaseModel):
    """添加任务到收藏夹请求"""
    task_ids: List[int]


# 总结相关
class SummaryCreateRequest(BaseModel):
    """创建总结请求"""
    name: Optional[str] = None
    content: str
    custom_prompt: Optional[str] = None


class SummaryUpdateRequest(BaseModel):
    """更新总结请求"""
    name: Optional[str] = None
    content: Optional[str] = None
    sort_order: Optional[int] = None


class SummaryReorderRequest(BaseModel):
    """重新排序总结请求"""
    summary_ids: List[int]


# 邮箱订阅相关
class EmailSubscriptionCreateRequest(BaseModel):
    """创建邮箱订阅请求"""
    email: str
    is_active: Optional[bool] = True


class EmailSubscriptionUpdateRequest(BaseModel):
    """更新邮箱订阅请求"""
    is_active: Optional[bool] = None

