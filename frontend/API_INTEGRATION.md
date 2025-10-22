# 前端与 ai_service 集成说明

## 📡 API 接口映射

前端已更新为调用 `ai_service` 的 API 接口：

### 创建任务
```typescript
POST /api/v1/tasks
Body: { url: string }

Response: {
  success: boolean
  message: string
  data: TaskStatus
}
```

### 获取任务详情
```typescript
GET /api/v1/tasks/{task_id}

Response: {
  success: boolean
  data: TaskStatus
}
```

### 获取所有任务
```typescript
GET /api/v1/tasks

Response: {
  success: boolean
  total: number
  limit: number
  offset: number
  data: TaskStatus[]
}
```

### 获取当前任务
```typescript
GET /api/v1/tasks/current/list

Response: {
  success: boolean
  data: TaskStatus[]
}
```

### 获取历史记录
```typescript
GET /api/v1/history

Response: {
  success: boolean
  total: number
  limit: number
  offset: number
  data: TaskStatus[]
}
```

### 获取历史详情
```typescript
GET /api/v1/history/{task_id}

Response: {
  success: boolean
  data: TaskStatus
}
```

### 删除任务
```typescript
DELETE /api/v1/tasks/{task_id}

Response: {
  success: boolean
  message: string
}
```

## 🔄 数据模型

### TaskStatus 接口
```typescript
interface TaskStatus {
  id: number                          // 任务ID
  url: string                         // 视频URL
  video_id?: string                   // 视频ID
  platform?: string                   // 平台类型 (douyin/tiktok)
  status: string                      // 任务状态
  progress: number                    // 进度百分比 (0-100)
  video_path?: string                 // 视频文件路径
  audio_path?: string                 // 音频文件路径
  transcription_path?: string         // 转录文件路径
  summary_path?: string              // 总结文件路径
  video_folder_path?: string          // 视频文件夹路径
  transcription?: string              // 转录内容
  summary?: string                    // AI总结内容
  error_message?: string              // 错误信息
  created_at: string                  // 创建时间
  updated_at?: string                 // 更新时间
  completed_at?: string               // 完成时间
}
```

## 📊 任务状态

| 状态 | 说明 |
|------|------|
| pending | 等待处理 |
| downloading | 下载中 |
| extracting_audio | 提取音频中 |
| transcribing | 转录中 |
| summarizing | AI总结中 |
| completed | 完成 |
| failed | 失败 |

## 🚀 启动服务

### 1. 启动后端服务

```bash
# 启动 MySQL 和 MinIO
docker-compose up -d

# 启动 ai_service
python start_ai_service.py
```

服务运行在：http://localhost:8000

### 2. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

前端运行在：http://localhost:5173

### 3. 访问应用

- 前端: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 📝 API 调用示例

### 创建任务
```typescript
import { processVideo } from '@/api/task'

const response = await processVideo({
  url: 'https://v.douyin.com/xxxxx'
})

console.log(response.data.id)  // 任务ID
```

### 获取任务状态
```typescript
import { getTaskStatus } from '@/api/task'

const response = await getTaskStatus(taskId)
console.log(response.data.status)  // 任务状态
```

### 获取历史记录
```typescript
import { getAllRecords } from '@/api/task'

const response = await getAllRecords()
console.log(response.data)  // 记录列表
```

## ⚠️ 注意事项

1. **任务ID是数字类型**，不是字符串
2. **响应数据结构**：`{ success, data }` 而不是 `{ success, tasks }`
3. **历史记录**使用 `GET /api/v1/history` 获取已完成的任务
4. **删除任务**只能删除已完成的任务
5. **取消任务**功能暂未实现

## 🔧 配置

### Vite 代理配置

```typescript
// vite.config.ts
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
}
```

前端请求会自动代理到后端服务。

## 📚 更多文档

- [ai_service 文档](../src/ai_service/README.md)
- [后端 API 文档](http://localhost:8000/docs)
- [前端开发指南](./README.md)
