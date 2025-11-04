import api from './index'

export interface VideoInfo {
  id?: number
  video_id?: string
  platform?: string
  desc?: string
  text_extra?: string
  tag?: string
  nickname?: string
  unique_id?: string
  signature?: string
  static_cover?: string
  dynamic_cover?: string
}

export interface TaskStatus {
  id: number
  url: string
  video_id?: string
  platform?: string
  status: string
  progress: number
  video_path?: string
  audio_path?: string
  transcription_path?: string
  summary_path?: string
  video_folder_path?: string
  transcription?: string
  summary?: string
  error_message?: string
  created_at: string
  updated_at?: string
  completed_at?: string
  video?: VideoInfo
}

export interface ProcessRequest {
  url: string
}

export interface BatchProcessRequest {
  url: string
  type: string  // 'mix', 'account', 'video' 或 'auto'
  max_count?: number  // 最大提取数量
}

export interface ProcessResponse {
  success: boolean
  message: string
  data: TaskStatus
  duplicate?: boolean
}

export interface BatchProcessResponse {
  success: boolean
  message: string
  data: {
    total: number
    created: number
    urls: string[]
    tasks?: TaskStatus[]
  }
}

export interface TasksResponse {
  success: boolean
  total: number
  limit: number
  offset: number
  data: TaskStatus[]
}

export interface TaskResponse {
  success: boolean
  data: TaskStatus
}

export interface Record {
  id: number
  url: string
  video_id?: string
  platform?: string
  status: string
  progress: number
  video_path?: string
  audio_path?: string
  transcription_path?: string
  summary_path?: string
  video_folder_path?: string
  transcription?: string
  summary?: string
  error_message?: string
  created_at: string
  updated_at?: string
  completed_at?: string
  // S3预签名URL
  video_url?: string
  audio_url?: string
  transcription_url?: string
  summary_url?: string
}

export interface RecordsResponse {
  success: boolean
  total: number
  limit: number
  offset: number
  data: Record[]
}

export interface RecordResponse {
  success: boolean
  data: Record
}

/**
 * 分析视频链接 - 识别平台和类型
 */
export interface UrlAnalysis {
  platform: string
  platform_name: string
  type: string
  type_name: string
  is_supported: boolean
  url: string
  video_id?: string
  user_id?: string
}

export interface UrlAnalysisResponse {
  success: boolean
  data: UrlAnalysis
}

export const analyzeUrl = (url: string) => {
  return api.get<UrlAnalysisResponse>('/v1/tasks/analyze', {
    params: { url }
  })
}

/**
 * 处理视频 - 创建任务
 */
export const processVideo = (data: ProcessRequest) => {
  return api.post<ProcessResponse>('/v1/tasks', data)
}

/**
 * 批量处理视频 - 批量创建任务（支持合集、作者等）
 */
export const processBatchVideos = (data: BatchProcessRequest) => {
  return api.post<BatchProcessResponse>('/v1/tasks/batch', data, {
    timeout: 60000,  // 批量处理可能耗时较长
  })
}

/**
 * 获取任务详情
 */
export const getTaskStatus = (taskId: number) => {
  return api.get<TaskResponse>(`/v1/tasks/${taskId}`)
}

/**
 * 获取所有任务
 */
export const getAllTasks = (limit = 20, offset = 0, status?: string) => {
  const params: any = { limit, offset }
  if (status) {
    params.status = status
  }
  return api.get<TasksResponse>('/v1/tasks', { params })
}

/**
 * 获取当前处理中的任务
 */
export const getCurrentTasks = () => {
  return api.get<TasksResponse>('/v1/tasks/current/list')
}

/**
 * 获取历史记录
 */
export const getAllRecords = () => {
  return api.get<RecordsResponse>('/v1/history')
}

/**
 * 获取历史记录详情
 */
export const getHistoryDetail = (taskId: number) => {
  return api.get<RecordResponse>(`/v1/history/${taskId}`)
}

/**
 * 删除任务
 */
export const deleteTask = (taskId: number) => {
  return api.delete(`/v1/tasks/${taskId}`)
}

/**
 * 批量删除任务
 */
export const batchDeleteTasks = (taskIds: number[]) => {
  return api.delete('/v1/tasks/batch', {
    data: { task_ids: taskIds }
  })
}

/**
 * 重新生成总结
 */
export const resummarizeTask = (taskId: number, customPrompt?: string) => {
  const data = customPrompt ? { custom_prompt: customPrompt } : {}
  return api.post<RecordResponse>(`/v1/tasks/${taskId}/resummarize`, data, {
    timeout: 60000,
  })
}

/**
 * 重新转录音频
 */
export const retranscribeTask = (taskId: number, modelName?: string) => {
  const params: any = {}
  if (modelName) {
    params.model_name = modelName
  }
  return api.post<RecordResponse>(`/v1/tasks/${taskId}/retranscribe`, {}, {
    timeout: 60000,
    params,
  })
}

/**
 * 重新执行失败的任务
 */
export const retryTask = (taskId: number) => {
  return api.post<RecordResponse>(`/v1/tasks/${taskId}/retry`)
}

/**
 * 刷新任务的预签名URL
 */
export const refreshUrls = (taskId: number) => {
  return api.get<RecordResponse>(`/v1/tasks/${taskId}/refresh-urls`)
}

export interface SendEmailResponse {
  success: boolean
  message: string
  data: {
    task_id: number
    total_emails: number
    success_count: number
    failed_count: number
    results: { [email: string]: boolean }
  }
}

/**
 * 发送任务邮件到所有激活的订阅邮箱
 */
export const sendTaskEmail = (taskId: number) => {
  return api.post<SendEmailResponse>(`/v1/tasks/${taskId}/send-email`)
}

export interface ObsidianStatusResponse {
  success: boolean
  message?: string
  data: {
    is_configured: boolean
    vault_path?: string | null
    summaries_folder?: string
  }
}

/**
 * 检查 Obsidian 服务是否已配置
 */
export const getObsidianStatus = () => {
  return api.get<ObsidianStatusResponse>('/v1/obsidian/status')
}

export interface SendToObsidianResponse {
  success: boolean
  message: string
  data: {
    task_id: number
    file_path: string
  }
}

/**
 * 发送任务总结到 Obsidian
 */
export const sendTaskToObsidian = (taskId: number) => {
  return api.post<SendToObsidianResponse>(`/v1/tasks/${taskId}/send-to-obsidian`)
}
