import api from './index'

export interface VideoSummary {
  id: number
  task_id: number
  name: string
  content: string
  custom_prompt?: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface SummaryResponse {
  success: boolean
  data: VideoSummary
}

export interface SummariesResponse {
  success: boolean
  data: VideoSummary[]
}

export interface SummaryCreateRequest {
  name?: string
  content: string
  custom_prompt?: string
}

export interface SummaryUpdateRequest {
  name?: string
  content?: string
  sort_order?: number
}

export interface SummaryReorderRequest {
  summary_ids: number[]
}

/**
 * 获取任务的所有总结
 */
export const getTaskSummaries = (taskId: number) => {
  return api.get<SummariesResponse>(`/v1/tasks/${taskId}/summaries`)
}

/**
 * 创建新的总结
 */
export const createSummary = (taskId: number, data: SummaryCreateRequest) => {
  return api.post<SummaryResponse>(`/v1/tasks/${taskId}/summaries`, data)
}

/**
 * 更新总结（重命名、更新内容等）
 */
export const updateSummary = (summaryId: number, data: SummaryUpdateRequest) => {
  return api.put<SummaryResponse>(`/v1/summaries/${summaryId}`, data)
}

/**
 * 删除总结
 */
export const deleteSummary = (summaryId: number) => {
  return api.delete(`/v1/summaries/${summaryId}`)
}

/**
 * 重新排序总结
 */
export const reorderSummaries = (taskId: number, data: SummaryReorderRequest) => {
  return api.post<SummariesResponse>(`/v1/tasks/${taskId}/summaries/reorder`, data)
}

