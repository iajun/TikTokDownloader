"""
数据库连接配置
支持 Supabase (PostgreSQL) 和 MySQL
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
BASE_DIR = Path(__file__).parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

from ..models import Base


# 数据库配置（从环境变量读取）
# 优先使用 DB_URL，如果不提供则使用单独配置
DB_URL = os.getenv("DB_URL", None)

# 数据库类型：supabase (PostgreSQL) 或 mysql
DB_TYPE = os.getenv("DB_TYPE", "supabase").lower()

if DB_URL:
    # 使用完整的数据库URL
    database_url = DB_URL
    
    # 清理连接 URL，移除可能导致错误的参数
    if DB_TYPE == "supabase" and "postgresql://" in database_url:
        # 移除可能存在的无效参数
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(database_url)
            query_params = urllib.parse.parse_qs(parsed.query)
            
            # 检查是否有无效参数
            if query_params:
                print(f"Original URL has {len(query_params)} query parameters")
            
            # 过滤掉无效的参数
            valid_params = {}
            removed_params = []
            for key, value in query_params.items():
                if key not in ['pgbouncer']:  # 移除 pgbouncer 参数
                    valid_params[key] = value
                else:
                    removed_params.append(key)
            
            if removed_params:
                print(f"Removed invalid parameters: {removed_params}")
            
            # 重建 URL
            new_query = urllib.parse.urlencode(valid_params, doseq=True)
            new_parsed = parsed._replace(query=new_query)
            database_url = urllib.parse.urlunparse(new_parsed)
        except Exception as e:
            print(f"Warning: Failed to parse URL: {e}")
            pass
    
    print(f"Using database URL from DB_URL environment variable")
else:
    # 使用单独的配置项
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432" if DB_TYPE == "supabase" else "3306")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    
    if DB_TYPE == "supabase":
        # Supabase (PostgreSQL) 连接
        database_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        # MySQL 连接
        database_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 安全地打印数据库URL（隐藏密码）
safe_url = database_url
for char in ['DB_PASSWORD', 'postgres.', '@aws']:
    if char in database_url:
        # 尝试隐藏密码
        try:
            if '@' in database_url and ':' in database_url.split('@')[0]:
                user_pass = database_url.split('@')[0]
                if ':' in user_pass:
                    password = user_pass.split(':')[1]
                    safe_url = database_url.replace(password, '***')
                    break
        except:
            pass

print(f"Database type: {DB_TYPE}")
print(f"Database URL: {safe_url}")

# 创建数据库引擎
connect_args = {}

if DB_TYPE == "mysql":
    # MySQL 特定配置
    try:
        import cryptography
        connect_args = {}
    except ImportError:
        connect_args = {"auth_plugin": "mysql_native_password"}
elif DB_TYPE == "supabase":
    # PostgreSQL/Supabase 特定配置
    # Supabase pooler（端口 6543）默认启用 SSL 连接
    # 使用空的 connect_args，让 psycopg2 自动处理
    connect_args = {}

# 对于 Supabase，确保使用 postgresql:// 而不是 postgresql+psycopg2://
if DB_TYPE == "supabase" and database_url.startswith("postgresql://"):
    # SQLAlchemy 会自动识别 postgresql:// 协议并使用 psycopg2
    pass

# 优化连接池配置以提升性能
# pool_size: 保持的连接数
# max_overflow: 允许的额外连接数（临时）
# pool_pre_ping: 自动检测并重连断开的连接
# pool_recycle: 连接回收时间（秒），避免长时间连接导致的问题
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=20,  # 增加连接池大小（从10增加到20）
    max_overflow=30,  # 增加溢出连接数（从20增加到30）
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_recycle=3600,  # 每小时回收一次连接，避免长时间连接问题
    echo=False,
    connect_args=connect_args
)

# 创建会话工厂
SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """获取数据库会话"""
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器"""
    db = SessionFactory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """删除数据库表（用于测试）"""
    Base.metadata.drop_all(bind=engine)
