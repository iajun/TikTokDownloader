import api from './index'

export interface Setting {
  id: number
  key: string
  value: string
  description?: string
  created_at?: string
  updated_at?: string
}

export interface SettingResponse {
  success: boolean
  data: Setting
}

export interface SettingsResponse {
  success: boolean
  data: Setting[]
}

export interface UpdateSettingRequest {
  value?: string
  description?: string
}

export interface Prompt {
  id: number
  name: string
  content: string
  description?: string
  is_default: number
  created_at?: string
  updated_at?: string
}

export interface PromptResponse {
  success: boolean
  data: Prompt
}

export interface PromptsResponse {
  success: boolean
  data: Prompt[]
}

export interface CreatePromptRequest {
  name: string
  content: string
  description?: string
}

export interface UpdatePromptRequest {
  name?: string
  content?: string
  description?: string
}

/**
 * 获取所有设置
 */
export const listSettings = () => {
  return api.get<SettingsResponse>('/v1/settings')
}

/**
 * 获取单个设置
 */
export const getSetting = (key: string) => {
  return api.get<SettingResponse>(`/v1/settings/${key}`)
}

/**
 * 获取AI提示词模板
 */
export const getPromptTemplate = () => {
  return api.get<SettingResponse>('/v1/settings/prompt/template')
}

/**
 * 更新设置
 */
export const updateSetting = (key: string, data: UpdateSettingRequest) => {
  return api.put<SettingResponse>(`/v1/settings/${key}`, data)
}

// ========== 提示词管理 API ==========

/**
 * 获取所有提示词
 */
export const listPrompts = () => {
  return api.get<PromptsResponse>('/v1/prompts')
}

/**
 * 获取单个提示词
 */
export const getPrompt = (promptId: number) => {
  return api.get<PromptResponse>(`/v1/prompts/${promptId}`)
}

/**
 * 获取默认提示词
 */
export const getDefaultPrompt = () => {
  return api.get<PromptResponse>('/v1/prompts/default')
}

/**
 * 创建提示词
 */
export const createPrompt = (data: CreatePromptRequest) => {
  return api.post<PromptResponse>('/v1/prompts', data)
}

/**
 * 更新提示词
 */
export const updatePrompt = (promptId: number, data: UpdatePromptRequest) => {
  return api.put<PromptResponse>(`/v1/prompts/${promptId}`, data)
}

/**
 * 删除提示词
 */
export const deletePrompt = (promptId: number) => {
  return api.delete<{ success: boolean; message: string }>(`/v1/prompts/${promptId}`)
}

/**
 * 设置默认提示词
 */
export const setDefaultPrompt = (promptId: number) => {
  return api.post<PromptResponse>(`/v1/prompts/${promptId}/set-default`)
}

