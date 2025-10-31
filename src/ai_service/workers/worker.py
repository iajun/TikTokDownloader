"""
任务处理Worker（同步版）
后台处理视频下载、音频提取、转录和总结任务
使用新的模块结构，video_id作为文件名，存储视频详情到数据库
"""

from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import json
from dotenv import load_dotenv
import time

# 加载 .env 文件
BASE_DIR = Path(__file__).parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

from src.application import TikTokDownloader
from ..utils import VideoProcessor, AudioExtractor, S3Client
from ..services import TranscriptionService, AISummarizer, EmailService
from ..models import Task, TaskStatus, Video, VideoSummary, EmailSubscription
from ..db import get_db_session
from ..utils.task_queue import run_coro_blocking, run_io_blocking, submit_io_nonblocking, get_task_queue


class TaskWorker:
    """任务处理Worker"""
    
    def __init__(self, deepseek_api_key: str):
        self.deepseek_api_key = deepseek_api_key
        self.s3_client = S3Client()
    
    def _update_task_status(self, task_id: int, status: str, progress: int, **kwargs):
        """更新任务状态的辅助方法"""
        try:
            with get_db_session() as db:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = status
                    task.progress = progress
                    # 更新其他字段
                    for key, value in kwargs.items():
                        setattr(task, key, value)
                    db.commit()
                    print(f"Task {task_id} status updated: {status}, progress: {progress}%")
        except Exception as e:
            # 如果更新失败，打印错误但不抛出异常，避免中断任务处理
            print(f"Failed to update task {task_id} status: {str(e)}")
    
    def _send_email_notifications(self, task_id: int, video_id: str, summary: str, detail_dict: dict):
        """发送邮件通知到所有激活的订阅邮箱"""
        try:
            # 获取所有激活的订阅邮箱
            with get_db_session() as db:
                subscriptions = db.query(EmailSubscription).filter(
                    EmailSubscription.is_active == True
                ).all()
            
            if not subscriptions:
                print("没有激活的邮箱订阅，跳过邮件发送")
                return
            
            # 构建视频信息字典
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
            
            # 发送邮件到所有订阅邮箱
            email_service = EmailService()
            if not email_service.is_configured():
                print("邮件服务未配置，跳过邮件发送")
                return
            
            emails = [sub.email for sub in subscriptions]
            print(f"准备向 {len(emails)} 个邮箱发送总结邮件")
            
            results = email_service.send_batch_summary_emails(
                emails,
                video_info,
                summary
            )
            
            # 统计发送结果
            success_count = sum(1 for success in results.values() if success)
            print(f"邮件发送完成: {success_count}/{len(emails)} 成功")
            
        except Exception as e:
            # 邮件发送失败不应影响任务完成
            print(f"发送邮件通知失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def process_task(self, task_id: int) -> bool:
        """处理单个任务 - 使用独立的数据库会话更新状态（同步）"""
        try:
            # 获取任务信息
            with get_db_session() as db:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    print(f"Task {task_id} not found")
                    return False
                task_url = task.url
            
            # 更新状态为下载中
            self._update_task_status(task_id, TaskStatus.DOWNLOADING.value, 10)
            
            print(f"Starting to process task {task_id} for URL: {task_url}")
            
            # 定义完整的异步操作，确保在同一个事件循环中执行
            async def _process_video_download():
                """在同一个事件循环中处理视频下载"""
                downloader = TikTokDownloader()
                async with downloader:
                    # 更新下载进度
                    self._update_task_status(task_id, TaskStatus.DOWNLOADING.value, 20)
                    
                    # 1. 下载视频
                    video_processor = VideoProcessor(downloader)
                    return await video_processor.download_video(
                        url=task_url,
                        force_download=False
                    )
            
            # 在单个事件循环中执行整个下载操作
            result = run_coro_blocking(_process_video_download)
            
            if not result:
                raise Exception("Failed to download video")
            
            video_path, detail_dict, video_id = result
                    
            if not video_path or not detail_dict or not video_id:
                raise Exception("Failed to download video")
            
            print(f"Video downloaded: {video_path}, Video ID: {video_id}")
            
            # 检查是否已存在完成的任务
            with get_db_session() as db:
                existing_task = db.query(Task).filter(
                    Task.video_id == video_id,
                    Task.status == TaskStatus.COMPLETED.value,
                    Task.id != task_id
                ).first()
                
                if existing_task:
                    # 在会话内提取所有需要的数据，避免延迟加载问题
                    existing_data = {
                        'video_id': existing_task.video_id,
                        'platform': existing_task.platform,
                        'video_path': existing_task.video_path,
                        'audio_path': existing_task.audio_path,
                        'transcription_path': existing_task.transcription_path,
                        'summary_path': existing_task.summary_path,
                        'transcription': existing_task.transcription,
                        'summary': existing_task.summary,
                        'video_db_id': existing_task.video_db_id,
                        'existing_task_id': existing_task.id
                    }
                else:
                    existing_data = None
            
            if existing_data:
                print(f"Video {video_id} already processed in task {existing_data['existing_task_id']}, copying data...")
                # 复制数据并标记为完成
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
                        print(f"Task {task_id} marked as completed with existing data")
                        return True
            
            # 将视频上传到S3
            s3_video_path = f"videos/{video_id}.mp4"
            if not self.s3_client.file_exists(s3_video_path):
                if self.s3_client.upload_file(video_path, s3_video_path):
                    print(f"Video uploaded to S3: {s3_video_path}")
            
            # 更新任务信息
            self._update_task_status(task_id, TaskStatus.DOWNLOADING.value, 30,
                video_id=video_id,
                platform=detail_dict.get('platform', 'douyin'),
                video_path=s3_video_path
            )
            
            # 1.5. 检查或创建 Video 记录
            with get_db_session() as db:
                video = db.query(Video).filter(Video.video_id == video_id).first()
                
                if not video:
                    # 创建新的 Video 记录
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
            
            # 2. 提取音频
            self._update_task_status(task_id, TaskStatus.EXTRACTING_AUDIO.value, 40)
            
            audio_extractor = AudioExtractor()
            audio_path = audio_extractor.extract_audio(video_path, video_id)
            
            if not audio_path:
                raise Exception("Failed to extract audio")
            
            self._update_task_status(task_id, TaskStatus.EXTRACTING_AUDIO.value, 50,
                audio_path=f"videos/{video_id}_audio.wav"
            )
            
            # 3. 语音转文字
            self._update_task_status(task_id, TaskStatus.TRANSCRIBING.value, 60)
            
            transcription_service = TranscriptionService()
            transcription = transcription_service.transcribe(audio_path, video_id)
            
            if not transcription:
                raise Exception("Failed to transcribe audio")
            
            self._update_task_status(task_id, TaskStatus.TRANSCRIBING.value, 70,
                transcription=transcription,
                transcription_path=f"videos/{video_id}_transcription.txt"
            )
            
            # 4. AI总结（在线程池中执行，避免阻塞）
            self._update_task_status(task_id, TaskStatus.SUMMARIZING.value, 80)
            
            # 初始化AISummarizer，会自动从数据库读取当前活跃的AI方法
            ai_summarizer = AISummarizer(self.deepseek_api_key)
            summary = run_io_blocking(
                ai_summarizer.summarize_with_ai,
                transcription,
                video_id
            )
            
            if summary:
                self._update_task_status(task_id, TaskStatus.SUMMARIZING.value, 90,
                    summary=summary,
                    summary_path=f"videos/{video_id}_summary.txt"
                )
                
                # 创建 VideoSummary 记录
                with get_db_session() as db:
                    task = db.query(Task).filter(Task.id == task_id).first()
                    if task:
                        # 获取当前总结数量，用于排序
                        summary_count = db.query(VideoSummary).filter(VideoSummary.task_id == task_id).count()
                        
                        # 获取提示词名称
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
                        print(f"Created VideoSummary record for task {task_id} with name: {summary_name}")
            
            # 发送邮件通知（如果有订阅邮箱）
            self._send_email_notifications(task_id, video_id, summary, detail_dict)
            
            # 更新完成状态
            self._update_task_status(task_id, TaskStatus.COMPLETED.value, 100,
                completed_at=datetime.utcnow()
            )
            
            print(f"Task {task_id} completed successfully")
            return True
                    
        except Exception as e:
            print(f"Error processing task {task_id}: {str(e)}")
            self._update_task_status(task_id, TaskStatus.FAILED.value, 100,
                error_message=str(e),
                completed_at=datetime.utcnow()
            )
            return False


# 全局Worker实例
_worker: TaskWorker = None


def get_worker(deepseek_api_key: str) -> TaskWorker:
    """获取Worker实例"""
    global _worker
    if _worker is None:
        _worker = TaskWorker(deepseek_api_key)
    return _worker


def background_task_processor():
    """后台任务处理器（同步版） - 使用线程池并发处理多个任务"""
    import os
    from datetime import datetime, timedelta
    from ..db import get_db_session
    from ..models import AIMethod
    
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
    
    # 尝试从数据库获取API密钥
    if not deepseek_api_key:
        try:
            with get_db_session() as db:
                method = db.query(AIMethod).filter(
                    AIMethod.is_active == 1,
                    AIMethod.name == "deepseek"
                ).first()
                if method and method.api_key:
                    deepseek_api_key = method.api_key
                    print(f"Loaded API key from database for method: {method.name}")
        except Exception as e:
            print(f"Failed to load API key from database: {e}")
    
    if not deepseek_api_key:
        print("Warning: DEEPSEEK_API_KEY not set and not found in database")
    
    worker = get_worker(deepseek_api_key)
    
    # 并发处理的配置
    MAX_CONCURRENT_TASKS = 3  # 最大并发任务数
    active_futures: Dict[int, Any] = {}  # task_id -> Future
    MAX_TASK_AGE_HOURS = 24  # 超过24小时未完成的任务会被重置
    
    # 启动时：重置所有处于中间状态的任务（可能是应用重启导致）
    print("Initializing background task processor...")
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
            print(f"Found {len(stuck_tasks)} tasks stuck in intermediate states (likely due to app restart)")
            for stuck_task in stuck_tasks:
                print(f"Resetting task {stuck_task.id} from {stuck_task.status} to PENDING")
                stuck_task.status = TaskStatus.PENDING.value
                stuck_task.progress = 0
                stuck_task.updated_at = datetime.utcnow()
                if hasattr(stuck_task, 'error_message'):
                    stuck_task.error_message = None
            
            db.commit()
            print(f"Reset {len(stuck_tasks)} tasks to pending state")
        else:
            print("No stuck tasks found")
    
    print("Background task processor started")
    
    while True:
        try:
            with get_db_session() as db:
                # 重置超过一定时间仍然处于中间状态的任务
                old_tasks_threshold = datetime.utcnow() - timedelta(hours=MAX_TASK_AGE_HOURS)
                old_stuck_tasks = db.query(Task).filter(
                    Task.status.in_([
                        TaskStatus.DOWNLOADING.value,
                        TaskStatus.EXTRACTING_AUDIO.value,
                        TaskStatus.TRANSCRIBING.value,
                        TaskStatus.SUMMARIZING.value
                    ]),
                    Task.updated_at < old_tasks_threshold
                ).all()
                
                for stuck_task in old_stuck_tasks:
                    print(f"Resetting stuck task {stuck_task.id} (status: {stuck_task.status}, last updated: {stuck_task.updated_at})")
                    stuck_task.status = TaskStatus.PENDING.value  # 重置为 pending，重新执行
                    stuck_task.progress = 0  # 重置进度
                    stuck_task.updated_at = datetime.utcnow()
                    # 清除错误信息（如果有的话）
                    if hasattr(stuck_task, 'error_message'):
                        stuck_task.error_message = None
                
                if old_stuck_tasks:
                    db.commit()
                    print(f"Reset {len(old_stuck_tasks)} stuck tasks")
                
                # 查找待处理的任务，限制最多同时处理 MAX_CONCURRENT_TASKS 个
                active_task_ids = set(active_futures.keys())
                
                # 只获取待处理（pending）且不在活跃任务列表中的任务
                pending_tasks = db.query(Task).filter(
                    Task.status == TaskStatus.PENDING.value,  # 只处理 pending 状态的任务
                    ~Task.id.in_(active_task_ids) if active_task_ids else True  # 排除正在处理的任务
                ).order_by(Task.created_at.asc()).limit(MAX_CONCURRENT_TASKS - len(active_futures)).all()
                
                # 为每个任务创建异步任务
                for task in pending_tasks:
                    task_id = task.id
                    print(f"Starting processing task {task_id}")
                    future = submit_io_nonblocking(worker.process_task, task_id)
                    active_futures[task_id] = future

            # 清理已完成的任务
            completed = [tid for tid, fut in active_futures.items() if fut.done()]
            for tid in completed:
                try:
                    _ = active_futures[tid].result()
                except Exception as e:
                    print(f"Error processing task {tid}: {e}")
                finally:
                    del active_futures[tid]

            # 等待一段时间后继续检查
            time.sleep(2)
        except Exception as e:
            print(f"Error in background processor: {str(e)}")
            time.sleep(10)
