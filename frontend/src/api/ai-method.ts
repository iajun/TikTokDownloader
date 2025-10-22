import api from './index'

export interface AIMethod {
  id: number
  name: string
  display_name: string
  is_active: number
  api_key?: string
  cookies?: string
  base_url?: string
  description?: string
  created_at: string
  updated_at: string
}

export interface AIMethodResponse {
  success: boolean
  data: AIMethod
}

export interface AIMethodsResponse {
  success: boolean
  data: AIMethod[]
}

export interface CreateAIMethodRequest {
  name: string
  display_name: string
  api_key?: string
  cookies?: string
  base_url?: string
  description?: string
}

export interface UpdateAIMethodRequest {
  display_name?: string
  is_active?: number
  api_key?: string
  cookies?: string
  base_url?: string
  description?: string
}

/**
 * 获取所有AI方法
 */
export const listAIMethods = () => {
  return api.get<AIMethodsResponse>('/v1/ai-methods')
}

/**
 * 获取单个AI方法
 */
export const getAIMethod = (methodId: number) => {
  return api.get<AIMethodResponse>(`/v1/ai-methods/${methodId}`)
}

/**
 * 创建AI方法
 */
export const createAIMethod = (data: CreateAIMethodRequest) => {
  return api.post<AIMethodResponse>('/v1/ai-methods', data)
}

/**
 * 更新AI方法
 */
export const updateAIMethod = (methodId: number, data: UpdateAIMethodRequest) => {
  return api.put<AIMethodResponse>(`/v1/ai-methods/${methodId}`, data)
}

/**
 * 删除AI方法
 */
export const deleteAIMethod = (methodId: number) => {
  return api.delete(`/v1/ai-methods/${methodId}`)
}

/**
 * 获取当前活跃的AI方法
 */
export const getActiveAIMethod = () => {
  return api.get<{ success: boolean; data: { name: string; display_name: string; method_type: string; config?: AIMethod } }>('/v1/ai-methods/active')
}

/**
 * 设置活跃的AI方法
 */
export const setActiveAIMethod = (methodId: number) => {
  return api.post<AIMethodResponse>(`/v1/ai-methods/${methodId}/set-active`)
}

