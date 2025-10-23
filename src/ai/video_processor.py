"""
视频处理模块
负责视频下载、平台检测、视频文件查找等功能
"""

import os
from pathlib import Path
from typing import Optional, Tuple, List
import asyncio

from src.application import TikTokDownloader
from src.application.main_terminal import TikTok


class VideoProcessor:
    """视频处理器"""
    
    def __init__(self, downloader: TikTokDownloader):
        self.downloader = downloader
        self.tiktok_instance = None
    
    def detect_platform(self, url: str) -> str:
        """检测URL所属平台"""
        url_lower = url.lower()
        if 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'douyin.com' in url_lower:
            return 'douyin'
        else:
            return 'douyin'  # 默认抖音
    
    async def download_video(self, url: str, output_dir: Optional[str] = None, 
                           force_download: bool = False) -> Tuple[Optional[str], Optional[List]]:
        """下载视频并返回视频文件路径和详情数据"""
        try:
            print(f"开始下载视频: {url}")
            
            # 检测平台
            platform = self.detect_platform(url)
            print(f"检测到平台: {platform}")
            
            # 初始化设置
            self.downloader.project_info()
            self.downloader.check_config()
            await self.downloader.check_settings(False)
            
            # 设置输出目录
            if output_dir:
                self.downloader.parameter.root = Path(output_dir)
                print(f"输出目录: {output_dir}")
            
            # 创建TikTok实例
            self.tiktok_instance = TikTok(
                self.downloader.parameter, 
                self.downloader.database
            )
            
            # 提取视频ID
            if platform == 'tiktok':
                ids = await self.tiktok_instance.links_tiktok.run(url)
            else:
                ids = await self.tiktok_instance.links.run(url)
            
            if not ids:
                raise Exception(f"无法从URL提取视频ID: {url}")
            
            print(f"提取到视频ID: {ids}")
            
            # 创建记录器并获取视频详情
            root, params, logger = self.tiktok_instance.record.run(self.downloader.parameter)
            async with logger(root, console=self.downloader.console, **params) as record:
                detail_data = await self.tiktok_instance._handle_detail(ids, platform == 'tiktok', record, api=True)
            
            # 从detail_data中提取视频名称
            video_name = self._get_video_name_from_detail_data(detail_data, ids)
            
            # 检查视频是否已经下载过（除非强制下载）
            if not force_download and await self._is_video_downloaded(ids):
                print(f"视频 {ids} 已经下载过，跳过下载步骤")
                # 查找已下载的视频文件
                video_path = await self._find_downloaded_video(ids, platform == 'tiktok', video_name)
                if video_path:
                    print(f"找到已下载的视频: {video_path}")
                    return video_path, detail_data
                else:
                    print("警告: 数据库中记录已下载，但未找到视频文件")
            
            # 首先尝试查找已下载的视频文件（除非强制下载）
            if not force_download:
                video_path = await self._find_downloaded_video(ids, platform == 'tiktok', video_name)
                if video_path:
                    print(f"视频下载成功: {video_path}")
                    return video_path, detail_data
            else:
                print("强制下载模式：忽略已存在的视频文件")
            
            # 如果没找到文件，使用正常的下载流程
            if detail_data and len(detail_data) > 0:
                print(f"获取到detail_data，长度: {len(detail_data)}")
                
                # 如果是强制下载模式，先清理已存在的文件和记录
                if force_download:
                    print("强制下载模式：清理已存在的文件和记录...")
                    await self._clean_existing_files_and_records(ids, platform == 'tiktok', video_name)
                
                # 使用正常的下载流程
                print("使用正常的下载流程下载视频...")
                await self.tiktok_instance.downloader.run(detail_data, "detail", tiktok=(platform == 'tiktok'))
                
                # 下载完成后，再次查找视频文件
                # 先列出下载目录中的所有文件，用于调试
                download_dir = Path(self.downloader.parameter.root) / "Download"
                print(f"下载目录: {download_dir}")
                if download_dir.exists():
                    print("下载目录中的文件:")
                    for file_path in download_dir.rglob("*"):
                        if file_path.is_file():
                            print(f"  - {file_path}")
                
                video_path = await self._find_downloaded_video(ids, platform == 'tiktok', video_name)
                if video_path:
                    print(f"视频下载成功: {video_path}")
                    return video_path, detail_data
                else:
                    print("下载完成但未找到视频文件")
            else:
                print("detail_data为空或长度为0")
            
            raise Exception("未找到下载的视频文件")
            
        except Exception as e:
            print(f"下载视频失败: {str(e)}")
            return None, None
    
    async def _is_video_downloaded(self, ids) -> bool:
        """检查视频是否已经在数据库中记录为已下载"""
        try:
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            return await self.downloader.database.has_download_data(video_id)
        except Exception as e:
            print(f"检查下载记录失败: {str(e)}")
            return False
    
    def _get_video_name_from_detail_data(self, detail_data: List, ids) -> str:
        """从detail_data中提取视频名称，使用与download.py相同的命名规则"""
        try:
            if detail_data and len(detail_data) > 0:
                video_data = detail_data[0]
                if isinstance(video_data, dict):
                    # 使用与download.py相同的命名逻辑
                    name = self._generate_detail_name(video_data)
                    print(f"使用name_format生成视频名称: {name}")
                    return name
                else:
                    print(f"detail_data[0] 不是字典格式: {type(video_data)}")
                    # 确保ids是字符串
                    video_id = ids[0] if isinstance(ids, list) else ids
                    return video_id
            else:
                print("detail_data为空")
                # 确保ids是字符串
                video_id = ids[0] if isinstance(ids, list) else ids
                return video_id
        except Exception as e:
            print(f"提取视频名称失败: {str(e)}")
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            return video_id
    
    def _generate_detail_name(self, data: dict) -> str:
        """生成作品文件名称，使用与download.py相同的逻辑"""
        try:
            # 获取name_format配置
            name_format = self.downloader.parameter.name_format
            split = self.downloader.parameter.split
            name_length = self.downloader.parameter.name_length
            
            print(f"name_format: {name_format}")
            print(f"split: {split}")
            print(f"name_length: {name_length}")
            
            # 根据name_format生成名称
            name_parts = []
            for field in name_format:
                if field in data:
                    value = str(data[field])
                    # 如果是create_time，需要格式化
                    if field == "create_time" and value:
                        try:
                            from datetime import datetime
                            # 假设create_time是时间戳
                            if value.isdigit():
                                dt = datetime.fromtimestamp(int(value))
                                value = dt.strftime(self.downloader.parameter.date_format)
                        except:
                            pass
                    name_parts.append(value)
                else:
                    print(f"字段 {field} 不存在于数据中")
            
            # 使用split连接
            name = split.join(name_parts)
            
            # 使用cleaner过滤名称
            name = self.downloader.parameter.CLEANER.filter_name(name, data.get("id", ""))
            
            # 使用beautify_string处理
            from src.tools import beautify_string
            name = beautify_string(name, name_length)
            
            print(f"生成的视频名称: {name}")
            return name
            
        except Exception as e:
            print(f"生成视频名称失败: {str(e)}")
            return data.get("id", "unknown")
    
    async def _clean_existing_files_and_records(self, ids, is_tiktok: bool = False, video_name: str = None):
        """清理已存在的文件和数据库记录"""
        try:
            print(f"清理视频 {ids} 的已存在文件和记录...")
            
            # 1. 删除数据库记录
            try:
                # 确保ids是字符串
                video_id = ids[0] if isinstance(ids, list) else ids
                await self.downloader.database.delete_download_data(video_id)
                print(f"已删除数据库记录: {video_id}")
            except Exception as e:
                print(f"删除数据库记录失败: {str(e)}")
            
            # 2. 删除已存在的视频文件
            video_path = await self._find_downloaded_video(ids, is_tiktok, video_name)
            if video_path:
                try:
                    os.remove(video_path)
                    print(f"已删除视频文件: {video_path}")
                except Exception as e:
                    print(f"删除视频文件失败: {str(e)}")
            
            # 3. 删除相关的音频和文本文件
            download_dir = Path(self.downloader.parameter.root) / "Download"
            
            # 如果有视频名称，优先按名称清理
            if video_name:
                video_folder = download_dir / video_name
                if video_folder.exists():
                    try:
                        # 删除文件夹中的所有文件
                        for file_path in video_folder.iterdir():
                            if file_path.is_file():
                                file_path.unlink()
                                print(f"已删除文件: {file_path}")
                        
                        # 删除空文件夹
                        if not any(video_folder.iterdir()):
                            video_folder.rmdir()
                            print(f"已删除空文件夹: {video_folder}")
                    except Exception as e:
                        print(f"清理文件夹失败: {str(e)}")
            
            # 4. 也尝试按ID清理（兼容旧文件）
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            video_folder_by_id = download_dir / video_id
            if video_folder_by_id.exists():
                try:
                    # 删除文件夹中的所有文件
                    for file_path in video_folder_by_id.iterdir():
                        if file_path.is_file():
                            file_path.unlink()
                            print(f"已删除文件: {file_path}")
                    
                    # 删除空文件夹
                    if not any(video_folder_by_id.iterdir()):
                        video_folder_by_id.rmdir()
                        print(f"已删除空文件夹: {video_folder_by_id}")
                except Exception as e:
                    print(f"清理文件夹失败: {str(e)}")
            
            print("清理完成")
            
        except Exception as e:
            print(f"清理文件和记录失败: {str(e)}")
    
    async def _find_downloaded_video(self, ids, is_tiktok: bool = False, video_name: str = None) -> Optional[str]:
        """查找已下载的视频文件"""
        try:
            # 获取下载目录
            download_dir = Path(self.downloader.parameter.root) / "Download"
            
            # 如果有视频名称，优先按名称查找
            if video_name:
                print(f"按视频名称查找: {video_name}")
                
                # 根据folder_mode决定查找位置
                if self.downloader.parameter.folder_mode:
                    # 文件夹模式：在子文件夹中查找
                    video_folder = download_dir / video_name
                    if video_folder.exists():
                        video_patterns = [
                            f"{video_name}.mp4",
                            f"{video_name}.mov",
                            f"{video_name}.avi"
                        ]
                        
                        for pattern in video_patterns:
                            video_file = video_folder / pattern
                            if video_file.exists() and video_file.stat().st_size > 0:
                                print(f"在文件夹中找到视频文件: {video_file}")
                                return str(video_file)
                    
                    # 也尝试查找文件夹中的其他视频文件
                    for video_file in video_folder.glob("*.mp4"):
                        if video_file.exists() and video_file.stat().st_size > 0:
                            print(f"在文件夹中找到视频文件: {video_file}")
                            return str(video_file)
                else:
                    # 非文件夹模式：直接在下载目录中查找
                    video_patterns = [
                        f"{video_name}.mp4",
                        f"{video_name}.mov",
                        f"{video_name}.avi",
                        f"*{video_name}*.mp4",
                        f"*{video_name}*.mov",
                        f"*{video_name}*.avi"
                    ]
                    
                    for pattern in video_patterns:
                        for video_file in download_dir.glob(pattern):
                            if video_file.exists() and video_file.stat().st_size > 0:
                                print(f"找到视频文件: {video_file}")
                                return str(video_file)
            
            # 如果按名称没找到，尝试按ID查找
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            print(f"按视频ID查找: {video_id}")
            video_patterns = [
                f"*{video_id}*.mp4",
                f"*{video_id}*.mov",
                f"*{video_id}*.avi"
            ]
            
            # 在下载目录中查找视频文件
            for pattern in video_patterns:
                for video_file in download_dir.glob(pattern):
                    if video_file.exists() and video_file.stat().st_size > 0:
                        print(f"找到视频文件: {video_file}")
                        return str(video_file)
            
            # 如果还是没找到，尝试查找最近下载的文件
            print("查找最近下载的视频文件...")
            video_files = []
            for ext in ['*.mp4', '*.mov', '*.avi']:
                video_files.extend(download_dir.glob(ext))
            
            if video_files:
                # 按修改时间排序，返回最新的
                latest_file = max(video_files, key=lambda f: f.stat().st_mtime)
                if latest_file.stat().st_size > 0:
                    print(f"找到最新视频文件: {latest_file}")
                    return str(latest_file)
            
            print("未找到视频文件")
            return None
            
        except Exception as e:
            print(f"查找视频文件失败: {str(e)}")
            return None
    
    def _get_video_folder_path(self, video_name: str) -> Path:
        """获取视频文件夹路径，根据folder_mode配置决定是否创建子文件夹"""
        download_dir = Path(self.downloader.parameter.root) / "Download"
        
        if self.downloader.parameter.folder_mode:
            # 文件夹模式：为每个视频创建子文件夹
            video_folder = download_dir / video_name
            video_folder.mkdir(parents=True, exist_ok=True)
            return video_folder
        else:
            # 非文件夹模式：直接在下载目录中
            download_dir.mkdir(parents=True, exist_ok=True)
            return download_dir
