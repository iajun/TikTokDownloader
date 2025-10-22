# AI视频总结工具 - 前端

基于 Vue 3 + TypeScript + Ant Design Vue Pro 开发的现代化前端界面。

## 技术栈

- **Vue 3** - 渐进式JavaScript框架
- **TypeScript** - 类型安全的JavaScript
- **Ant Design Vue** - 企业级UI组件库
- **Pinia** - Vue的状态管理库
- **Vite** - 快速的前端构建工具
- **Vue Router** - 官方路由管理器

## 功能特性

### 🎬 视频处理
- 支持输入抖音/TikTok视频链接
- 自动提取链接（支持长链接、短链接及包含链接的文本）
- 可选DeepSeek API密钥配置
- 实时任务状态反馈

### 📋 任务管理
- 查看所有任务列表
- 按状态分类（全部/进行中/已完成/失败）
- 实时进度更新
- 取消进行中的任务
- 自动刷新任务状态

### 📚 历史记录
- 查看所有处理过的视频
- 显示视频链接、创建时间
- 显示总结预览
- 支持查看详情
- 支持重新总结

### 📄 详情页面
- 查看完整视频信息
- 查看语音转录内容
- 查看AI总结内容
- 下载相关文件
- 支持复制文本内容

## 快速开始

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:5173

### 构建生产版本

```bash
npm run build
```

构建产物在 `dist` 目录。

### 预览生产版本

```bash
npm run preview
```

## 项目结构

```
frontend/
├── public/              # 静态资源
├── src/
│   ├── api/            # API接口封装
│   ├── components/     # 组件
│   ├── layouts/        # 布局
│   ├── router/         # 路由配置
│   ├── store/          # 状态管理
│   ├── views/          # 页面视图
│   ├── App.vue         # 根组件
│   ├── main.ts         # 入口文件
│   └── style.css       # 全局样式
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## 主要页面

### 首页 (Home.vue)
- 视频链接输入
- API密钥配置
- 任务提交

### 任务管理 (Tasks.vue)
- 任务列表展示
- 状态筛选
- 进度显示
- 任务操作

### 历史记录 (History.vue)
- 记录列表
- 总结预览
- 详情跳转

### 详情页面 (Detail.vue)
- 视频信息展示
- 转录和总结内容
- 文件下载
- 重新总结

## API接口

### 处理视频
```typescript
POST /api/process
Body: { url: string, api_key?: string }
```

### 获取任务状态
```typescript
GET /api/task/{taskId}
```

### 获取所有任务
```typescript
GET /api/tasks
```

### 取消任务
```typescript
POST /api/task/{taskId}/cancel
```

### 获取所有记录
```typescript
GET /api/records
```

### 获取记录详情
```typescript
GET /api/record/{recordId}
```

### 重新总结
```typescript
POST /api/resummarize/{recordId}
```

## 开发说明

### 添加新页面

1. 在 `src/views/` 创建组件
2. 在 `src/router/index.ts` 添加路由
3. 在导航中添加链接

### 添加新组件

在 `src/components/` 目录创建组件。

### 状态管理

使用 Pinia 进行状态管理，可在 `src/store/` 中创建新的store。

### API调用

所有API调用封装在 `src/api/task.ts` 中，统一使用axios进行HTTP请求。

## 浏览器支持

- Chrome (推荐)
- Firefox
- Safari
- Edge

## 许可证

MIT
