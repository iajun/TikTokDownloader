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
            
            # 在Web应用环境中，跳过数据库检查，直接检查文件是否存在
            print("跳过数据库检查，直接检查文件是否存在")
            return False
                
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
        """生成作品文件名称，使用与download.py完全相同的命名规则"""
        try:
            # 使用与download.py完全相同的逻辑
            from src.tools import beautify_string
            
            name = beautify_string(
                self.downloader.parameter.CLEANER.filter_name(
                    self.downloader.parameter.split.join(data[i] for i in self.downloader.parameter.name_format),
                    data["id"],
                ),
                length=self.downloader.parameter.name_length,
            )
            
            print(f"生成的视频名称: {name}")
            return name
            
        except Exception as e:
            print(f"生成视频名称失败: {str(e)}")
            return data.get("id", "unknown")
    
    async def _clean_existing_files_and_records(self, ids, is_tiktok: bool = False, video_name: str = None):
        """清理已存在的文件和数据库记录"""
        try:
            print(f"清理视频 {ids} 的已存在文件和记录...")
            
            # 1. 跳过数据库记录删除（Web应用不需要数据库）
            print("跳过数据库记录删除")
            
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
        """查找已下载的视频文件，使用与download.py相同的路径逻辑"""
        try:
            # 获取下载目录
            download_dir = Path(self.downloader.parameter.root) / "Download"
            print(f"查找目录: {download_dir}")
            
            # 如果有视频名称，优先按名称查找
            if video_name:
                print(f"按视频名称查找: {video_name}")
                
                # 使用与download.py相同的路径逻辑
                # 根据folder_mode决定查找位置
                if self.downloader.parameter.folder_mode:
                    # 文件夹模式：文件路径是 root/name/name.mp4
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
                    # 非文件夹模式：文件路径是 root/name.mp4
                    # 处理特殊字符和长文件名
                    safe_video_name = self._make_filename_safe(video_name)
                    print(f"安全文件名: {safe_video_name}")
                    
                    video_patterns = [
                        f"{safe_video_name}.mp4",
                        f"{safe_video_name}.mov",
                        f"{safe_video_name}.avi"
                    ]
                    
                    for pattern in video_patterns:
                        video_file = download_dir / pattern
                        if video_file.exists() and video_file.stat().st_size > 0:
                            print(f"找到视频文件: {video_file}")
                            return str(video_file)
                    
                    # 如果安全文件名没找到，尝试原始文件名
                    print("安全文件名匹配失败，尝试原始文件名...")
                    video_patterns = [
                        f"{video_name}.mp4",
                        f"{video_name}.mov",
                        f"{video_name}.avi"
                    ]
                    
                    for pattern in video_patterns:
                        video_file = download_dir / pattern
                        if video_file.exists() and video_file.stat().st_size > 0:
                            print(f"找到视频文件: {video_file}")
                            return str(video_file)
                    
                    # 如果原始文件名也没找到，尝试beautify_string处理后的文件名
                    print("原始文件名匹配失败，尝试beautify_string处理后的文件名...")
                    from src.tools import beautify_string
                    
                    # 尝试不同的长度限制
                    for length in [50, 64, 128]:
                        beautified_name = beautify_string(video_name, length)
                        print(f"beautify_string处理后的文件名 (长度{length}): {beautified_name}")
                        
                        video_patterns = [
                            f"{beautified_name}.mp4",
                            f"{beautified_name}.mov",
                            f"{beautified_name}.avi"
                        ]
                        
                        for pattern in video_patterns:
                            video_file = download_dir / pattern
                            if video_file.exists() and video_file.stat().st_size > 0:
                                print(f"找到视频文件: {video_file}")
                                return str(video_file)
                    
                    # 如果beautify_string也没找到，尝试手动截断匹配
                    print("beautify_string匹配失败，尝试手动截断匹配...")
                    video_files = list(download_dir.glob("*.mp4")) + list(download_dir.glob("*.mov")) + list(download_dir.glob("*.avi"))
                    
                    for video_file in video_files:
                        if video_file.exists() and video_file.stat().st_size > 0:
                            file_stem = video_file.stem
                            print(f"检查文件: {file_stem}")
                            
                            # 检查是否包含视频名称的主要部分
                            if self._is_partial_match(file_stem, video_name):
                                print(f"部分匹配成功，找到视频文件: {video_file}")
                                return str(video_file)
            
            # 如果按名称没找到，尝试按ID查找
            # 确保ids是字符串
            video_id = ids[0] if isinstance(ids, list) else ids
            print(f"按视频ID查找: {video_id}")
            
            # 在下载目录中递归查找包含ID的视频文件
            video_extensions = ["*.mp4", "*.mov", "*.avi"]
            for ext in video_extensions:
                for video_file in download_dir.rglob(ext):
                    if video_file.exists() and video_file.stat().st_size > 0:
                        # 检查文件名是否包含视频ID
                        if video_id in video_file.name:
                            print(f"找到视频文件: {video_file}")
                            return str(video_file)
            
            # 最后尝试：列出所有视频文件进行调试
            print("所有视频文件列表:")
            all_video_files = []
            for ext in video_extensions:
                all_video_files.extend(download_dir.glob(ext))
            
            for video_file in all_video_files:
                if video_file.exists() and video_file.stat().st_size > 0:
                    print(f"  - {video_file.name}")
            
            print("未找到视频文件")
            return None
            
        except Exception as e:
            print(f"查找视频文件失败: {str(e)}")
            return None
    
    def _make_filename_safe(self, filename: str) -> str:
        """将文件名转换为安全的文件名，支持特殊字符"""
        try:
            import re
            
            # 保留中文字符、英文字母、数字、连字符、下划线、空格
            # 移除或替换其他特殊字符
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            # 移除连续的下划线
            safe_name = re.sub(r'_+', '_', safe_name)
            
            # 移除开头和结尾的下划线
            safe_name = safe_name.strip('_')
            
            # 限制文件名长度（Windows限制为255字符，我们保守一点用200）
            if len(safe_name) > 200:
                safe_name = safe_name[:200]
            
            return safe_name
            
        except Exception as e:
            print(f"文件名安全处理失败: {str(e)}")
            return filename
    
    def _is_partial_match(self, file_stem: str, video_name: str) -> bool:
        """检查文件名是否部分匹配视频名称"""
        try:
            # 检查文件名是否包含视频名称的主要部分
            # 取视频名称的前30个字符进行匹配
            name_prefix = video_name[:30]
            
            # 检查文件名是否以这个前缀开始
            if file_stem.startswith(name_prefix):
                return True
            
            # 检查文件名是否包含视频名称的主要关键词
            # 提取关键词（去除特殊字符）
            import re
            keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z0-9]+', video_name)
            
            # 检查是否包含足够多的关键词
            matched_keywords = 0
            for keyword in keywords:
                if len(keyword) >= 2 and keyword in file_stem:
                    matched_keywords += 1
            
            # 如果匹配的关键词数量超过一半，认为匹配
            return matched_keywords >= len(keywords) // 2
            
        except Exception as e:
            print(f"部分匹配检查失败: {str(e)}")
            return False
    
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
