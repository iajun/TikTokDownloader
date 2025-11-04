"""
Obsidian 同步服务
用于将视频总结同步到 Obsidian 库的专门文件夹
"""

import os
from pathlib import Path
from typing import Optional
from datetime import datetime
import re
from dotenv import load_dotenv

# 加载 .env 文件
BASE_DIR = Path(__file__).parent.parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)


class ObsidianService:
    """Obsidian 同步服务"""
    
    def __init__(self):
        """初始化 Obsidian 服务"""
        # 从环境变量读取配置
        self.vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
        self.summaries_folder = os.getenv("OBSIDIAN_SUMMARIES_FOLDER", "Summaries")
        
        # 如果未配置，尝试使用默认路径（macOS 常见路径）
        if not self.vault_path:
            # 尝试常见的 Obsidian 库路径
            default_paths = [
                Path.home() / "Documents" / "Obsidian",
                Path.home() / "Obsidian",
            ]
            for path in default_paths:
                if path.exists() and (path / ".obsidian").exists():
                    self.vault_path = str(path)
                    print(f"自动检测到 Obsidian 库路径: {self.vault_path}")
                    break
        
        # 确保文件夹路径是 Path 对象
        if self.vault_path:
            self.vault_path = Path(self.vault_path)
        
    def is_configured(self) -> bool:
        """检查 Obsidian 服务是否已配置"""
        if not self.vault_path:
            return False
        
        # 检查路径是否存在且是 Obsidian 库（有 .obsidian 文件夹）
        vault_path = Path(self.vault_path)
        if not vault_path.exists():
            return False
        
        # 检查是否是 Obsidian 库
        if not (vault_path / ".obsidian").exists():
            print(f"警告: {vault_path} 不是有效的 Obsidian 库（缺少 .obsidian 文件夹）")
            return False
        
        return True
    
    def _sanitize_filename(self, filename: str, max_length: int = 100) -> str:
        """清理文件名，移除不合法字符
        
        Args:
            filename: 原始文件名
            max_length: 最大长度
        
        Returns:
            清理后的文件名
        """
        # 移除或替换不合法字符
        # Windows: < > : " / \ | ? *
        # macOS/Linux: / 
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # 移除前后空格和点
        filename = filename.strip(' .')
        
        # 限制长度
        if len(filename) > max_length:
            filename = filename[:max_length]
        
        # 如果文件名为空，使用默认名称
        if not filename:
            filename = "未命名"
        
        return filename
    
    def _format_summary_content(
        self,
        video_info: dict,
        summary_content: str,
        summary_name: str = "总结"
    ) -> str:
        """格式化总结内容为 Markdown
        
        Args:
            video_info: 视频信息字典
            summary_content: 总结内容（Markdown格式）
            summary_name: 总结名称
        
        Returns:
            格式化后的 Markdown 内容
        """
        # 获取视频信息
        platform = video_info.get('platform', 'douyin')
        platform_text = "抖音" if platform == 'douyin' else "TikTok"
        desc = video_info.get('desc', '无标题')
        nickname = video_info.get('nickname', '未知')
        video_id = video_info.get('video_id', '')
        share_url = video_info.get('share_url', video_info.get('url', ''))
        digg_count = video_info.get('digg_count', 0)
        comment_count = video_info.get('comment_count', 0)
        share_count = video_info.get('share_count', 0)
        
        # 获取当前时间
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建 Markdown 内容
        content = f"""---
title: {desc[:50] if desc else '视频总结'}
date: {now.strftime("%Y-%m-%d")}
time: {now.strftime("%H:%M:%S")}
platform: {platform_text}
video_id: {video_id}
author: {nickname}
---

# {desc or '视频总结'}

## 📋 视频信息

- **平台**: {platform_text}
- **作者**: {nickname}
- **视频ID**: `{video_id}`
- **视频链接**: [{share_url[:50] + '...' if len(share_url) > 50 else share_url}]({share_url})
- **点赞数**: {digg_count}
- **评论数**: {comment_count}
- **分享数**: {share_count}
- **总结时间**: {date_str}

## 📝 {summary_name}

{summary_content}

---

*此总结由 TikTok 下载器自动生成*
"""
        return content
    
    def save_summary_to_obsidian(
        self,
        video_info: dict,
        summary_content: str,
        summary_name: str = "总结"
    ) -> Optional[str]:
        """保存总结到 Obsidian 库
        
        Args:
            video_info: 视频信息字典（包含 desc, platform, url, nickname 等）
            summary_content: 总结内容（Markdown格式）
            summary_name: 总结名称
        
        Returns:
            保存的文件路径，如果失败返回 None
        """
        if not self.is_configured():
            print("Obsidian 服务未配置，跳过同步")
            return None
        
        try:
            # 确保总结文件夹存在
            summaries_folder = self.vault_path / self.summaries_folder
            summaries_folder.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            desc = video_info.get('desc', '')
            nickname = video_info.get('nickname', '')
            video_id = video_info.get('video_id', '')
            date_str = datetime.now().strftime("%Y-%m-%d")
            
            # 构建文件名：日期_作者_标题_video_id
            # 如果标题太长，只取前30个字符
            title_part = self._sanitize_filename(desc[:30] if desc else '视频', max_length=30)
            author_part = self._sanitize_filename(nickname[:20] if nickname else '未知', max_length=20)
            
            # 文件名格式：YYYY-MM-DD_作者_标题_video_id.md
            filename_parts = [date_str]
            if author_part:
                filename_parts.append(author_part)
            if title_part:
                filename_parts.append(title_part)
            if video_id:
                filename_parts.append(video_id[:10])  # 只取前10位
            
            filename = "_".join(filename_parts) + ".md"
            filename = self._sanitize_filename(filename, max_length=200)
            
            # 完整文件路径
            file_path = summaries_folder / filename
            
            # 如果文件已存在，添加序号
            if file_path.exists():
                counter = 1
                base_name = file_path.stem
                while file_path.exists():
                    new_filename = f"{base_name}_{counter}.md"
                    file_path = summaries_folder / new_filename
                    counter += 1
                    if counter > 100:  # 防止无限循环
                        break
            
            # 格式化内容
            formatted_content = self._format_summary_content(
                video_info,
                summary_content,
                summary_name
            )
            
            # 写入文件
            file_path.write_text(formatted_content, encoding='utf-8')
            
            print(f"总结已保存到 Obsidian: {file_path}")
            return str(file_path)
            
        except Exception as e:
            print(f"保存总结到 Obsidian 失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_batch_summaries(
        self,
        summaries: list[dict]
    ) -> dict:
        """批量保存总结到 Obsidian
        
        Args:
            summaries: 总结列表，每个元素包含 video_info, summary_content, summary_name
        
        Returns:
            保存结果字典 {index: file_path or None}
        """
        results = {}
        for idx, summary_data in enumerate(summaries):
            result = self.save_summary_to_obsidian(
                summary_data.get('video_info', {}),
                summary_data.get('summary_content', ''),
                summary_data.get('summary_name', '总结')
            )
            results[idx] = result
        return results

