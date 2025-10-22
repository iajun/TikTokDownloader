#!/usr/bin/env python3
"""
TikTokDownloader 命令行下载工具
支持直接通过命令行下载抖音/TikTok视频

使用方法:
    python cli_downloader.py <URL>                    # 下载单个视频
    python cli_downloader.py --batch <file>            # 批量下载
    python cli_downloader.py --help                    # 显示帮助
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.application import TikTokDownloader
from src.application.main_terminal import TikTok


class CLIDownloader:
    """命令行下载器"""
    
    def __init__(self):
        self.downloader = None
        self.tiktok_instance = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.downloader = TikTokDownloader()
        await self.downloader.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.downloader:
            await self.downloader.__aexit__(exc_type, exc_val, exc_tb)
    
    def detect_platform(self, url: str) -> str:
        """检测URL所属平台"""
        url_lower = url.lower()
        if 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'douyin.com' in url_lower:
            return 'douyin'
        else:
            # 默认尝试抖音
            return 'douyin'
    
    async def download_single(self, url: str, platform: Optional[str] = None, 
                            output_dir: Optional[str] = None, 
                            cookie_file: Optional[str] = None,
                            proxy: Optional[str] = None) -> bool:
        """下载单个视频"""
        try:
            # 检测平台
            if not platform:
                platform = self.detect_platform(url)
            
            print(f"检测到平台: {platform}")
            print(f"开始下载: {url}")
            
            # 初始化设置
            self.downloader.project_info()
            self.downloader.check_config()
            await self.downloader.check_settings(False)
            
            # 如果指定了输出目录，更新设置
            if output_dir:
                self.downloader.parameter.root = output_dir
                print(f"输出目录: {output_dir}")
                
            # 如果指定了代理，更新设置
            if proxy:
                self.downloader.parameter.proxy = proxy
                print(f"使用代理: {proxy}")
                
            # 如果指定了Cookie文件，读取Cookie
            if cookie_file:
                await self._load_cookie_from_file(cookie_file, platform == 'tiktok')
                await self.downloader.check_settings()
                print(f"已加载Cookie文件: {cookie_file}")
            
            # 创建TikTok实例
            self.tiktok_instance = TikTok(
                self.downloader.parameter, 
                self.downloader.database
            )
            
            # 执行下载
            if platform == 'tiktok':
                await self._download_tiktok_url(url)
            else:
                await self._download_douyin_url(url)
            
            print("下载完成!")
            return True
                
        except Exception as e:
            print(f"下载失败: {str(e)}")
            return False
    
    async def download_batch(self, file_path: str, platform: Optional[str] = None,
                           output_dir: Optional[str] = None,
                           cookie_file: Optional[str] = None,
                           proxy: Optional[str] = None) -> bool:
        """批量下载视频"""
        try:
            # 读取文件中的链接
            with open(file_path, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            if not urls:
                print("文件中没有找到有效的链接")
                return False
                
            print(f"找到 {len(urls)} 个链接，开始批量下载...")
            
            # 初始化设置
            self.downloader.project_info()
            self.downloader.check_config()
            await self.downloader.check_settings(False)
            
            # 如果指定了输出目录，更新设置
            if output_dir:
                self.downloader.parameter.root = output_dir
                print(f"输出目录: {output_dir}")
                
            # 如果指定了代理，更新设置
            if proxy:
                self.downloader.parameter.proxy = proxy
                print(f"使用代理: {proxy}")
                
            # 如果指定了Cookie文件，读取Cookie
            if cookie_file:
                await self._load_cookie_from_file(cookie_file, platform == 'tiktok')
                await self.downloader.check_settings()
                print(f"已加载Cookie文件: {cookie_file}")
            
            # 创建TikTok实例
            self.tiktok_instance = TikTok(
                self.downloader.parameter, 
                self.downloader.database
            )
            
            # 批量下载
            success_count = 0
            for i, url in enumerate(urls, 1):
                print(f"\n正在下载第 {i}/{len(urls)} 个视频: {url}")
                
                # 检测平台类型
                current_platform = platform or self.detect_platform(url)
                
                try:
                    if current_platform == 'tiktok':
                        await self._download_tiktok_url(url)
                    else:
                        await self._download_douyin_url(url)
                    success_count += 1
                    print(f"✓ 第 {i} 个视频下载成功")
                except Exception as e:
                    print(f"✗ 第 {i} 个视频下载失败: {str(e)}")
                    
            print(f"\n批量下载完成，成功 {success_count}/{len(urls)} 个")
            return True
            
        except FileNotFoundError:
            print(f"文件不存在: {file_path}")
            return False
        except Exception as e:
            print(f"批量下载失败: {str(e)}")
            return False
    
    async def _load_cookie_from_file(self, cookie_file: str, is_tiktok: bool = False):
        """从文件加载Cookie"""
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                cookie_content = f.read().strip()
            
            if is_tiktok:
                self.downloader.cookie.extract(cookie_content, platform="TikTok")
            else:
                self.downloader.cookie.extract(cookie_content, platform="抖音")
                
            print("Cookie加载成功")
        except Exception as e:
            print(f"加载Cookie失败: {str(e)}")
            raise
    
    async def _download_tiktok_url(self, url: str):
        """下载TikTok视频"""
        # 提取视频ID
        ids = await self.tiktok_instance.links_tiktok.run(url)
        if not ids:
            raise Exception(f"无法从URL提取视频ID: {url}")
        
        print(f"提取到视频ID: {ids}")
        
        # 创建记录器
        root, params, logger = self.tiktok_instance.record.run(self.downloader.parameter)
        async with logger(root, console=self.downloader.console, **params) as record:
            # 下载视频
            await self.tiktok_instance._handle_detail(ids, True, record)
    
    async def _download_douyin_url(self, url: str):
        """下载抖音视频"""
        # 提取视频ID
        ids = await self.tiktok_instance.links.run(url)
        if not ids:
            raise Exception(f"无法从URL提取视频ID: {url}")
        
        print(f"提取到视频ID: {ids}")
        
        # 创建记录器
        root, params, logger = self.tiktok_instance.record.run(self.downloader.parameter)
        async with logger(root, console=self.downloader.console, **params) as record:
            # 下载视频
            await self.tiktok_instance._handle_detail(ids, False, record)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="TikTokDownloader 命令行下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python cli_downloader.py https://v.douyin.com/xxxxx         # 下载抖音视频
  python cli_downloader.py https://www.tiktok.com/@user/video/xxxxx  # 下载TikTok视频
  python cli_downloader.py --batch urls.txt                  # 批量下载
  python cli_downloader.py --mode tiktok https://example.com  # 指定平台
  python cli_downloader.py --output ./downloads https://example.com  # 指定输出目录
  python cli_downloader.py --cookie cookie.txt https://example.com   # 使用Cookie文件
  python cli_downloader.py --proxy http://127.0.0.1:7890 https://example.com  # 使用代理
        """
    )
    
    parser.add_argument(
        'url', 
        nargs='?', 
        help='要下载的视频链接 (抖音或TikTok)'
    )
    
    parser.add_argument(
        '--mode', 
        choices=['douyin', 'tiktok'], 
        help='指定平台类型 (默认自动检测)'
    )
    
    parser.add_argument(
        '--output', 
        '-o', 
        help='指定输出目录'
    )
    
    parser.add_argument(
        '--cookie', 
        help='指定Cookie文件路径'
    )
    
    parser.add_argument(
        '--proxy', 
        help='指定代理地址'
    )
    
    parser.add_argument(
        '--batch', 
        action='store_true', 
        help='批量下载模式 (从文件读取链接)'
    )
    
    parser.add_argument(
        '--file', 
        help='包含链接的文件路径 (用于批量下载)'
    )

    args = parser.parse_args()
    
    # 检查参数
    if args.batch and not args.file:
        print("错误: 批量下载模式需要指定 --file 参数")
        return 1
    
    if not args.url and not (args.batch and args.file):
        print("错误: 请提供要下载的URL或使用批量下载模式")
        parser.print_help()
        return 1
    
    # 创建下载器实例
    async with CLIDownloader() as downloader:
        try:
            if args.batch and args.file:
                # 批量下载模式
                success = await downloader.download_batch(
                    file_path=args.file,
                    platform=args.mode,
                    output_dir=args.output,
                    cookie_file=args.cookie,
                    proxy=args.proxy
                )
            else:
                # 单个下载模式
                success = await downloader.download_single(
                    url=args.url,
                    platform=args.mode,
                    output_dir=args.output,
                    cookie_file=args.cookie,
                    proxy=args.proxy
                )
            
            return 0 if success else 1
            
        except KeyboardInterrupt:
            print("\n用户中断下载")
            return 1
        except Exception as e:
            print(f"程序错误: {str(e)}")
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
