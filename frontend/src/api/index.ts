import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
}) as Omit<AxiosInstance, 'get' | 'post' | 'put' | 'delete' | 'patch'> & {
  get<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  post<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  put<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
  delete<T = any, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<T>
  patch<T = any, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<T>
}

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export default api
