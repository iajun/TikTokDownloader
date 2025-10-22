# 架构文档（C4 视角 + 模块设计）

## 1. 背景

系统为抖音/TikTok 数据采集与 AI 处理平台，形态包含 CLI、Web API、前端 Web。本文聚焦 `frontend/` 与 `src/ai_service/` 的系统结构与交互。

## 2. C4：系统上下文（Context）

- 主要用户：内容创作者、分析师、开发者
- 外部系统：
  - Douyin/TikTok 平台（数据源）
  - ASR/LLM 服务（Whisper、DeepSeek 等）
  - 对象存储（MinIO/S3，可选）
- 部署边界：
  - 前端：Vite 本地开发或静态资源部署
  - AI Service：FastAPI（Uvicorn/容器）
  - 依赖：MySQL/MinIO（docker-compose）

## 3. C4：容器（Containers）

- Web 前端（Vue 3 + TS）：
  - 通过 Vite 代理访问后端 `/api/v1/*`
  - 主要页面：任务创建、任务队列、历史列表、详情页
- AI Service（FastAPI）：
  - API 容器：接受请求、落库、返回状态
  - Worker 容器（可与 API 同进程）：后台推进任务状态机
  - 依赖容器：MySQL、MinIO（可选）

## 4. C4：组件（Components）

- API 层（`src/ai_service/api/`）
  - 任务创建/查询/删除、历史查询
  - OpenAPI 文档 `/docs`
- Worker（`src/ai_service/workers/`）
  - 队列轮询、状态推进、重试策略
- 能力服务（`src/ai_service/services/`）
  - `TranscriptionService`：封装 Whisper/ASR
  - `AISummarizer`：封装 DeepSeek/LLM
- 工具（`src/ai_service/utils/`）
  - `VideoProcessor`：下载视频、断点续传、去重
  - `AudioExtractor`：FFmpeg 抽音
  - `S3Client`：MinIO/S3 读写
- 数据访问（`src/ai_service/db/`、`src/ai_service/models/`）
  - `Task`、`TaskStatus`、`Video` 等模型与会话管理

前端组件：
- `src/views/*`：任务列表/详情/历史
- `src/api/*`：HTTP 抽象与类型定义
- `MarkdownRenderer.vue`：富文本/代码片段渲染

## 5. 运行时流程（顺序图文字版）

1) 前端调用 `POST /api/v1/tasks` 创建任务（body: { url })
2) API 创建 `Task`（status=pending），入队
3) Worker 取出任务，按状态机执行：
   - downloading：下载视频 → 写入 `video_path`
   - extracting_audio：FFmpeg → `audio_path`
   - transcribing：ASR → `transcription_path` + 文本缓存
   - summarizing：LLM → `summary_path` + 文本缓存
4) 每步更新 `status`、`progress`、时间戳；失败写入 `error_message`
5) 前端轮询/推送刷新 UI；历史页可检索任务与产物

## 6. 配置与部署

- 开发：
  - 后端：`python start_ai_service.py`
  - 依赖：`docker-compose up -d`（MySQL/MinIO）
  - 前端：`npm run dev`（Vite 代理 `/api` → `localhost:8000`）
- 生产：
  - 反向代理（Nginx/Caddy）统一域名与 TLS
  - 环境变量注入 Cookie、代理、ASR/LLM Key、S3 凭据
  - 可将 Worker 单独进程/副本水平扩展

## 7. 可观测性与日志

- 结构化日志（JSON）含 task_id、status、duration、error
- 关键指标（建议）：
  - 任务时延分布、各阶段耗时
  - 成功/失败率、重试次数
  - 下载带宽与对象存储吞吐

## 8. 质量与测试

- 单元：utils/services 的纯函数与边界条件
- 集成：下载 → 抽音 → 转写 → 总结 的端到端案例
- 契约：前后端对 `TaskStatus` 的类型契约与字段回归

## 9. 扩展点与演进

- 插件化平台适配层（解析/下载）
- 多模型/多提供方策略（ASR/LLM）
- 任务编排（优先级/取消/暂停/配额）
- 结构化抽取/知识库入库（向量/检索）

## 10. 目录索引（关键）

```
frontend/
  src/api/*           # 与 /api/v1 对齐的请求层
  src/views/*         # 任务/历史/详情
  components/MarkdownRenderer.vue

src/ai_service/
  api/                # FastAPI 路由
  workers/            # 后台任务推进
  services/           # ASR/LLM 封装
  utils/              # 下载/抽音/S3
  db/, models/        # ORM 与会话
  __init__.py         # 对外导出（app、服务、模型）
```

