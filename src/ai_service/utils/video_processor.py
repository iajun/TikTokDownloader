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
from .bilibili_downloader import BilibiliDownloader

class VideoProcessor:
    """视频处理器"""
    
    def __init__(self, downloader: TikTokDownloader, bilibili_cookies: Optional[str] = None):
        """
        初始化视频处理器
        
        Args:
            downloader: TikTok下载器实例
            bilibili_cookies: Bilibili Cookie 文件路径或内容
        """
        self.downloader = downloader
        self.tiktok_instance = None
        self.s3_client = S3Client()
        self.bilibili_cookies = bilibili_cookies
        self.bilibili_downloader = None
        if bilibili_cookies:
            try:
                self.bilibili_downloader = BilibiliDownloader(cookies=bilibili_cookies)
            except Exception as e:
                print(f"初始化 Bilibili 下载器失败: {e}")
    
    def detect_platform(self, url: str) -> str:
        """检测URL所属平台"""
        url_lower = url.lower()
        if 'bilibili.com' in url_lower:
            return 'bilibili'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        else:
            return 'douyin'
    
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
            
            # 如果是 Bilibili 平台，使用 Bilibili 下载器
            if platform == 'bilibili':
                return await self._download_bilibili_video(url, output_dir, force_download)
            
            # 其他平台使用原有的 TikTok/Douyin 下载逻辑
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
            
            # 先检查本地是否已有下载的视频文件
            if not force_download:
                local_video_path = await self._check_local_video(video_id, video_name)
                if local_video_path:
                    print(f"找到本地已下载的视频: {local_video_path}")
                    return local_video_path, detail_dict, video_id
            
            # 如果本地没有，再检查S3中是否已存在文件（使用video_id作为文件名）
            if not force_download:
                s3_video_path = f"videos/{video_id}.mp4"
                s3_exists = await run_io_bound(self.s3_client.file_exists, s3_video_path)
                if s3_exists:
                    print(f"找到S3中已下载的视频: {s3_video_path}")
                    local_path = await self._download_from_s3_to_temp(s3_video_path, video_id)
                    return local_path, detail_dict, video_id
                else:
                    print("本地和S3中均未找到视频文件，将强制下载")
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
            import traceback
            traceback.print_exc()
            return None, None, None
    
    async def _download_bilibili_video(
        self,
        url: str,
        output_dir: Optional[str] = None,
        force_download: bool = False
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        下载 Bilibili 视频
        
        Args:
            url: Bilibili 视频 URL
            output_dir: 输出目录
            force_download: 是否强制下载
            
        Returns:
            tuple: (本地视频路径, 视频详情数据字典, 视频ID)
        """
        try:
            # 确保 Bilibili 下载器已初始化
            if not self.bilibili_downloader:
                # 尝试重新初始化
                if self.bilibili_cookies:
                    self.bilibili_downloader = BilibiliDownloader(cookies=self.bilibili_cookies)
                else:
                    self.bilibili_downloader = BilibiliDownloader()
            
            # 设置输出目录
            if output_dir:
                download_dir = Path(output_dir) / "Download"
            else:
                # 尝试使用 downloader 的 root 路径，如果不可用则使用默认路径
                if (self.downloader and 
                    hasattr(self.downloader, 'parameter') and 
                    self.downloader.parameter and 
                    hasattr(self.downloader.parameter, 'root') and 
                    self.downloader.parameter.root):
                    download_dir = Path(self.downloader.parameter.root) / "Download"
                else:
                    # 使用默认的 Volume/Download 目录
                    from src.custom import PROJECT_ROOT
                    download_dir = PROJECT_ROOT / "Download"
            
            download_dir.mkdir(parents=True, exist_ok=True)
            
            # 先获取视频信息
            info = await run_io_bound(self.bilibili_downloader.extract_video_info, url)
            if not info:
                raise Exception("无法获取 Bilibili 视频信息")
            
            # 提取视频ID（从URL或信息中）
            video_id = self._extract_bilibili_video_id(url, info)
            title = info.get('title', '')
            
            # 转换为统一的详情字典格式
            detail_dict = self._convert_bilibili_info_to_dict(info, url, video_id)
            
            # 先检查本地是否已有下载的视频文件
            if not force_download:
                local_video_path = await self._check_local_bilibili_video(video_id, title, download_dir)
                if local_video_path:
                    print(f"找到本地已下载的视频: {local_video_path}")
                    return local_video_path, detail_dict, video_id
            
            # 如果本地没有，再检查S3中是否已存在文件
            if not force_download:
                s3_video_path = f"videos/{video_id}.mp4"
                s3_exists = await run_io_bound(self.s3_client.file_exists, s3_video_path)
                if s3_exists:
                    print(f"找到S3中已下载的视频: {s3_video_path}")
                    local_path = await self._download_from_s3_to_temp(s3_video_path, video_id)
                    return local_path, detail_dict, video_id
                else:
                    print("本地和S3中均未找到视频文件，将强制下载")
                    force_download = True
            
            # 执行下载
            video_path, info = await run_io_bound(
                self.bilibili_downloader.download_video,
                url,
                str(download_dir),
                format_id=None,
                merge=True
            )
            
            if video_path:
                print(f"Bilibili 视频下载成功: {video_path}")
                return video_path, detail_dict, video_id
            else:
                print("未找到下载的 Bilibili 视频文件")
                return None, detail_dict, video_id
                
        except Exception as e:
            print(f"下载 Bilibili 视频失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None, None, None
    
    def _extract_bilibili_video_id(self, url: str, info: Dict[str, Any]) -> str:
        """从 URL 或信息中提取 Bilibili 视频 ID"""
        import re
        # 尝试从 URL 中提取 BV 号
        bv_match = re.search(r'BV([a-zA-Z0-9]+)', url)
        if bv_match:
            return f"BV{bv_match.group(1)}"
        
        # 尝试从 URL 中提取 av 号
        av_match = re.search(r'av(\d+)', url, re.IGNORECASE)
        if av_match:
            return f"av{av_match.group(1)}"
        
        # 尝试从信息中提取
        if info:
            # 可能包含 id 字段
            video_id = info.get('id') or info.get('aid') or info.get('bvid')
            if video_id:
                return str(video_id)
        
        # 如果都提取不到，使用 URL 的哈希值
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:16]
    
    def _convert_bilibili_info_to_dict(self, info: Dict[str, Any], url: str, video_id: str) -> Dict[str, Any]:
        """将 Bilibili 视频信息转换为统一的字典格式"""
        try:
            streams = info.get('streams', {})
            # 获取第一个流的信息
            first_stream = list(streams.values())[0] if streams else {}
            
            detail_dict = {
                'id': video_id,
                'url': url,
                'platform': 'bilibili',
                'title': info.get('title', ''),
                'desc': info.get('description', '') or info.get('title', ''),
                'text_extra': [],
                'tag': [],
                'type': 'video',
                'height': first_stream.get('height', 0) if first_stream else 0,
                'width': first_stream.get('width', 0) if first_stream else 0,
                'duration': info.get('duration', ''),
                'uri': url,
                'downloads': '',
                'dynamic_cover': info.get('thumbnail', ''),
                'static_cover': info.get('thumbnail', ''),
                'uid': info.get('uploader_id', ''),
                'sec_uid': '',
                'unique_id': info.get('uploader', ''),
                'signature': '',
                'user_age': 0,
                'nickname': info.get('uploader', ''),
                'mark': '',
                'music_author': '',
                'music_title': '',
                'music_url': '',
                'digg_count': 0,
                'comment_count': 0,
                'collect_count': 0,
                'share_count': 0,
                'play_count': info.get('view_count', 0),
                'share_url': url,
                'streams': streams,
            }
            
            return detail_dict
            
        except Exception as e:
            print(f"转换 Bilibili 视频信息失败: {e}")
            return {
                'id': video_id,
                'url': url,
                'platform': 'bilibili',
                'title': info.get('title', ''),
            }
    
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
    
    async def _check_local_video(self, video_id: str, video_name: str) -> Optional[str]:
        """
        检查本地是否已有下载的视频文件
        
        Args:
            video_id: 视频ID
            video_name: 视频名称
            
        Returns:
            本地视频文件路径，如果不存在则返回 None
        """
        try:
            # 确定下载目录
            if (self.downloader and 
                hasattr(self.downloader, 'parameter') and 
                self.downloader.parameter and 
                hasattr(self.downloader.parameter, 'root') and 
                self.downloader.parameter.root):
                download_dir = Path(self.downloader.parameter.root) / "Download"
            else:
                from src.custom import PROJECT_ROOT
                download_dir = PROJECT_ROOT / "Download"
            
            if not download_dir.exists():
                return None
            
            # video_name 已经通过 generate_detail_name 处理过了，直接使用
            safe_name = video_name
            
            # 支持的视频文件扩展名
            video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm']
            
            # 如果启用了文件夹模式，在文件夹内查找
            if (self.downloader and 
                hasattr(self.downloader, 'parameter') and 
                self.downloader.parameter and 
                hasattr(self.downloader.parameter, 'folder_mode') and 
                self.downloader.parameter.folder_mode):
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
            
        except Exception as e:
            print(f"检查本地视频文件失败: {e}")
            return None
    
    async def _check_local_bilibili_video(self, video_id: str, title: str, download_dir: Path) -> Optional[str]:
        """
        检查本地是否已有下载的 Bilibili 视频文件
        
        Args:
            video_id: 视频ID
            title: 视频标题
            download_dir: 下载目录
            
        Returns:
            本地视频文件路径，如果不存在则返回 None
        """
        try:
            if not download_dir.exists():
                return None
            
            # 清理标题中的非法字符
            safe_title = self._sanitize_bilibili_filename(title) if title else video_id
            
            # 支持的视频文件扩展名
            video_extensions = ['.mp4', '.flv', '.webm', '.mkv', '.mov', '.avi']
            
            # 首先尝试精确匹配标题
            for ext in video_extensions:
                video_file = download_dir / f"{safe_title}{ext}"
                if video_file.exists() and video_file.is_file():
                    return str(video_file.resolve())
            
            # 如果找不到，列出目录中的所有视频文件，选择最新的
            video_files = []
            for video_file in download_dir.glob('*'):
                if video_file.is_file() and video_file.suffix.lower() in video_extensions:
                    video_files.append((video_file.stat().st_mtime, video_file))
            
            if video_files:
                # 按修改时间排序，返回最新的
                video_files.sort(key=lambda x: x[0], reverse=True)
                return str(video_files[0][1].resolve())
            
            return None
            
        except Exception as e:
            print(f"检查本地 Bilibili 视频文件失败: {e}")
            return None
    
    def _sanitize_bilibili_filename(self, filename: str) -> str:
        """清理 Bilibili 文件名中的非法字符"""
        import re
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除前后空格和点
        filename = filename.strip(' .')
        # 限制文件名长度
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    async def _find_downloaded_video(self, video_name: str) -> Optional[str]:
        """查找已下载的视频文件（保持向后兼容）"""
        try:
            # 确定下载目录
            if (self.downloader and 
                hasattr(self.downloader, 'parameter') and 
                self.downloader.parameter and 
                hasattr(self.downloader.parameter, 'root') and 
                self.downloader.parameter.root):
                download_dir = Path(self.downloader.parameter.root) / "Download"
            else:
                from src.custom import PROJECT_ROOT
                download_dir = PROJECT_ROOT / "Download"
            
            if not download_dir.exists():
                return None
            
            # video_name 已经通过 generate_detail_name 处理过了，直接使用
            safe_name = video_name
            
            # 支持的视频文件扩展名
            video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.webm']
            
            # 如果启用了文件夹模式，在文件夹内查找
            if (self.downloader and 
                hasattr(self.downloader, 'parameter') and 
                self.downloader.parameter and 
                hasattr(self.downloader.parameter, 'folder_mode') and 
                self.downloader.parameter.folder_mode):
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
            
        except Exception as e:
            print(f"查找下载的视频文件失败: {e}")
            return None

