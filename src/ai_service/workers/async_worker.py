"""
异步任务处理Worker
提供高性能的异步任务处理能力
"""

import asyncio
from typing import Dict, Any, Optional, Set
from datetime import datetime, timedelta
import os
from contextlib import asynccontextmanager

from ..utils import VideoProcessor, AudioExtractor, S3Client
from ..services import TranscriptionService, AISummarizer, EmailService, ObsidianService
from ..models import Task, TaskStatus, Video, VideoSummary, EmailSubscription
from ..db import get_db_session
from ..utils.task_queue import run_io_bound, run_cpu_bound, get_task_queue
from src.application import TikTokDownloader


class AsyncTaskProcessor:
    """异步任务处理器"""
    
    def __init__(self, max_concurrent_tasks: int = 5):
        """
        初始化异步任务处理器
        
        Args:
            max_concurrent_tasks: 最大并发任务数
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self.running = False
        self.task_queue = get_task_queue()
        self._worker = None
        self._deepseek_api_key = None
        
    async def _load_api_key(self):
        """异步加载API密钥"""
        try:
            from ..models import AIMethod
            
            with get_db_session() as db:
                method = db.query(AIMethod).filter(
                    AIMethod.is_active == 1,
                    AIMethod.name == "deepseek"
                ).first()
                if method and method.api_key:
                    self._deepseek_api_key = method.api_key
                    print(f"Loaded API key from database for method: {method.name}")
                    return self._deepseek_api_key
        except Exception as e:
            print(f"Failed to load API key from database: {e}")
        
        # 从环境变量获取
        self._deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not self._deepseek_api_key:
            print("Warning: DEEPSEEK_API_KEY not set and not found in database")
        
        return self._deepseek_api_key
    
    async def _reset_stuck_tasks(self):
        """重置处于中间状态的卡住任务"""
        try:
            with get_db_session() as db:
                stuck_tasks = db.query(Task).filter(
                    Task.status.in_([
                        TaskStatus.DOWNLOADING.value,
                        TaskStatus.EXTRACTING_AUDIO.value,
                        TaskStatus.TRANSCRIBING.value,
                        TaskStatus.SUMMARIZING.value
                    ])
                ).all()
                
                if stuck_tasks:
                    print(f"Found {len(stuck_tasks)} stuck tasks, resetting...")
                    for stuck_task in stuck_tasks:
                        stuck_task.status = TaskStatus.PENDING.value
                        stuck_task.progress = 0
                        stuck_task.updated_at = datetime.utcnow()
                        if hasattr(stuck_task, 'error_message'):
                            stuck_task.error_message = None
                    
                    db.commit()
                    print(f"Reset {len(stuck_tasks)} stuck tasks")
        except Exception as e:
            print(f"Error resetting stuck tasks: {e}")
    
    async def _reset_old_stuck_tasks(self, max_age_hours: int = 24):
        """重置超过指定时间的卡住任务"""
        try:
            old_threshold = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            with get_db_session() as db:
                old_stuck_tasks = db.query(Task).filter(
                    Task.status.in_([
                        TaskStatus.DOWNLOADING.value,
                        TaskStatus.EXTRACTING_AUDIO.value,
                        TaskStatus.TRANSCRIBING.value,
                        TaskStatus.SUMMARIZING.value
                    ]),
                    Task.updated_at < old_threshold
                ).all()
                
                if old_stuck_tasks:
                    print(f"Resetting {len(old_stuck_tasks)} old stuck tasks...")
                    for stuck_task in old_stuck_tasks:
                        stuck_task.status = TaskStatus.PENDING.value
                        stuck_task.progress = 0
                        stuck_task.updated_at = datetime.utcnow()
                        if hasattr(stuck_task, 'error_message'):
                            stuck_task.error_message = None
                    
                    db.commit()
                    print(f"Reset {len(old_stuck_tasks)} old stuck tasks")
        except Exception as e:
            print(f"Error resetting old stuck tasks: {e}")
    
    async def _update_task_status(
        self, 
        task_id: int, 
        status: str, 
        progress: int, 
        **kwargs
    ):
        """异步更新任务状态"""
        try:
            # 使用线程池执行同步的数据库操作
            def _update():
                with get_db_session() as db:
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        task.status = status
                        task.progress = progress
                        for key, value in kwargs.items():
                            setattr(task, key, value)
                        db.commit()
                        return True
                return False
            
            await run_io_bound(_update)
            print(f"Task {task_id} status updated: {status}, progress: {progress}%")
        except Exception as e:
            print(f"Failed to update task {task_id} status: {str(e)}")
    
    async def _send_email_notifications(
        self, 
        task_id: int, 
        video_id: str, 
        summary: str, 
        detail_dict: dict
    ):
        """异步发送邮件通知"""
        try:
            def _get_emails():
                with get_db_session() as db:
                    subscriptions = db.query(EmailSubscription).filter(
                        EmailSubscription.is_active == True
                    ).all()
                    return [sub.email for sub in subscriptions]
            
            emails = await run_io_bound(_get_emails)
            
            if not emails:
                print("No active email subscriptions, skipping email notification")
                return
            
            video_info = {
                'video_id': video_id,
                'platform': detail_dict.get('platform', 'douyin'),
                'desc': detail_dict.get('desc', '无标题'),
                'nickname': detail_dict.get('nickname', '未知'),
                'url': detail_dict.get('share_url', ''),
                'share_url': detail_dict.get('share_url', ''),
                'digg_count': detail_dict.get('digg_count', 0),
                'comment_count': detail_dict.get('comment_count', 0),
                'share_count': detail_dict.get('share_count', 0),
            }
            
            email_service = EmailService()
            if not email_service.is_configured():
                print("Email service not configured, skipping email notification")
                return
            
            print(f"Preparing to send summary emails to {len(emails)} subscribers")
            
            # 在线程池中执行邮件发送（因为EmailService是同步的）
            def _send_emails():
                results = email_service.send_batch_summary_emails(
                    emails,
                    video_info,
                    summary
                )
                success_count = sum(1 for success in results.values() if success)
                return success_count, len(emails)
            
            success_count, total_count = await run_io_bound(_send_emails)
            print(f"Email notification completed: {success_count}/{total_count} succeeded")
            
        except Exception as e:
            print(f"Failed to send email notifications: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def _send_to_obsidian(
        self, 
        task_id: int, 
        video_id: str, 
        summary: str, 
        detail_dict: dict
    ):
        """异步同步总结到 Obsidian"""
        try:
            # 获取总结名称（从数据库查询最新的总结记录）
            def _get_summary_info():
                with get_db_session() as db:
                    # 获取最新的总结记录
                    latest_summary = db.query(VideoSummary).filter(
                        VideoSummary.task_id == task_id
                    ).order_by(VideoSummary.created_at.desc()).first()
                    
                    summary_name = "总结"
                    if latest_summary:
                        summary_name = latest_summary.name or "总结"
                    
                    return summary_name
            
            summary_name = await run_io_bound(_get_summary_info)
            
            video_info = {
                'video_id': video_id,
                'platform': detail_dict.get('platform', 'douyin'),
                'desc': detail_dict.get('desc', '无标题'),
                'nickname': detail_dict.get('nickname', '未知'),
                'url': detail_dict.get('share_url', ''),
                'share_url': detail_dict.get('share_url', ''),
                'digg_count': detail_dict.get('digg_count', 0),
                'comment_count': detail_dict.get('comment_count', 0),
                'share_count': detail_dict.get('share_count', 0),
            }
            
            obsidian_service = ObsidianService()
            if not obsidian_service.is_configured():
                print("Obsidian service not configured, skipping Obsidian sync")
                return
            
            print(f"Preparing to save summary to Obsidian")
            
            # 在线程池中执行 Obsidian 同步（因为 ObsidianService 是同步的）
            def _save_to_obsidian():
                result = obsidian_service.save_summary_to_obsidian(
                    video_info,
                    summary,
                    summary_name
                )
                return result
            
            file_path = await run_io_bound(_save_to_obsidian)
            if file_path:
                print(f"Summary saved to Obsidian: {file_path}")
            else:
                print(f"Failed to save summary to Obsidian")
            
        except Exception as e:
            print(f"Failed to save summary to Obsidian: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def process_task_async(self, task_id: int) -> bool:
        """异步处理单个任务"""
        try:
            # 获取任务信息
            def _get_task():
                with get_db_session() as db:
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        return task.url, {
                            'id': task.id,
                            'url': task.url,
                            'status': task.status
                        }
                    return None, None
            
            task_url, task_info = await run_io_bound(_get_task)
            
            if not task_url:
                print(f"Task {task_id} not found")
                return False
            
            # 更新状态为下载中
            await self._update_task_status(task_id, TaskStatus.DOWNLOADING.value, 10)
            
            print(f"Starting to process task {task_id} for URL: {task_url}")
            
            # 1. 下载视频（异步）
            await self._update_task_status(task_id, TaskStatus.DOWNLOADING.value, 20)
            
            downloader = TikTokDownloader()
            async with downloader:
                video_processor = VideoProcessor(downloader)
                result = await video_processor.download_video(
                    url=task_url,
                    force_download=False
                )
            
            if not result:
                raise Exception("Failed to download video")
            
            video_path, detail_dict, video_id = result
            
            if not video_path or not detail_dict or not video_id:
                raise Exception("Failed to download video")
            
            print(f"Video downloaded: {video_path}, Video ID: {video_id}")
            
            # 检查是否已存在完成的任务
            def _check_existing():
                with get_db_session() as db:
                    existing_task = db.query(Task).filter(
                        Task.video_id == video_id,
                        Task.status == TaskStatus.COMPLETED.value,
                        Task.id != task_id
                    ).first()
                    
                    if existing_task:
                        return {
                            'video_id': existing_task.video_id,
                            'platform': existing_task.platform,
                            'video_path': existing_task.video_path,
                            'audio_path': existing_task.audio_path,
                            'transcription_path': existing_task.transcription_path,
                            'summary_path': existing_task.summary_path,
                            'transcription': existing_task.transcription,
                            'summary': existing_task.summary,
                            'video_db_id': existing_task.video_db_id,
                        }
                    return None
            
            existing_data = await run_io_bound(_check_existing)
            
            if existing_data:
                print(f"Video {video_id} already processed, copying data...")
                def _copy_data():
                    with get_db_session() as db:
                        task = db.query(Task).filter(Task.id == task_id).first()
                        if task:
                            task.video_id = existing_data['video_id']
                            task.platform = existing_data['platform']
                            task.video_path = existing_data['video_path']
                            task.audio_path = existing_data['audio_path']
                            task.transcription_path = existing_data['transcription_path']
                            task.summary_path = existing_data['summary_path']
                            task.transcription = existing_data['transcription']
                            task.summary = existing_data['summary']
                            task.video_db_id = existing_data['video_db_id']
                            task.status = TaskStatus.COMPLETED.value
                            task.progress = 100
                            task.completed_at = datetime.utcnow()
                            db.commit()
                            return True
                    return False
                
                await run_io_bound(_copy_data)
                print(f"Task {task_id} marked as completed with existing data")
                return True
            
            # 上传视频到S3
            s3_client = S3Client()
            s3_video_path = f"videos/{video_id}.mp4"
            
            def _upload_video():
                if not s3_client.file_exists(s3_video_path):
                    return s3_client.upload_file(video_path, s3_video_path)
                return True
            
            uploaded = await run_io_bound(_upload_video)
            if uploaded:
                print(f"Video uploaded to S3: {s3_video_path}")
            
            # 更新任务信息
            await self._update_task_status(
                task_id, 
                TaskStatus.DOWNLOADING.value, 
                30,
                video_id=video_id,
                platform=detail_dict.get('platform', 'douyin'),
                video_path=s3_video_path
            )
            
            # 检查或创建 Video 记录
            def _create_video_record():
                import json
                with get_db_session() as db:
                    video = db.query(Video).filter(Video.video_id == video_id).first()
                    
                    if not video:
                        video = Video(
                            video_id=video_id,
                            platform=detail_dict.get('platform', 'douyin'),
                            desc=detail_dict.get('desc', ''),
                            text_extra=json.dumps(detail_dict.get('text_extra', [])),
                            tag=json.dumps(detail_dict.get('tag', [])),
                            type=detail_dict.get('type', ''),
                            height=detail_dict.get('height', 0),
                            width=detail_dict.get('width', 0),
                            duration=detail_dict.get('duration', ''),
                            uri=detail_dict.get('uri', ''),
                            dynamic_cover=detail_dict.get('dynamic_cover', ''),
                            static_cover=detail_dict.get('static_cover', ''),
                            uid=detail_dict.get('uid', ''),
                            sec_uid=detail_dict.get('sec_uid', ''),
                            unique_id=detail_dict.get('unique_id', ''),
                            signature=detail_dict.get('signature', ''),
                            user_age=detail_dict.get('user_age', 0),
                            nickname=detail_dict.get('nickname', ''),
                            mark=detail_dict.get('mark', ''),
                            music_author=detail_dict.get('music_author', ''),
                            music_title=detail_dict.get('music_title', ''),
                            music_url=detail_dict.get('music_url', ''),
                            digg_count=detail_dict.get('digg_count', 0),
                            comment_count=detail_dict.get('comment_count', 0),
                            collect_count=detail_dict.get('collect_count', 0),
                            share_count=detail_dict.get('share_count', 0),
                            play_count=detail_dict.get('play_count', -1),
                            extra=detail_dict.get('extra', ''),
                            share_url=detail_dict.get('share_url', ''),
                            collection_time=datetime.utcnow().isoformat(),
                        )
                        db.add(video)
                        db.commit()
                        db.refresh(video)
                        print(f"Created new Video record: {video_id}")
                    else:
                        print(f"Using existing Video record: {video_id}")
                    
                    # 更新任务的 video_db_id
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        task.video_db_id = video.id
                        db.commit()
                    
                    return video.id
            
            await run_io_bound(_create_video_record)
            
            # 2. 提取音频
            await self._update_task_status(task_id, TaskStatus.EXTRACTING_AUDIO.value, 40)
            
            audio_extractor = AudioExtractor()
            # 使用异步版本的音频提取方法
            audio_path = await audio_extractor.extract_audio_async(
                video_path,
                video_id
            )
            
            if not audio_path:
                raise Exception("Failed to extract audio")
            
            await self._update_task_status(
                task_id,
                TaskStatus.EXTRACTING_AUDIO.value,
                50,
                audio_path=f"videos/{video_id}_audio.wav"
            )
            
            # 3. 语音转文字（CPU密集型，使用进程池）
            await self._update_task_status(task_id, TaskStatus.TRANSCRIBING.value, 60)
            
            transcription_service = TranscriptionService()
            transcription = await run_cpu_bound(
                transcription_service.transcribe,
                audio_path,
                video_id
            )
            
            if not transcription:
                raise Exception("Failed to transcribe audio")
            
            await self._update_task_status(
                task_id,
                TaskStatus.TRANSCRIBING.value,
                70,
                transcription=transcription,
                transcription_path=f"videos/{video_id}_transcription.txt"
            )
            
            # 4. AI总结（在线程池中执行）
            await self._update_task_status(task_id, TaskStatus.SUMMARIZING.value, 80)
            
            ai_summarizer = AISummarizer(self._deepseek_api_key)
            summary = await run_io_bound(
                ai_summarizer.summarize_with_ai,
                transcription,
                video_id
            )
            
            if summary:
                await self._update_task_status(
                    task_id,
                    TaskStatus.SUMMARIZING.value,
                    90,
                    summary=summary,
                    summary_path=f"videos/{video_id}_summary.txt"
                )
                
                # 创建 VideoSummary 记录
                def _create_summary():
                    with get_db_session() as db:
                        task = db.query(Task).filter(Task.id == task_id).first()
                        if task:
                            summary_count = db.query(VideoSummary).filter(
                                VideoSummary.task_id == task_id
                            ).count()
                            
                            prompt_info = ai_summarizer._get_default_prompt_info()
                            summary_name = prompt_info['name'] if prompt_info else "默认总结"
                            
                            video_summary = VideoSummary(
                                task_id=task_id,
                                name=summary_name,
                                content=summary,
                                custom_prompt=None,
                                sort_order=summary_count
                            )
                            db.add(video_summary)
                            db.commit()
                            print(f"Created VideoSummary record for task {task_id}")
                
                await run_io_bound(_create_summary)
            
            # 发送邮件通知
            await self._send_email_notifications(task_id, video_id, summary, detail_dict)
            
            # 同步到 Obsidian
            await self._send_to_obsidian(task_id, video_id, summary, detail_dict)
            
            # 更新完成状态
            await self._update_task_status(
                task_id,
                TaskStatus.COMPLETED.value,
                100,
                completed_at=datetime.utcnow()
            )
            
            print(f"Task {task_id} completed successfully")
            return True
            
        except Exception as e:
            print(f"Error processing task {task_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            await self._update_task_status(
                task_id,
                TaskStatus.FAILED.value,
                100,
                error_message=str(e),
                completed_at=datetime.utcnow()
            )
            return False
    
    async def start(self):
        """启动异步任务处理器"""
        if self.running:
            print("Async task processor is already running")
            return
        
        self.running = True
        
        # 加载API密钥
        await self._load_api_key()
        
        # 重置卡住的任务
        await self._reset_stuck_tasks()
        
        print("Async task processor started")
        
        # 主循环
        while self.running:
            try:
                # 定期重置旧任务
                await self._reset_old_stuck_tasks(max_age_hours=24)
                
                # 清理已完成的任务
                completed_task_ids = [
                    task_id for task_id, task in self.active_tasks.items()
                    if task.done()
                ]
                
                for task_id in completed_task_ids:
                    task = self.active_tasks.pop(task_id, None)
                    if task:
                        try:
                            result = await task
                            if not result:
                                print(f"Task {task_id} failed")
                        except Exception as e:
                            print(f"Error in task {task_id}: {e}")
                
                # 获取待处理的任务
                def _get_pending_tasks():
                    with get_db_session() as db:
                        active_task_ids = set(self.active_tasks.keys())
                        pending_tasks = db.query(Task).filter(
                            Task.status == TaskStatus.PENDING.value,
                            ~Task.id.in_(active_task_ids) if active_task_ids else True
                        ).order_by(Task.created_at.asc()).limit(
                            self.max_concurrent_tasks - len(self.active_tasks)
                        ).all()
                        return [task.id for task in pending_tasks]
                
                pending_task_ids = await run_io_bound(_get_pending_tasks)
                
                # 为每个待处理任务创建异步任务
                for task_id in pending_task_ids:
                    if len(self.active_tasks) >= self.max_concurrent_tasks:
                        break
                    
                    print(f"Starting async processing for task {task_id}")
                    task = asyncio.create_task(self.process_task_async(task_id))
                    self.active_tasks[task_id] = task
                
                # 等待一段时间后继续
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error in async task processor loop: {str(e)}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(10)
    
    async def stop(self):
        """停止异步任务处理器"""
        print("Stopping async task processor...")
        self.running = False
        
        # 等待所有活跃任务完成
        if self.active_tasks:
            print(f"Waiting for {len(self.active_tasks)} active tasks to complete...")
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        print("Async task processor stopped")
    
    def get_status(self) -> dict:
        """获取处理器状态"""
        return {
            "running": self.running,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "active_tasks_count": len(self.active_tasks),
            "active_task_ids": list(self.active_tasks.keys())
        }


# 全局异步任务处理器实例
_async_processor: Optional[AsyncTaskProcessor] = None


def get_async_processor(max_concurrent_tasks: int = 5) -> AsyncTaskProcessor:
    """获取全局异步任务处理器实例"""
    global _async_processor
    if _async_processor is None:
        _async_processor = AsyncTaskProcessor(max_concurrent_tasks=max_concurrent_tasks)
    return _async_processor

