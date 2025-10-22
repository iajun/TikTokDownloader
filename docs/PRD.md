# PRD｜DouK-Downloader（前端 + AI Service）

## 1. 背景与目标

为抖音/Douyin 与 TikTok 生态提供「采集 + 处理 + 可视化」一体化能力：用户提交链接后，系统自动完成下载、音频抽取、语音转写与 AI 总结，并在前端展示进度与结果，同时提供标准化 API 供系统集成。

## 2. 用户画像

- 内容创作者：快速整理素材要点、生成文案提纲。
- 数据分析师/研究者：批量采集与结构化沉淀，后续做分析与标注。
- 自动化开发者：作为流水线能力模块调用（CI/爬虫/中台）。

## 3. 术语与范围

- 任务（Task）：一次完整的端到端处理实例，包含状态、进度、结果。
- 历史（History）：已完成/失败的任务归档，可检索与复用产物。
- 处理流水线：downloading → extracting_audio → transcribing → summarizing。
- 平台范围：Douyin/TikTok 起步，可扩展。

## 4. 功能需求

### 4.1 前端

- 创建任务：输入 URL，提交到 `/api/v1/tasks`。
- 任务列表：分页查看任务（当前与全部），轮询/推送更新进度。
- 任务详情：展示状态机、错误、产物路径与富文本（Markdown）渲染。
- 历史记录：分页检索、详情查看、文件下载/复制路径。
- 删除任务：删除已完成任务（软删/硬删由后端控制）。

### 4.2 后端（AI Service）

- API（REST）：
  - POST `/api/v1/tasks` 创建任务。
  - GET `/api/v1/tasks/{id}` 查询任务详情。
  - GET `/api/v1/tasks` 查询任务列表（分页）。
  - GET `/api/v1/tasks/current/list` 查询当前执行或排队任务。
  - DELETE `/api/v1/tasks/{id}` 删除任务（仅已完成）。
  - GET `/api/v1/history`、GET `/api/v1/history/{id}` 历史列表与详情。
- 任务执行：后台 Worker 拉取并推进状态；失败可重试（幂等下载与处理）。
- 文件管理：下载与处理产物存放于 `downloads/<video_id>/`；可选对接 MinIO/S3。
- 可配置：Cookie、代理、ASR/LLM 模型与鉴权（环境变量/配置文件）。

## 5. 非功能需求

- 可用性：接口具备错误码与可读错误信息；前端对异常有提示。
- 性能：短视频端到端 1–5 分钟；并发任务可配置（默认 5）。
- 可靠性：断点续传、文件完整性校验；状态准确可追踪。
- 安全：接口可置于内网/反代；敏感配置不落盘或加密存储。

## 6. 数据结构（摘要）

TaskStatus：

```
id: number
url: string
video_id?: string
platform?: 'douyin'|'tiktok'
status: 'pending'|'downloading'|'extracting_audio'|'transcribing'|'summarizing'|'completed'|'failed'
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
```

分页响应：

```
{
  success: boolean,
  total: number,
  limit: number,
  offset: number,
  data: TaskStatus[]
}
```

## 7. 交互与流程

1) 用户提交 URL → 创建任务成功 → 返回任务 ID 与初始状态 pending。
2) 前端跳转到任务详情并开始轮询（或通过 SSE/WebSocket 订阅）。
3) 后端按状态机推进，更新 `progress`、`status`、`error_message`。
4) 任务完成后可在历史页检索，查看/下载产物与摘要。

## 8. 验收标准

- 提交有效 URL 时，任务能进入执行队列，进度/状态可见。
- 任务失败时，用户能在前端看到错误原因与建议操作。
- 历史列表可分页、可按时间排序，详情包含转写与摘要。
- API 文档可通过 `/docs` 自动生成并可用。

## 9. 边界与未来工作

- 不保证对所有平台与所有链接样式的长期稳定适配。
- 大模型产出质量受模型能力与提示词影响，需迭代优化。
- 未来引入：任务优先级、取消/暂停、批量导入、Webhook 回调、权限体系。



