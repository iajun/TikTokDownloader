"""
视频处理模块
负责视频下载、平台检测、视频文件查找等功能
使用S3存储，video_id作为文件名
"""

import shutil
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import json

from src.application import TikTokDownloader
from src.application.main_terminal import TikTok
from .s3_client import S3Client  # 同一目录，不需要修改
from .task_queue import run_io_bound

class VideoProcessor:
    """视频处理器"""
    
    def __init__(self, downloader: TikTokDownloader):
        self.downloader = downloader
        self.tiktok_instance = None
        self.s3_client = S3Client()
    
    def detect_platform(self, url: str) -> str:
        """检测URL所属平台"""
        url_lower = url.lower()
        return 'tiktok' if 'tiktok.com' in url_lower else 'douyin'
    
    async def download_video(self, url: str, output_dir: Optional[str] = None, 
                           force_download: bool = False) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        下载视频并返回视频文件路径和详情数据
        
        Returns:
            tuple: (本地视频路径, 视频详情数据字典, 视频ID)
        """
        try:
            print(f"开始下载视频: {url}")
            
            platform = self.detect_platform(url)
            self.downloader.project_info()
            self.downloader.check_config()
            await self.downloader.check_settings(False)
            
            if output_dir:
                self.downloader.parameter.root = Path(output_dir)
            
            self.tiktok_instance = TikTok(self.downloader.parameter, self.downloader.database)
            
            is_tiktok = (platform == 'tiktok')
            run_method = self.tiktok_instance.links_tiktok.run if is_tiktok else self.tiktok_instance.links.run
            ids = await run_method(url)
            
            if not ids:
                raise Exception(f"无法从URL提取视频ID: {url}")
            
            video_id = ids[0] if isinstance(ids, list) else str(ids)
            detail_data, video_name = await self._get_video_details(ids, is_tiktok)
            
            if not detail_data:
                raise Exception("无法获取视频详情")
            
            # 将detail_data转换为字典格式
            detail_dict = self._convert_detail_data_to_dict(detail_data, url, video_id, platform)
            
            # 检查S3中是否已存在文件（使用video_id作为文件名）
            s3_video_path = f"videos/{video_id}.mp4"
            s3_exists = await run_io_bound(self.s3_client.file_exists, s3_video_path)
            if not force_download and s3_exists:
                print(f"找到S3中已下载的视频: {s3_video_path}")
                local_path = await self._download_from_s3_to_temp(s3_video_path, video_id)
                return local_path, detail_dict, video_id
            else:
                if not force_download:
                    print("S3中未找到视频文件，将强制下载")
                force_download = True
            
            # 执行下载
            if force_download:
                await self._clean_existing_files(video_name, video_id)
            
            print("开始下载视频...")
            # downloader.run 本身为异步协程，直接 await，不要包装到 IO 线程池
            await self.tiktok_instance.downloader.run(detail_data, "detail", tiktok=is_tiktok)
            
            video_path = await self._find_downloaded_video(video_name)
            if video_path:
                print(f"视频下载成功: {video_path}")
                return video_path, detail_dict, video_id
            else:
                print("未找到下载的视频文件")
                return None, None, None
            
        except Exception as e:
            print(f"下载视频失败: {str(e)}")
            return None, None, None
    
    def _convert_detail_data_to_dict(self, detail_data: List, url: str, video_id: str, platform: str) -> Dict[str, Any]:
        """将detail_data转换为字典格式"""
        try:
            if not detail_data or len(detail_data) == 0:
                return {}
            
            detail = detail_data[0] if isinstance(detail_data, list) else detail_data
            
            # 提取text_extra标签
            text_extra = []
            if isinstance(detail.get('text_extra'), list):
                text_extra = [tag.get('hashtag_name', '') for tag in detail.get('text_extra', []) if isinstance(tag, dict)]
            
            # 提取tag
            tag = []
            if isinstance(detail.get('tag'), list):
                tag = detail.get('tag', [])
            
            detail_dict = {
                'id': video_id,
                'url': url,
                'platform': platform,
                'desc': detail.get('desc', ''),
                'text_extra': text_extra,
                'tag': tag,
                'type': detail.get('type', ''),
                'height': detail.get('height', 0),
                'width': detail.get('width', 0),
                'duration': detail.get('duration', ''),
                'uri': detail.get('uri', ''),
                'downloads': detail.get('downloads', ''),
                'dynamic_cover': detail.get('dynamic_cover', ''),
                'static_cover': detail.get('static_cover', ''),
                'uid': detail.get('uid', ''),
                'sec_uid': detail.get('sec_uid', ''),
                'unique_id': detail.get('unique_id', ''),
                'signature': detail.get('signature', ''),
                'user_age': detail.get('user_age', 0),
                'nickname': detail.get('nickname', ''),
                'mark': detail.get('mark', ''),
                'music_author': detail.get('music_author', ''),
                'music_title': detail.get('music_title', ''),
                'music_url': detail.get('music_url', ''),
                'digg_count': detail.get('digg_count', 0),
                'comment_count': detail.get('comment_count', 0),
                'collect_count': detail.get('collect_count', 0),
                'share_count': detail.get('share_count', 0),
                'play_count': detail.get('play_count', -1),
                'share_url': detail.get('share_url', ''),
            }
            
            return detail_dict
            
        except Exception as e:
            print(f"转换detail_data失败: {str(e)}")
            return {}
    
    async def _download_from_s3_to_temp(self, s3_path: str, video_id: str) -> str:
        """从S3下载文件到临时目录"""
        import tempfile
        import os
        
        temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
        temp_dir.mkdir(exist_ok=True)
        
        local_path = temp_dir / f"{video_id}.mp4"
        
        if self.s3_client.download_file(s3_path, str(local_path)):
            return str(local_path)
        else:
            return None
    
    async def _get_video_details(self, ids, is_tiktok: bool) -> Tuple[Optional[List], str]:
        """获取视频详情和名称"""
        root, params, logger = self.tiktok_instance.record.run(self.downloader.parameter)
        async with logger(root, console=self.downloader.console, **params) as record:
            detail_data = await self.tiktok_instance._handle_detail(ids, is_tiktok, record, api=True)
            video_name = self._get_video_name_from_detail_data(detail_data, ids)
        return detail_data, video_name
    
    def _get_video_name_from_detail_data(self, detail_data: List, ids) -> str:
        """从detail_data中提取视频名称"""
        try:
            if detail_data and len(detail_data) > 0 and isinstance(detail_data[0], dict):
                return self.tiktok_instance.downloader.generate_detail_name(detail_data[0])
            else:
                return ids[0] if isinstance(ids, list) else str(ids)
        except Exception as e:
            print(f"提取视频名称失败: {str(e)}")
            return ids[0] if isinstance(ids, list) else str(ids)
    
    async def _clean_existing_files(self, video_name: str, video_id: str):
        """清理已存在的文件和记录"""
        download_dir = Path(self.downloader.parameter.root) / "Download"
        
        # video_name 已经通过 generate_detail_name 处理过了，直接使用
        safe_name = video_name
        
        # 清理文件
        if self.downloader.parameter.folder_mode:
            video_folder = download_dir / safe_name
            if video_folder.exists():
                shutil.rmtree(video_folder, ignore_errors=True)
        else:
            for ext in ['.mp4', '.mov', '.avi']:
                file_path = download_dir / f"{safe_name}{ext}"
                if file_path.exists():
                    file_path.unlink()
        
        # 清理数据库记录
        print(f"正在清理视频 {video_id} 的数据库记录...")
        if hasattr(self.downloader, 'recorder') and self.downloader.recorder:
            try:
                # 先检查是否存在记录
                has_record = await self.downloader.recorder.has_id(video_id)
                if has_record:
                    await self.downloader.recorder.delete_id(video_id)
                    print(f"✓ 已清理数据库记录: {video_id}")
                else:
                    print(f"  数据库中不存在记录: {video_id}")
            except Exception as e:
                print(f"清理数据库记录失败: {str(e)}")
        else:
            print("recorder 不可用，跳过数据库清理")
    
    async def _find_downloaded_video(self, video_name: str) -> Optional[str]:
        """查找已下载的视频文件"""
        download_dir = Path(self.downloader.parameter.root) / "Download"
        
        if not download_dir.exists():
            return None
        
        # video_name 已经通过 generate_detail_name 处理过了，直接使用
        safe_name = video_name
        
        # 支持的视频文件扩展名
        video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm']
        
        # 如果启用了文件夹模式，在文件夹内查找
        if self.downloader.parameter.folder_mode:
            video_folder = download_dir / safe_name
            if video_folder.exists() and video_folder.is_dir():
                # 在文件夹中查找视频文件
                for ext in video_extensions:
                    video_file = video_folder / f"{safe_name}{ext}"
                    if video_file.exists() and video_file.is_file():
                        return str(video_file.resolve())
        
        # 非文件夹模式，直接在目录中查找
        for ext in video_extensions:
            video_file = download_dir / f"{safe_name}{ext}"
            if video_file.exists() and video_file.is_file():
                return str(video_file.resolve())
        
        return None

