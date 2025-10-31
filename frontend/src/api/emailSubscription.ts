import api from './index'

export interface EmailSubscription {
  id: number
  email: string
  is_active: boolean
  verified: boolean
  created_at: string
  updated_at?: string
}

export interface EmailSubscriptionsResponse {
  success: boolean
  data: EmailSubscription[]
}

export interface EmailSubscriptionResponse {
  success: boolean
  message?: string
  data: EmailSubscription
}

export interface EmailSubscriptionCreateRequest {
  email: string
  is_active?: boolean
}

export interface EmailSubscriptionUpdateRequest {
  is_active?: boolean
}

export interface CheckEmailResponse {
  success: boolean
  data: {
    exists: boolean
    subscription: EmailSubscription | null
  }
}

/**
 * 获取所有邮箱订阅
 */
export const getAllEmailSubscriptions = () => {
  return api.get<EmailSubscriptionsResponse>('/v1/email-subscriptions')
}

/**
 * 获取单个邮箱订阅
 */
export const getEmailSubscription = (subscriptionId: number) => {
  return api.get<EmailSubscriptionResponse>(`/v1/email-subscriptions/${subscriptionId}`)
}

/**
 * 创建邮箱订阅
 */
export const createEmailSubscription = (data: EmailSubscriptionCreateRequest) => {
  return api.post<EmailSubscriptionResponse>('/v1/email-subscriptions', data)
}

/**
 * 更新邮箱订阅
 */
export const updateEmailSubscription = (subscriptionId: number, data: EmailSubscriptionUpdateRequest) => {
  return api.put<EmailSubscriptionResponse>(`/v1/email-subscriptions/${subscriptionId}`, data)
}

/**
 * 删除邮箱订阅
 */
export const deleteEmailSubscription = (subscriptionId: number) => {
  return api.delete<{ success: boolean; message: string }>(`/v1/email-subscriptions/${subscriptionId}`)
}

/**
 * 检查邮箱是否已订阅
 */
export const checkEmailSubscription = (email: string) => {
  return api.get<CheckEmailResponse>(`/v1/email-subscriptions/check/${email}`)
}

