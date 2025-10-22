"""
启动AI服务
运行FastAPI服务
"""

import uvicorn
import os
from pathlib import Path
from dotenv import load_dotenv

# 设置工作目录
BASE_DIR = Path(__file__).parent
os.chdir(BASE_DIR)

# 加载 .env 文件
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

# 从环境变量读取配置，如果不存在则使用默认值
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


def main():
    """主函数"""
    # 导入app
    from src.ai_service.api import app
    from src.ai_service.db import init_db
    
    # 初始化数据库
    try:
        print("Initializing database...")
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize database: {e}")
        print("Service will continue, but database operations may fail")
    
    print(f"""
    ======================================
    AI Video Summarizer Service Starting
    ======================================
    Host: {HOST}
    Port: {PORT}
    
    Access API documentation at:
    http://{HOST}:{PORT}/docs
    
    ======================================
    """)
    
    uvicorn.run(
        "src.ai_service.api:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
