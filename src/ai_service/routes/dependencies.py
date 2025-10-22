"""
API 依赖函数和工具函数
"""
from typing import List
from sqlalchemy.orm import Session
from src.application import TikTokDownloader
from src.application.main_terminal import TikTok
from ..models import Task


async def _extract_video_urls(url: str, url_type: str, max_count: int) -> List[str]:
    """
    从合集或作者链接中提取所有视频URL
    
    Args:
        url: 合集或作者链接
        url_type: 类型 ('mix', 'account', 'video', 'auto')
        max_count: 最大提取数量
        
    Returns:
        视频URL列表
    """
    # 初始化下载器
    downloader = TikTokDownloader()
    await downloader.__aenter__()
    
    try:
        # 必须先初始化 parameter（按 video_processor 的模式）
        downloader.project_info()
        downloader.check_config()
        await downloader.check_settings(False)
        
        tiktok_instance = TikTok(downloader.parameter, downloader.database)
        
        # 如果类型为auto，自动检测
        if url_type == 'auto':
            if 'collection' in url or '/collection/' in url or '/mix' in url:
                url_type = 'mix'
            elif 'user' in url or '/user/' in url or 'sec_uid' in url:
                url_type = 'account'
            else:
                url_type = 'video'
        
        video_urls = []
        
        if url_type == 'mix':
            # 处理合集
            print(f"Extracting video URLs from mix: {url}")
            # links.run() 返回 (is_mix, ids) 元组
            mix_result = await tiktok_instance.links.run(url, type_="mix")
            mix_id = None
            detail_id = None
            
            if isinstance(mix_result, tuple) and len(mix_result) == 2:
                is_mix, ids = mix_result
                if is_mix and ids:
                    # 这是合集
                    mix_id = True
                    detail_id = ids[0] if isinstance(ids, list) and ids else ids if isinstance(ids, str) else None
                elif not is_mix and ids:
                    # 这是视频，不是合集 - 只返回单个视频
                    video_id = ids[0] if isinstance(ids, list) and ids else ids if isinstance(ids, str) else None
                    if video_id:
                        # 返回原始URL作为单个视频
                        video_urls.append(url)
                        return video_urls
            
            if mix_id is not None and detail_id:
                try:
                    # 调用deal_mix_detail
                    mix_data = await tiktok_instance.deal_mix_detail(
                        mix_id=mix_id,
                        id_=detail_id,
                        api=False,
                        source=True,
                        tiktok=False
                    )
                    
                    if mix_data and isinstance(mix_data, list):
                        for item in mix_data:
                            if item.get('share_url'):
                                video_urls.append(item['share_url'])
                            if len(video_urls) >= max_count:
                                break
                except Exception as e:
                    print(f"Error processing mix: {e}")
                    # 如果处理失败，返回原始URL作为单个视频
                    video_urls.append(url)
        
        elif url_type == 'account':
            # 处理作者视频
            print(f"Extracting video URLs from account: {url}")
            try:
                # links.run() 返回 list[str]
                sec_user_id_list = await tiktok_instance.links.run(url, type_="user")
                sec_user_id = None
                
                if isinstance(sec_user_id_list, list) and sec_user_id_list:
                    sec_user_id = sec_user_id_list[0]
                elif isinstance(sec_user_id_list, str):
                    sec_user_id = sec_user_id_list
                
                if sec_user_id:
                    account_data = await tiktok_instance.deal_account_detail(
                        index=0,
                        sec_user_id=sec_user_id,
                        api=False,
                        source=True,
                        tiktok=False
                    )
                    
                    if account_data and isinstance(account_data, list):
                        for item in account_data:
                            if item.get('share_url'):
                                video_urls.append(item['share_url'])
                            if len(video_urls) >= max_count:
                                break
            except Exception as e:
                print(f"Error processing account: {e}")
                # 如果处理失败，尝试作为单个视频处理
                pass
        
        elif url_type == 'video':
            # 单个视频
            video_urls = [url]
        
        # 如果没有提取到任何URL，返回原始URL作为单个视频
        if not video_urls:
            print("No videos extracted, treating as single video")
            video_urls = [url]
        
        print(f"Extracted {len(video_urls)} video URLs")
        return video_urls

    except Exception as e:
        print(f"Error extracting video URLs: {e}")
        return []
        
    finally:
        await downloader.__aexit__(None, None, None)


def _delete_task_files(task, db):
    """
    删除任务的S3文件（辅助函数）
    
    Args:
        task: 任务对象
        db: 数据库会话
    """
    from ..utils import S3Client
    s3 = S3Client()
    
    # 使用video_id查询其他任务是否也在使用这些文件
    if task.video_id:
        other_tasks = db.query(Task).filter(
            Task.video_id == task.video_id,
            Task.id != task.id
        ).all()
        
        has_other_tasks = len(other_tasks) > 0
    else:
        has_other_tasks = False
    
    # 只有当没有其他任务使用这些文件时，才删除S3文件
    if not has_other_tasks:
        try:
            if task.video_path and task.video_path.startswith("videos/"):
                s3.delete_file(task.video_path)
                print(f"Deleted S3 file: {task.video_path}")
        except Exception as e:
            print(f"Failed to delete video file: {e}")
            
        try:
            if task.audio_path and task.audio_path.startswith("videos/"):
                s3.delete_file(task.audio_path)
                print(f"Deleted S3 file: {task.audio_path}")
        except Exception as e:
            print(f"Failed to delete audio file: {e}")
            
        try:
            if task.transcription_path and task.transcription_path.startswith("videos/"):
                s3.delete_file(task.transcription_path)
                print(f"Deleted S3 file: {task.transcription_path}")
        except Exception as e:
            print(f"Failed to delete transcription file: {e}")
            
        try:
            if task.summary_path and task.summary_path.startswith("videos/"):
                s3.delete_file(task.summary_path)
                print(f"Deleted S3 file: {task.summary_path}")
        except Exception as e:
            print(f"Failed to delete summary file: {e}")
    else:
        print(f"Not deleting S3 files for video_id {task.video_id} because other tasks still reference them")

