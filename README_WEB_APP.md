# 抖音视频AI总结Web应用

一个基于FastAPI的Web应用，可以输入抖音链接，自动下载视频、提取音频、转文字并使用AI进行内容总结。

## 功能特性

- 🎬 **视频下载**: 支持抖音和TikTok视频下载
- 🎵 **音频提取**: 自动从视频中提取音频文件
- 📝 **语音转文字**: 使用OpenAI Whisper进行语音识别
- 🤖 **AI总结**: 使用DeepSeek AI进行内容总结
- 💾 **持久化存储**: 所有内容（视频、音频、文字、总结）都会保存到本地
- 📚 **历史记录**: 查看所有已处理的视频记录
- 🌐 **Web界面**: 现代化的响应式Web界面
- 📖 **API文档**: 自动生成的API文档

## 安装依赖

### 1. Python依赖

```bash
pip install fastapi uvicorn jinja2 python-multipart
pip install openai-whisper requests openai
```

### 2. FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
下载FFmpeg并添加到PATH环境变量

## 使用方法

### 1. 启动Web应用

```bash
python start_web_app.py
```

或者指定端口和地址：

```bash
python start_web_app.py --host 0.0.0.0 --port 8080
```

### 2. 访问Web界面

打开浏览器访问：http://127.0.0.1:8000

### 3. 使用步骤

1. **输入视频链接**: 在首页输入抖音视频链接
2. **可选配置API密钥**: 输入DeepSeek API密钥以启用AI总结功能
3. **开始处理**: 点击"开始处理视频"按钮
4. **查看结果**: 等待处理完成后查看结果
5. **查看历史**: 访问历史记录页面查看所有已处理的视频

## API使用

### 处理视频

```bash
curl -X POST "http://127.0.0.1:8000/api/process" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://v.douyin.com/xxxxx",
       "api_key": "your_deepseek_api_key"
     }'
```

### 获取处理状态

```bash
curl "http://127.0.0.1:8000/api/status/{record_id}"
```

### 获取所有记录

```bash
curl "http://127.0.0.1:8000/api/records"
```

## 文件结构

```
TikTokDownloader/
├── web_app.py              # Web应用主文件
├── start_web_app.py        # 启动脚本
├── video_ai_summarizer.py  # 视频AI总结器
├── templates/              # HTML模板
│   ├── index.html         # 首页
│   └── history.html       # 历史记录页
├── static/                # 静态文件
├── data/                  # 数据存储
│   └── video_records.json # 记录数据库
└── downloads/             # 下载文件存储
    ├── video_id/          # 按视频ID分组的文件
    │   ├── video.mp4      # 视频文件
    │   ├── audio.wav      # 音频文件
    │   ├── transcription.txt # 转录文本
    │   └── summary.txt    # AI总结
```

## 配置说明

### DeepSeek API密钥

要使用AI总结功能，需要配置DeepSeek API密钥：

1. 访问 [DeepSeek官网](https://platform.deepseek.com/) 注册账号
2. 获取API密钥
3. 在Web界面输入API密钥，或通过环境变量设置：

```bash
export DEEPSEEK_API_KEY="your_api_key"
```

### 存储路径

- **数据文件**: `data/video_records.json`
- **下载文件**: `downloads/` 目录
- **静态文件**: `static/` 目录

## 技术栈

- **后端**: FastAPI + Uvicorn
- **前端**: HTML + CSS + JavaScript
- **视频处理**: FFmpeg
- **语音识别**: OpenAI Whisper
- **AI总结**: DeepSeek API
- **数据存储**: JSON文件

## 注意事项

1. **网络要求**: 需要稳定的网络连接下载视频
2. **存储空间**: 确保有足够的磁盘空间存储视频和音频文件
3. **API限制**: DeepSeek API有使用限制，请注意配额
4. **版权问题**: 请遵守相关法律法规，仅用于个人学习研究

## 故障排除

### 常见问题

1. **FFmpeg未找到**
   - 确保FFmpeg已正确安装并在PATH中

2. **视频下载失败**
   - 检查网络连接
   - 确认视频链接有效
   - 可能需要配置Cookie或代理

3. **AI总结失败**
   - 检查API密钥是否正确
   - 确认API配额是否充足

4. **端口被占用**
   - 使用 `--port` 参数指定其他端口

### 日志查看

Web应用会在控制台输出详细的处理日志，包括：
- 视频下载进度
- 音频提取状态
- 语音识别结果
- AI总结过程

## 开发说明

### 添加新功能

1. 修改 `web_app.py` 添加新的API端点
2. 更新HTML模板添加新的UI元素
3. 修改 `video_ai_summarizer.py` 添加新的处理逻辑

### 自定义样式

修改 `templates/` 目录下的HTML文件中的CSS样式。

## 许可证

本项目基于原TikTokDownloader项目的许可证。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目！
