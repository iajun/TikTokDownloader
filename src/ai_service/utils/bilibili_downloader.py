"""
Bilibili 视频下载器
使用 you-get 库下载 Bilibili 视频
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import shutil


class BilibiliDownloader:
    """Bilibili 视频下载器"""
    
    def __init__(self, cookies: Optional[str] = None):
        """
        初始化 Bilibili 下载器
        
        Args:
            cookies: Cookie 文件路径或 Cookie 内容字符串
        """
        # 检查 you-get 是否安装
        self.you_get_cmd = shutil.which('you-get')
        if not self.you_get_cmd:
            # 尝试使用 python -m you_get
            try:
                import sys
                result = subprocess.run(
                    [sys.executable, '-m', 'you_get', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.you_get_cmd = [sys.executable, '-m', 'you_get']
                else:
                    raise ImportError("you-get is not installed. Please install it with: pip install you-get")
            except Exception:
                raise ImportError("you-get is not installed. Please install it with: pip install you-get")
        
        self.cookies = cookies
        self.cookies_file = None
        self._temp_cookies_file = False
        
        # 如果 cookies 是字符串内容，创建临时文件
        if cookies:
            if os.path.exists(cookies):
                # 如果是文件路径
                self.cookies_file = cookies
            else:
                # 如果是 Cookie 内容字符串，创建临时文件
                self._create_temp_cookies_file(cookies)
    
    def _create_temp_cookies_file(self, cookies_content: str):
        """创建临时 Cookie 文件"""
        try:
            # 创建临时文件
            temp_dir = Path(tempfile.gettempdir()) / "ai_service_bilibili"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            self.cookies_file = temp_dir / "cookies.txt"
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            self._temp_cookies_file = True
        except Exception as e:
            print(f"创建临时 Cookie 文件失败: {e}")
            self.cookies_file = None
    
    def extract_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        提取视频信息（不下载）
        
        Args:
            url: Bilibili 视频 URL
            
        Returns:
            视频信息字典，包含 title, site, streams 等信息
        """
        try:
            # 首先尝试使用 --json 参数（不使用 --info，因为两者不能同时使用）
            # 使用 --json 时，you-get 会自动只显示信息而不下载
            cmd = self._build_cmd(url, info_only=False, json_output=True)
            
            # 执行命令并捕获输出
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0 and result.stdout:
                try:
                    # you-get 的 JSON 输出可能包含调试信息，需要提取 JSON 部分
                    output = result.stdout.strip()
                    
                    # 尝试找到 JSON 部分（可能包含在多行输出中）
                    json_start = output.find('{')
                    if json_start == -1:
                        # 如果没有找到 {，尝试从 stderr 中查找（某些版本可能输出到 stderr）
                        if result.stderr:
                            output = result.stderr.strip()
                            json_start = output.find('{')
                    
                    if json_start >= 0:
                        # 找到最后一个 }，确保提取完整的 JSON
                        json_end = output.rfind('}') + 1
                        if json_end > json_start:
                            json_str = output[json_start:json_end]
                            try:
                                return json.loads(json_str)
                            except json.JSONDecodeError:
                                # 如果解析失败，尝试修复常见的 JSON 问题
                                # 移除可能的尾随逗号
                                json_str = json_str.rstrip().rstrip(',')
                                if json_str.endswith('}'):
                                    try:
                                        return json.loads(json_str)
                                    except json.JSONDecodeError:
                                        pass
                    
                    # 如果整个输出都是 JSON（尝试直接解析）
                    try:
                        return json.loads(output)
                    except json.JSONDecodeError:
                        pass
                    
                    print(f"无法解析 JSON 输出，输出内容: {output[:500]}")
                    return None
                    
                except json.JSONDecodeError as e:
                    print(f"解析 JSON 输出失败: {e}")
                    print(f"输出内容: {result.stdout[:500]}")
                    if result.stderr:
                        print(f"错误输出: {result.stderr[:500]}")
                    return None
            else:
                # 如果命令失败，尝试不使用 --json 参数，解析文本输出
                if result.returncode != 0:
                    error_msg = result.stderr or result.stdout or ''
                    # 检查是否是参数冲突错误
                    if 'not allowed with argument' in error_msg or '--json' in error_msg:
                        print(f"--json 参数不可用，回退到文本解析")
                        return self._extract_info_from_text(url)
                    else:
                        print(f"获取视频信息失败 (code {result.returncode}): {error_msg[:200]}")
                        # 仍然尝试文本解析作为备用
                        return self._extract_info_from_text(url)
                return None
                
        except subprocess.TimeoutExpired:
            print("获取视频信息超时")
            return None
        except Exception as e:
            print(f"提取视频信息失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_info_from_text(self, url: str) -> Optional[Dict[str, Any]]:
        """
        从文本输出中提取视频信息（备用方法）
        
        Args:
            url: Bilibili 视频 URL
            
        Returns:
            视频信息字典
        """
        try:
            # 构建命令，不使用 --json 参数
            cmd = self._build_cmd(url, info_only=True, json_output=False)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0 and result.stdout:
                # 解析文本输出
                lines = result.stdout.strip().split('\n')
                info = {
                    'site': 'Bilibili',
                    'title': '',
                    'streams': {}
                }
                
                current_stream = None
                for line in lines:
                    line = line.strip()
                    if line.startswith('site:'):
                        info['site'] = line.split(':', 1)[1].strip()
                    elif line.startswith('title:'):
                        info['title'] = line.split(':', 1)[1].strip()
                    elif line.startswith('- format:'):
                        # 开始新的流信息
                        format_id = line.split(':', 1)[1].strip()
                        current_stream = {
                            'format': format_id,
                            'container': '',
                            'quality': '',
                            'size': ''
                        }
                    elif line.startswith('container:') and current_stream:
                        current_stream['container'] = line.split(':', 1)[1].strip()
                    elif line.startswith('quality:') and current_stream:
                        current_stream['quality'] = line.split(':', 1)[1].strip()
                    elif line.startswith('size:') and current_stream:
                        size_str = line.split(':', 1)[1].strip()
                        current_stream['size'] = size_str
                        # 保存流信息
                        if current_stream.get('format'):
                            info['streams'][current_stream['format']] = current_stream
                            current_stream = None
                
                if info.get('title'):
                    return info
                    
            return None
            
        except Exception as e:
            print(f"从文本提取信息失败: {e}")
            return None
    
    def download_video(
        self,
        url: str,
        output_dir: str,
        format_id: Optional[str] = None,
        merge: bool = True
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        下载 Bilibili 视频
        
        Args:
            url: Bilibili 视频 URL
            output_dir: 输出目录
            format_id: 格式 ID（如 'dash-flv480-AVC'）
            merge: 是否合并视频片段
            
        Returns:
            (视频文件路径, 视频信息字典)
        """
        try:
            # 确保输出目录存在
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 先获取视频信息
            info = self.extract_video_info(url)
            if not info:
                print("无法获取视频信息")
                return None, None
            
            title = info.get('title', '')
            if not title:
                # 尝试从 streams 中获取
                streams = info.get('streams', {})
                if streams:
                    first_stream = list(streams.values())[0] if streams else {}
                    title = first_stream.get('title', '')
            
            safe_title = self._sanitize_filename(title) if title else 'video'
            
            # 构建下载命令
            cmd = self._build_cmd(
                url,
                output_dir=str(output_path),
                format_id=format_id,
                merge=merge
            )
            
            # 执行下载命令
            print(f"开始下载视频: {url}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟超时
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode != 0:
                print(f"下载失败: {result.stderr}")
                return None, info
            
            # 查找下载的视频文件
            video_path = self._find_downloaded_video(output_path, safe_title)
            
            if video_path:
                print(f"视频下载成功: {video_path}")
                return video_path, info
            else:
                print("未找到下载的视频文件")
                return None, info
            
        except subprocess.TimeoutExpired:
            print("下载视频超时")
            return None, None
        except Exception as e:
            print(f"下载视频失败: {e}")
            import traceback
            traceback.print_exc()
            return None, None
    
    def _build_cmd(
        self,
        url: str,
        output_dir: Optional[str] = None,
        format_id: Optional[str] = None,
        merge: bool = True,
        info_only: bool = False,
        json_output: bool = False
    ) -> list:
        """构建 you-get 命令"""
        if isinstance(self.you_get_cmd, str):
            cmd = [self.you_get_cmd]
        else:
            cmd = list(self.you_get_cmd)
        
        if json_output:
            cmd.append('--json')
        
        if info_only:
            cmd.append('--info')
        
        if self.cookies_file:
            cmd.extend(['--cookies', str(self.cookies_file)])
        
        if output_dir:
            cmd.extend(['-o', output_dir])
        
        if format_id:
            cmd.extend(['--format', format_id])
        
        if not merge:
            cmd.append('--no-merge')
        
        cmd.append(url)
        
        return cmd
    
    def _find_downloaded_video(self, output_dir: Path, title: str) -> Optional[str]:
        """
        查找已下载的视频文件
        
        Args:
            output_dir: 输出目录
            title: 视频标题（已清理）
            
        Returns:
            视频文件路径
        """
        try:
            # 查找视频文件
            video_extensions = ['.mp4', '.flv', '.webm', '.mkv', '.mov', '.avi']
            
            # 首先尝试精确匹配标题
            for ext in video_extensions:
                video_file = output_dir / f"{title}{ext}"
                if video_file.exists():
                    return str(video_file.resolve())
            
            # 如果找不到，列出目录中的所有视频文件，选择最新的
            video_files = []
            for video_file in output_dir.glob('*'):
                if video_file.is_file() and video_file.suffix.lower() in video_extensions:
                    video_files.append((video_file.stat().st_mtime, video_file))
            
            if video_files:
                # 按修改时间排序，返回最新的
                video_files.sort(key=lambda x: x[0], reverse=True)
                return str(video_files[0][1].resolve())
            
            return None
            
        except Exception as e:
            print(f"查找下载的视频文件失败: {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        import re
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除前后空格和点
        filename = filename.strip(' .')
        # 限制文件名长度
        if len(filename) > 200:
            filename = filename[:200]
        return filename
    
    def __del__(self):
        """清理临时文件"""
        if self._temp_cookies_file and self.cookies_file and os.path.exists(self.cookies_file):
            try:
                os.remove(self.cookies_file)
            except Exception:
                pass

