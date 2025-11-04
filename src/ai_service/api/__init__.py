"""
FastAPI API模块
提供模块化的路由结构
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from ..db import init_db, get_db_session
from ..workers import background_task_processor, get_async_processor
from ..utils.task_queue import submit_io_nonblocking
from ..models import Setting, Prompt, AIMethod
import asyncio

# 创建 FastAPI 应用
app = FastAPI(
    title="AI Video Summarizer API",
    description="TikTok/Douyin Video AI Summarizer Service",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 启动时初始化数据库
@app.on_event("startup")
async def startup_event():
    """启动时执行的操作"""
    try:
        init_db()
        print("Database initialized")
        
        # 创建默认配置（如果不存在）
        with get_db_session() as db:
            # 迁移旧的 ai_prompt_template 设置到新的 prompts 表
            existing_prompt_setting = db.query(Setting).filter(Setting.key == "ai_prompt_template").first()
            existing_default_prompt = db.query(Prompt).filter(Prompt.is_default == 1).first()
            
            if existing_prompt_setting and not existing_default_prompt:
                # 如果存在旧的提示词配置且没有默认提示词，迁移到 prompts 表
                default_prompt = Prompt(
                    name="默认提示词",
                    content=existing_prompt_setting.value,
                    description="从旧系统迁移的默认提示词",
                    is_default=1
                )
                db.add(default_prompt)
                db.commit()
                print("Migrated old prompt template to prompts table")
            
            # 创建默认 AI 参数配置
            default_ai_settings = [
                ("ai_max_tokens", "2000", "AI 生成文本的最大 token 数"),
                ("ai_temperature", "0.7", "AI 生成的随机性（0-2），值越高越随机"),
                ("ai_model", "deepseek-chat", "使用的 AI 模型"),
                ("ai_system_prompt", "", "AI 系统提示词"),
                ("bilibili_cookies", "", "Bilibili Cookie 文件路径或内容（用于下载高质量视频，720p及以上需要登录）"),
            ]
            
            for key, value, description in default_ai_settings:
                existing = db.query(Setting).filter(Setting.key == key).first()
                if not existing:
                    setting = Setting(
                        key=key,
                        value=value,
                        description=description
                    )
                    db.add(setting)
                    db.commit()
                    print(f"Created default setting: {key}")
            
            # 创建默认 AI 方法配置
            default_ai_methods = [
                {
                    "name": "deepseek",
                    "display_name": "DeepSeek API",
                    "is_active": 1,
                    "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
                    "description": "DeepSeek API方式，使用Token进行总结"
                },
                {
                    "name": "chatgpt",
                    "display_name": "ChatGPT",
                    "is_active": 0,
                    "description": "ChatGPT浏览器方式，需要配置Cookies"
                },
                {
                    "name": "yuanbao",
                    "display_name": "腾讯元宝",
                    "is_active": 0,
                    "description": "腾讯元宝浏览器方式，需要配置Cookies"
                }
            ]
            
            for method_data in default_ai_methods:
                existing = db.query(AIMethod).filter(AIMethod.name == method_data["name"]).first()
                if not existing:
                    method = AIMethod(**method_data)
                    db.add(method)
                    db.commit()
                    print(f"Created default AI method: {method_data['name']}")
    except Exception as e:
        print(f"Failed to initialize database: {e}")
    
    # 启动异步任务处理器（推荐使用）
    # 也可以选择使用同步的 background_task_processor
    use_async_processor = os.getenv("USE_ASYNC_PROCESSOR", "true").lower() == "true"
    
    if use_async_processor:
        # 启动异步任务处理器（在后台运行）
        processor = get_async_processor(max_concurrent_tasks=int(
            os.getenv("MAX_CONCURRENT_TASKS", "5")
        ))
        # 使用 asyncio.create_task 在后台启动
        asyncio.create_task(processor.start())
        print("Async task processor started")
    else:
        # 启动同步后台任务处理器（在线程池中）
        submit_io_nonblocking(background_task_processor)
        print("Background task processor started (sync mode)")


# 根路径
@app.get("/")
def root():
    """根路径"""
    return {
        "service": "AI Video Summarizer API",
        "version": "1.0.0",
        "status": "running"
    }


# 导入并注册路由
from ..routes import tasks, settings, prompts, ai_methods, collections, files, health, summaries, email_subscriptions

app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(settings.router, prefix="/api/v1", tags=["settings"])
app.include_router(prompts.router, prefix="/api/v1", tags=["prompts"])
app.include_router(ai_methods.router, prefix="/api/v1", tags=["ai-methods"])
app.include_router(collections.router, prefix="/api/v1", tags=["collections"])
app.include_router(files.router, prefix="/api/v1", tags=["files"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(summaries.router, prefix="/api/v1", tags=["summaries"])
app.include_router(email_subscriptions.router, prefix="/api/v1", tags=["email-subscriptions"])

