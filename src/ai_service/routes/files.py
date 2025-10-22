"""
文件访问相关路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from minio.error import S3Error

router = APIRouter()


@router.get("/files/{file_path:path}")
async def get_file(file_path: str):
    """
    代理访问S3文件
    
    Args:
        file_path: 文件路径（如 videos/xxx.mp4）
    """
    from ..utils import S3Client
    
    print(f"Requesting file: {file_path}")
    
    s3 = S3Client()
    # 检查文件是否存在
    if not s3.file_exists(file_path):
        print(f"File not found in S3: {file_path}")
        print(f"S3 endpoint: {s3.endpoint}, bucket: {s3.bucket_name}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    try:
        print(f"Getting file from S3: {s3.bucket_name}/{file_path}")
        # 从S3下载文件
        response = s3.client.get_object(s3.bucket_name, file_path)
        
        # 返回文件流
        def iterfile():
            try:
                for chunk in response.stream(32*1024):
                    yield chunk
            finally:
                response.close()
                response.release_conn()
        
        # 根据文件类型设置Content-Type
        content_type = "application/octet-stream"
        if file_path.endswith(".mp4"):
            content_type = "video/mp4"
        elif file_path.endswith(".wav"):
            content_type = "audio/wav"
        elif file_path.endswith(".txt"):
            content_type = "text/plain"
        
        print(f"Streaming file with content-type: {content_type}")
        return StreamingResponse(
            iterfile(),
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # 缓存24小时
                "Access-Control-Allow-Origin": "*",  # 允许跨域
            }
        )
        
    except S3Error as e:
        print(f"S3Error getting file: {e}")
        print(f"Error details: {str(e)}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/files/{file_path:path}")
async def debug_file(file_path: str):
    """调试：检查文件是否存在"""
    from ..utils import S3Client
    
    s3 = S3Client()
    
    exists = s3.file_exists(file_path)
    
    try:
        stat = s3.client.stat_object(s3.bucket_name, file_path)
        file_info = {
            "size": stat.size,
            "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
            "content_type": stat.content_type
        }
    except Exception as e:
        file_info = {"error": str(e)}
    
    # 列出bucket中的所有文件
    all_files = s3.list_files(prefix="videos/")
    
    return {
        "file_path": file_path,
        "exists": exists,
        "file_info": file_info,
        "endpoint": s3.endpoint,
        "bucket": s3.bucket_name,
        "all_files_count": len(all_files),
        "all_files": all_files[:20]  # 返回前20个文件
    }

