"""
测试数据库连接脚本
用于验证 Supabase 或 MySQL 数据库连接配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import sys

# 加载 .env 文件
BASE_DIR = Path(__file__).parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

# 读取配置
DB_TYPE = os.getenv("DB_TYPE", "supabase").lower()
DB_URL = os.getenv("DB_URL", None)

print("=" * 60)
print("数据库连接测试")
print("=" * 60)
print(f"数据库类型: {DB_TYPE}")

if DB_URL:
    print(f"使用 DB_URL 配置")
    print(f"数据库 URL: {DB_URL[:50]}...")  # 只显示前50个字符
    
    # 显示连接 URL 的前50个字符（隐藏敏感信息）
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(DB_URL)
        print(f"主机: {parsed.hostname}")
        print(f"端口: {parsed.port}")
        print(f"数据库: {parsed.path.lstrip('/')}")
    except Exception as e:
        print(f"警告: 无法解析 URL: {e}")
else:
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432" if DB_TYPE == "supabase" else "3306")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_NAME = os.getenv("DB_NAME", "postgres")
    
    print(f"使用单独配置项")
    print(f"主机: {DB_HOST}")
    print(f"端口: {DB_PORT}")
    print(f"用户: {DB_USER}")
    print(f"数据库: {DB_NAME}")

print()

# 测试连接
print("尝试连接数据库...")
try:
    if DB_TYPE == "supabase":
        try:
            import psycopg2
            print("✓ psycopg2 已安装")
        except ImportError:
            print("✗ psycopg2 未安装")
            print("请运行: pip install psycopg2-binary")
            sys.exit(1)
        
        # 测试连接
        if DB_URL:
            # 清理 URL
            import urllib.parse
            parsed = urllib.parse.urlparse(DB_URL)
            query_params = urllib.parse.parse_qs(parsed.query)
            
            valid_params = {}
            for key, value in query_params.items():
                if key not in ['pgbouncer']:
                    valid_params[key] = value
            
            new_query = urllib.parse.urlencode(valid_params, doseq=True)
            cleaned_url = urllib.parse.urlunparse(parsed._replace(query=new_query))
            
            conn = psycopg2.connect(cleaned_url)
        else:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT", 6543)),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME")
            )
        
        print("✓ 连接成功!")
        
        # 测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✓ PostgreSQL 版本: {version[0]}")
        
        # 列出表
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"\n✓ 已存在的表 ({len(tables)} 个):")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("\n⚠ 数据库中还没有表，启动服务时会自动创建")
        
        cursor.close()
        conn.close()
        
    elif DB_TYPE == "mysql":
        try:
            import pymysql
            print("✓ pymysql 已安装")
        except ImportError:
            print("✗ pymysql 未安装")
            print("请运行: pip install pymysql")
            sys.exit(1)
        
        # 测试连接
        if DB_URL:
            import re
            # 从 MySQL URL 中提取参数
            pattern = r'mysql\+pymysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
            match = re.match(pattern, DB_URL)
            if not match:
                raise ValueError("无效的 MySQL URL 格式")
            
            user, password, host, port, database = match.groups()
            
            conn = pymysql.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=database
            )
        else:
            conn = pymysql.connect(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT", 3306)),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME")
            )
        
        print("✓ 连接成功!")
        
        # 测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()
        print(f"✓ MySQL 版本: {version[0]}")
        
        cursor.close()
        conn.close()
    
    print("\n" + "=" * 60)
    print("✓ 数据库连接测试通过！")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ 连接失败: {e}")
    print("\n故障排查建议:")
    print("1. 检查网络连接")
    print("2. 验证数据库配置是否正确")
    print("3. 确认数据库服务是否运行")
    if DB_TYPE == "supabase":
        print("4. 检查 Supabase 项目是否创建并运行")
        print("5. 确认使用 pooler 连接（端口 6543）")
    sys.exit(1)

