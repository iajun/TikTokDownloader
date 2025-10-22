import api from './index'

export interface CollectionFolder {
  id: number
  name: string
  parent_id: number | null
  sort_order: number
  description?: string
  task_count?: number
  children?: CollectionFolder[]
  created_at?: string
  updated_at?: string
}

export interface CollectionTask {
  id: number
  folder_id: number
  task_id: number
  notes?: string
  created_at?: string
  task?: any  // TaskStatus类型
}

export interface CollectionTreeResponse {
  success: boolean
  data: CollectionFolder[]
}

export interface CollectionFolderResponse {
  success: boolean
  message?: string
  data: CollectionFolder
}

export interface CollectionTasksResponse {
  success: boolean
  total: number
  limit: number
  offset: number
  data: CollectionTask[]
}

/**
 * 获取收藏夹树结构
 */
export const getCollectionTree = () => {
  return api.get<CollectionTreeResponse>('/v1/collections/tree')
}

/**
 * 创建收藏夹
 */
export const createCollectionFolder = (data: {
  name: string
  parent_id?: number | null
  description?: string
}) => {
  return api.post<CollectionFolderResponse>('/v1/collections', data)
}

/**
 * 更新收藏夹（重命名、移动等）
 */
export const updateCollectionFolder = (
  folderId: number,
  data: {
    name?: string
    parent_id?: number | null
    sort_order?: number
    description?: string
  }
) => {
  return api.put<CollectionFolderResponse>(`/v1/collections/${folderId}`, data)
}

/**
 * 删除收藏夹
 */
export const deleteCollectionFolder = (folderId: number) => {
  return api.delete(`/v1/collections/${folderId}`)
}

/**
 * 添加任务到收藏夹
 */
export const addTasksToCollection = (folderId: number, taskIds: number[]) => {
  return api.post(`/v1/collections/${folderId}/tasks`, { task_ids: taskIds })
}

/**
 * 从收藏夹移除任务
 */
export const removeTaskFromCollection = (folderId: number, taskId: number) => {
  return api.delete(`/v1/collections/${folderId}/tasks/${taskId}`)
}

/**
 * 批量从收藏夹移除任务
 */
export const batchRemoveTasksFromCollection = (folderId: number, taskIds: number[]) => {
  return api.delete(`/v1/collections/${folderId}/tasks/batch`, {
    data: { task_ids: taskIds }
  })
}

/**
 * 获取收藏夹中的任务列表
 */
export const getCollectionTasks = (folderId: number, limit = 20, offset = 0) => {
  return api.get<CollectionTasksResponse>(`/v1/collections/${folderId}/tasks`, {
    params: { limit, offset }
  })
}

