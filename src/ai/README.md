# AI模块使用说明

## 模块结构

AI模块已经重构为以下结构，实现了低内聚高耦合的设计：

```
src/ai/
├── __init__.py              # 模块入口，导出所有公共接口
├── video_processor.py       # 视频处理模块
├── audio_extractor.py       # 音频提取模块
├── transcription_service.py # 语音转文字服务模块
├── ai_summarizer.py        # AI总结服务模块
├── file_manager.py         # 文件管理模块
└── main_cli.py            # 主CLI入口模块
```

## 模块职责

### 1. VideoProcessor (视频处理模块)
- 负责视频下载
- 平台检测（抖音/TikTok）
- 视频文件查找和管理
- 与TikTokDownloader的集成

### 2. AudioExtractor (音频提取模块)
- 从视频中提取音频
- 使用ffmpeg进行音频转换
- 音频文件格式处理

### 3. TranscriptionService (语音转文字服务模块)
- Whisper模型管理
- 音频转文字功能
- 转录文件缓存

### 4. AISummarizer (AI总结服务模块)
- DeepSeek API集成
- AI内容总结
- 提示词管理

### 5. FileManager (文件管理模块)
- 文件保存和读取
- 临时文件清理
- 结果文件管理

### 6. MainCLI (主CLI入口模块)
- 命令行参数解析
- 主流程控制
- 各模块协调

## 使用方式

### 1. 命令行使用（推荐）
```bash
# 使用重构后的入口文件
python video_ai_summarizer.py https://v.douyin.com/xxxxx

# 或者直接使用模块
python -m src.ai.main_cli https://v.douyin.com/xxxxx --api-key your_key
```

### 2. 编程方式使用
```python
from src.ai import VideoAISummarizer

async def process_video():
    async with VideoAISummarizer(api_key="your_key") as summarizer:
        result = await summarizer.process_video("https://v.douyin.com/xxxxx")
        print(result)

# 运行
import asyncio
asyncio.run(process_video())
```

### 3. 单独使用某个模块
```python
from src.ai import AudioExtractor, TranscriptionService, AISummarizer

# 只使用音频提取
extractor = AudioExtractor()
audio_path = extractor.extract_audio("video.mp4", output_folder, "video_name")

# 只使用语音转文字
transcriber = TranscriptionService()
text = transcriber.transcribe_audio(audio_path)

# 只使用AI总结
summarizer = AISummarizer("your_api_key")
summary = summarizer.summarize_with_ai(text)
```

## 设计优势

1. **低内聚高耦合**：每个模块职责单一，模块间通过明确的接口交互
2. **可扩展性**：可以轻松添加新的AI服务或音频处理方式
3. **可测试性**：每个模块可以独立测试
4. **可维护性**：代码结构清晰，易于维护和修改
5. **可复用性**：各模块可以独立使用，满足不同场景需求

## 配置说明

API密钥配置优先级：
1. 命令行参数 `--api-key`
2. `Volume/settings.json` 中的 `deepseek_api_key` 字段
3. 环境变量 `DEEPSEEK_API_KEY`

推荐在 `Volume/settings.json` 中配置：
```json
{
  "deepseek_api_key": "your_deepseek_api_key_here"
}
```
