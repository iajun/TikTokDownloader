"""
AI总结服务模块
负责使用多种AI服务进行内容总结
支持：DeepSeek API (Token方式)、ChatGPT (Browser方式)、腾讯元宝 (Browser方式)
使用S3存储，video_id作为文件名
"""

import tempfile
from pathlib import Path
from typing import Optional
from openai import OpenAI
from ..utils import S3Client
import os
import importlib.util
from ..utils.task_queue import run_io_blocking


class AISummarizer:
    """AI总结服务"""
    
    def __init__(self, api_key: Optional[str] = None, method_name: Optional[str] = None):
        """初始化AI总结服务
        
        Args:
            api_key: API密钥（用于token方式）
            method_name: 使用的方法名称 (deepseek, chatgpt, yuanbao)，如果为None则从数据库读取
        """
        self.api_key = api_key
        self.s3_client = S3Client()
        
        # 如果没有指定方法名，从数据库读取当前活跃的AI方法
        if method_name is None:
            method_name = self._get_active_method_name()
        
        self.method_name = method_name or "deepseek"  # 默认使用deepseek
        self.deepseek_client = None
        
        # 初始化DeepSeek客户端（如果使用token方式）
        if self.method_name == "deepseek" and api_key:
            self.deepseek_client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
            print("DeepSeek客户端初始化成功")
        elif self.method_name in ["chatgpt", "yuanbao"]:
            # 浏览器方式将在使用时初始化
            print(f"将使用浏览器方式: {self.method_name}")
        else:
            print(f"警告: 方法 {self.method_name} 未配置，将跳过AI总结功能")
    
    def _get_active_method_name(self) -> str:
        """从数据库读取当前活跃的AI方法名称"""
        try:
            from ..db import get_db_session
            from ..models import AIMethod
            
            with get_db_session() as db:
                method = db.query(AIMethod).filter(AIMethod.is_active == 1).first()
                if method:
                    print(f"Using active AI method: {method.name}")
                    return method.name
        except Exception as e:
            print(f"Failed to load active AI method: {e}")
        
        # 如果没有配置，返回默认值
        return "deepseek"
    
    def summarize_with_ai(self, text: str, video_id: str, force_regenerate: bool = False, custom_prompt: Optional[str] = None, method_config: Optional[dict] = None) -> Optional[str]:
        """使用AI进行内容总结
        
        Args:
            text: 要总结的文本
            video_id: 视频ID
            force_regenerate: 是否强制重新生成，即使S3中已存在总结
            custom_prompt: 自定义提示词（可选，用户调试时使用）
            method_config: AI方法配置（可选，包含api_key, cookies等）
        """
        # 准备最终的提示词：如果用户提供了自定义提示词则使用，否则使用数据库默认提示词
        if custom_prompt:
            # 用户调试：使用用户提供的提示词（可能包含{text}占位符）
            final_prompt = custom_prompt.format(text=text) if '{text}' in custom_prompt else f"{custom_prompt}\n\n{text}"
        else:
            # 使用默认提示词模板
            default_prompt_template = self._get_default_prompt_template()
            if default_prompt_template:
                final_prompt = default_prompt_template.format(text=text)
            else:
                final_prompt = f"请总结以下内容：\n\n{text}"
        
        # 根据方法名称选择不同的实现
        if self.method_name == "deepseek":
            return self._summarize_with_api(text, video_id, force_regenerate, final_prompt, method_config)
        elif self.method_name == "chatgpt":
            return self._summarize_with_browser("chatgpt", text, video_id, force_regenerate, final_prompt, method_config)
        elif self.method_name == "yuanbao":
            return self._summarize_with_browser("yuanbao", text, video_id, force_regenerate, final_prompt, method_config)
        else:
            print(f"未知的AI方法: {self.method_name}")
            return None
    
    def _summarize_with_api(self, text: str, video_id: str, force_regenerate: bool = False, final_prompt: str = None, method_config: Optional[dict] = None) -> Optional[str]:
        """使用API方式（如DeepSeek）进行总结"""
        # 尝试从配置获取API密钥
        if not self.api_key:
            # 从数据库读取API密钥
            try:
                from ..db import get_db_session
                from ..models import AIMethod
                
                with get_db_session() as db:
                    method = db.query(AIMethod).filter(AIMethod.name == self.method_name).first()
                    if method and method.api_key:
                        self.api_key = method.api_key
            except Exception as e:
                print(f"Failed to load API key from database: {e}")
        
        api_key = method_config.get('api_key') if method_config else self.api_key
        
        if not api_key and not self.deepseek_client:
            print("未配置API密钥，跳过AI总结")
            return None
        
        try:
            
            # 本地临时总结文件
            temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
            temp_dir.mkdir(exist_ok=True)
            summary_file = temp_dir / f"{video_id}_summary.txt"
            
            # 如果不强制重新生成，检查本地临时文件
            if not force_regenerate:
                if summary_file.exists():
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary = f.read().strip()
                    if summary:
                        print("使用本地临时总结文件")
                        return summary
            
            if force_regenerate:
                print("强制重新生成总结，忽略已有的本地和S3文件")
            else:
                print("正在使用AI进行内容总结...")
            
            # 使用上层传入的最终提示词
            prompt = final_prompt
            
            # 从数据库读取 AI 参数
            max_tokens = 2000
            temperature = 0.7
            model = "deepseek-chat"
            system_prompt = ""
            
            try:
                from ..db import get_db_session
                from ..models import Setting
                
                with get_db_session() as db:
                    # 读取 max_tokens
                    setting = db.query(Setting).filter(Setting.key == "ai_max_tokens").first()
                    if setting and setting.value:
                        max_tokens = int(setting.value)
                    
                    # 读取 temperature
                    setting = db.query(Setting).filter(Setting.key == "ai_temperature").first()
                    if setting and setting.value:
                        temperature = float(setting.value)
                    
                    # 读取 model
                    setting = db.query(Setting).filter(Setting.key == "ai_model").first()
                    if setting and setting.value:
                        model = setting.value
                    
                    # 读取 system_prompt
                    setting = db.query(Setting).filter(Setting.key == "ai_system_prompt").first()
                    if setting and setting.value:
                        system_prompt = setting.value
            except Exception as e:
                print(f"Failed to load AI settings from database: {e}, using defaults")
            
            response = self.deepseek_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            summary = response.choices[0].message.content.strip()
            print("AI总结完成")
            return summary
            
        except Exception as e:
            print(f"AI总结失败: {str(e)}")
            return None
    
    def _summarize_with_browser(self, method_type: str, text: str, video_id: str, force_regenerate: bool = False, final_prompt: str = None, method_config: Optional[dict] = None) -> Optional[str]:
        """使用浏览器方式（如ChatGPT、腾讯元宝）进行总结"""
        try:
            # 动态导入ai_server模块
            ai_server_spec = importlib.util.find_spec("src.ai_server")
            if not ai_server_spec:
                print("ai_server模块未找到，请确保已安装playwright")
                return None
            
            from src.ai_server import ChatGPTService, YuanBaoService
            from src.ai_server.base_service import BaseAIService
            
            # 获取cookies
            cookies = method_config.get('cookies') if method_config else None
            if not cookies:
                # 尝试从数据库读取
                from ..db import get_db_session
                from ..models import AIMethod
                
                with get_db_session() as db:
                    method = db.query(AIMethod).filter(AIMethod.name == method_type).first()
                    if method and method.cookies:
                        cookies = method.cookies
            
            # 初始化服务
            if method_type == "chatgpt":
                service = ChatGPTService(cookies)
            elif method_type == "yuanbao":
                service = YuanBaoService(cookies)
            else:
                print(f"未知的浏览器方法: {method_type}")
                return None
            
            print(f"使用{method_type}浏览器方式总结...")
            
            # 由于async_playwright需要事件循环，但当前可能是从线程调用
            # 在线程中创建并运行异步代码
            def run_in_thread():
                async def run_summarize():
                    async with service:
                        # 传递最终的提示词（已经在上层处理好，包含完整的提示词+文本）
                        return await service.summarize(final_prompt)
                
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(run_summarize())
                finally:
                    loop.close()
            
            # 在线程池中运行
            summary = self._run_in_thread(run_in_thread)
            
            if summary:
                print(f"{method_type}总结完成")
                return summary
            else:
                print(f"{method_type}总结失败")
                return None
                
        except Exception as e:
            print(f"浏览器总结失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_default_prompt_template(self) -> Optional[str]:
        """获取默认提示词模板（包含{text}占位符）"""
        prompt_info = self._get_default_prompt_info()
        return prompt_info['content'] if prompt_info else None
    
    def _get_default_prompt_info(self) -> Optional[dict]:
        """获取默认提示词信息（包含名称和内容）"""
        # 首先尝试从 prompts 表获取默认提示词
        try:
            from ..db import get_db_session
            from ..models import Prompt
            
            with get_db_session() as db:
                default_prompt = db.query(Prompt).filter(Prompt.is_default == 1).first()
                if default_prompt and default_prompt.content:
                    return {
                        'name': default_prompt.name,
                        'content': default_prompt.content
                    }
        except Exception as e:
            print(f"Failed to load default prompt from prompts table: {e}")
        
        # 尝试从数据库 Setting 读取（兼容旧数据）
        try:
            from ..db import get_db_session
            from ..models import Setting
            
            with get_db_session() as db:
                setting = db.query(Setting).filter(Setting.key == "ai_prompt_template").first()
                if setting and setting.value:
                    return {
                        'name': '默认提示词',
                        'content': setting.value
                    }
        except Exception as e:
            print(f"Failed to load prompt from database: {e}")
        
        return None
    
    def _download_text_from_s3(self, s3_path: str) -> Optional[str]:
        """从S3下载文本文件内容"""
        try:
            temp_dir = Path(tempfile.gettempdir()) / "ai_service_downloads"
            temp_dir.mkdir(exist_ok=True)
            
            filename = Path(s3_path).name
            local_path = temp_dir / filename
            
            if self.s3_client.download_file(s3_path, str(local_path)):
                with open(local_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            
            return None
        except Exception as e:
            print(f"从S3下载文本失败: {str(e)}")
            return None
    
    def _run_in_thread(self, func):
        """在共享线程池中运行阻塞函数，保持接口同步返回结果。"""
        return run_io_blocking(func)

