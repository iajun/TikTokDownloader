# DouK-Downloader 白皮书（前端 + AI Service）

## 1. 概述

DouK-Downloader 是一个开源的数据采集与内容处理平台，聚焦抖音/Douyin 与 TikTok 生态的多模态数据采集（视频、图集、直播、评论、账号等）与内容增值（语音转写、AI 总结）。项目提供命令行、Web API、Web 前端三种使用形态，支持本地单机与容器化部署，面向个人研究者、内容创作者、数据分析师与自动化开发者。

本白皮书聚焦两大子系统：
- 前端应用（frontend/）：Vite + Vue 3 + TypeScript 的任务编排与结果可视化界面。
- AI Service（src/ai_service/）：基于 FastAPI 的服务化后端，提供任务生命周期管理、下载与处理流水线（下载→抽音→转写→总结）、存储与检索能力。

## 2. 核心价值

- 数据采集一体化：覆盖 Douyin/TikTok 多类型实体，统一抽象与接口。
- 可复用处理流水线：将视频下载、音频抽取、ASR 转写、LLM 总结标准化、可并行。
- 本地私有化：本地落地存储与处理，降低合规与隐私风险。
- 可视化与 API 双轨：既可在前端管理任务，也可通过 HTTP API 集成到任意系统。

## 3. 能力边界与合规

- 仅面向公开数据或授权数据，拒绝绕过付费墙/DRM/账号保护的非法行为。
- 强依赖 Cookie/代理配置的可用性与时效性。
- LLM/ASR 等三方能力受配额/模型选择/网络环境影响。

## 4. 系统目标与指标

- 吞吐：单机并发 5–20 任务（取决于带宽/FFmpeg/ASR/LLM）。
- 时延：短视频（≤2min）端到端处理在 1–5 分钟区间。
- 稳定性：失败可复试，任务状态强一致；下载具备断点续传与完整性校验。
- 易用性：前端 3 步完成处理；API 提供 OpenAPI 文档；一键 docker-compose 启动依赖。

## 5. 总体架构

- 前端（frontend/）：
  - 路由与视图：任务创建、队列、历史详情、Markdown 渲染。
  - 与后端通过 `/api/v1` 进行 REST 通信，Vite 代理转发。
- AI Service（src/ai_service/）：
  - API 层（api/）：任务创建/查询/删除、历史查询。
  - Worker 层（workers/）：后台任务执行，拉取队列并推进状态机。
  - 处理工具（utils/）：`VideoProcessor`、`AudioExtractor`、`S3Client`（MinIO/S3）。
  - 能力服务（services/）：`TranscriptionService`（Whisper/ASR），`AISummarizer`（DeepSeek/LLM）。
  - 数据访问（db/、models/）：任务、视频等表与会话管理。

## 6. 任务流水线（状态机）

pending → downloading → extracting_audio → transcribing → summarizing → completed/failed

- downloading：解析平台与链接，下载最高画质且可用的资源，支持断点续传与去重。
- extracting_audio：调用 FFmpeg 抽取音轨。
- transcribing：调用 ASR（默认 Whisper）生成逐字转写。
- summarizing：调用 LLM（默认 DeepSeek）产出摘要与要点。
- completed/failed：持久化结果/错误，提供前端与 API 查询。

## 7. 数据与存储

- 元数据：任务、状态、进度、时间戳、错误信息、关联文件路径。
- 文件：`downloads/<video_id>/video.mp4|audio.wav|transcription.txt|summary.txt`。
- 对象存储：可选 MinIO/S3，通过 `S3Client` 封装。

## 8. 安全与隐私

- 本地优先存储；对外仅暴露必要 API；必要时通过反向代理加鉴权。
- 建议对机密参数（Cookie、API Key）使用环境变量/密钥管理器。

## 9. 生态与扩展

- 平台扩展：新增解析器/下载器接入即可支持新平台（保持接口一致）。
- 能力扩展：替换 ASR/LLM 实现（如自部署 Whisper/大模型）无需改动上层。
- 输出扩展：支持 CSV/XLSX/SQLite 持久化与导出。

## 10. 路线与愿景

- 强化可观测性（指标、日志、追踪）。
- 引入任务优先级、并发调度与限流。
- 拓展结构化抽取（标题、标签、实体、情感、语言）。



