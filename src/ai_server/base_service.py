"""AI服务基类 - 提供通用浏览器操作方法"""

from abc import ABC, abstractmethod
from typing import Optional
from playwright.async_api import async_playwright, Page, Browser
from urllib.parse import urlparse
import asyncio
import json


class BaseAIService(ABC):
    """AI服务基类（异步版本）"""
    
    def __init__(self, cookies: Optional[str] = None, chat_url: Optional[str] = None):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.cookies_dict = self._parse_cookies(cookies) if cookies else None
        self.playwright = None
        self.chat_url = chat_url
        
    def _parse_cookies(self, cookies_str: str) -> list:
        """解析cookies字符串为字典列表"""
        if not cookies_str:
            return []
        try:
            data = json.loads(cookies_str)
            return [data] if isinstance(data, dict) else data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return [{'name': k.strip(), 'value': v.strip()} 
                   for item in cookies_str.split(';') 
                   if '=' in item and (k := item.split('=', 1)[0].strip()) and (v := item.split('=', 1)[1].strip())]
    
    async def _initialize_browser(self, headless: bool = True):
        """初始化浏览器（异步严格执行每个异常检查）"""
        if self.browser and self.page:
            return
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                permissions=['clipboard-read', 'clipboard-write'],
                locale='en-US'
            )
            if self.cookies_dict:
                parsed = urlparse(self.chat_url) if self.chat_url else None
                for cookie in self.cookies_dict:
                    if 'domain' not in cookie and 'url' not in cookie:
                        cookie['domain'] = parsed.netloc if parsed else ''
                    cookie.setdefault('path', '/')
                    # Normalize sameSite to Playwright accepted values (Strict, Lax, None)
                    same_site_key = None
                    for key in cookie.keys():
                        if key.lower() == 'samesite':
                            same_site_key = key
                            break
                    if same_site_key:
                        same_site_value = str(cookie[same_site_key]).strip()
                        same_site_lower = same_site_value.lower()
                        if same_site_lower == 'none':
                            cookie['sameSite'] = 'None'
                        elif same_site_lower == 'strict':
                            cookie['sameSite'] = 'Strict'
                        elif same_site_lower == 'lax':
                            cookie['sameSite'] = 'Lax'
                        else:
                            # Remove invalid sameSite values
                            cookie.pop(same_site_key, None)
                        # Remove the old key if it was different from 'sameSite'
                        if same_site_key != 'sameSite' and same_site_key in cookie:
                            cookie.pop(same_site_key, None)
                await context.add_cookies(self.cookies_dict)
            if self.chat_url:
                parsed = urlparse(self.chat_url)
                await context.grant_permissions(['clipboard-read', 'clipboard-write'], 
                                               origin=f"{parsed.scheme}://{parsed.netloc}")
            self.page = await context.new_page()
        except Exception as e:
            if "Executable doesn't exist" in str(e) or "Looks like Playwright" in str(e):
                raise Exception("Playwright浏览器未安装，请运行: playwright install chromium")
            raise
    
    async def _cleanup_browser(self):
        """清理浏览器资源"""
        for resource, method in [(self.page, 'close'), (self.browser, 'close'), (self.playwright, 'stop')]:
            if resource:
                try:
                    await getattr(resource, method)()
                except:
                    pass
        self.page = self.browser = self.playwright = None
    
    async def summarize(self, final_prompt: str) -> Optional[str]:
        """总结文本（异步模板方法）"""
        try:
            await self._initialize_browser(headless=self._get_headless_mode())
            print(f"正在访问{self._get_service_name()}...")
            await self.page.goto(self.chat_url, wait_until='networkidle')
            await asyncio.sleep(3)
            await self._check_login_status()

            await self._init_page()
            
            if not (input_element := await self._find_input_element()):
                return None
            
            await input_element.fill(final_prompt)
            await asyncio.sleep(1)
            
            if not await self._submit_message(input_element):
                return None
            
            await asyncio.sleep(2)
            return await self._wait_and_get_content()
        except Exception as e:
            print(f"{self._get_service_name()}总结失败: {e}")
            return None
    
    @abstractmethod
    def _get_service_name(self) -> str:
        """获取服务名称"""
        pass
    
    @abstractmethod
    def _get_headless_mode(self) -> bool:
        """获取是否使用无头模式"""
        pass
    
    @abstractmethod
    def _get_input_selectors(self) -> list[str]:
        """获取输入框选择器列表"""
        pass
    
    @abstractmethod
    def _get_submit_selectors(self) -> list[str]:
        """获取提交按钮选择器列表"""
        pass
    
    @abstractmethod
    def _get_wait_success_selector(self) -> Optional[str]:
        """获取等待成功的选择器"""
        pass
    
    async def _init_page(self):
        """初始化页面"""
        pass
    
    def _get_content_selectors(self) -> Optional[list[str]]:
        """获取内容选择器列表（可选）"""
        return None
    
    async def _check_login_status(self):
        """检查登录状态"""
        if "login" in self.page.url.lower():
            print("检测到需要登录，请确保cookies有效")
    
    def _is_content_ready(self, text_content: str) -> bool:
        """判断内容是否就绪"""
        if not text_content or len(text := text_content.strip()) < 50:
            return False
        excluded = ['thinking', 'typing', '思考中', '输入中', '生成中']
        return not any(k in text.lower() for k in excluded)
    
    def _get_max_wait_time(self) -> int:
        """获取最大等待时间（秒）"""
        return 120
    
    def _get_copy_button_selectors(self) -> list[str]:
        """获取复制按钮选择器列表"""
        return [
            'button:has-text("复制")', 'button[aria-label*="复制"]',
            'button[title*="复制"]', 'button.copy-btn', '[data-testid*="copy"]',
            'button:has-text("Copy")', 'button[aria-label*="Copy"]'
        ]
    
    async def _find_input_element(self):
        """查找输入框元素"""
        for selector in self._get_input_selectors():
            try:
                if element := await self.page.wait_for_selector(selector, timeout=5000):
                    return element
            except:
                continue
        return None
    
    async def _submit_message(self, input_element) -> bool:
        """提交消息"""
        for selector in self._get_submit_selectors():
            try:
                if button := await self.page.query_selector(selector):
                    await button.click()
                    return True
            except:
                continue
        try:
            await input_element.press('Enter')
            return True
        except:
            return False
    
    async def _wait_and_get_content(self) -> Optional[str]:
        """等待并获取内容"""
        selector = self._get_wait_success_selector()
        if selector:
            try:
                await self.page.wait_for_selector(selector, timeout=10)
            except:
                pass
        
        max_wait, wait_time, interval = self._get_max_wait_time(), 0, 2
        while wait_time < max_wait:
            if content := await self._try_get_content():
                return content
            await asyncio.sleep(interval)
            wait_time += interval
        return None
    
    async def _try_get_content(self) -> Optional[str]:
        """尝试获取内容（优先剪贴板，其次选择器）"""
        clipboard_content = await self._try_get_from_clipboard()
        if clipboard_content and self._is_content_ready(clipboard_content):
            return clipboard_content.strip()
        
        for selector in (self._get_content_selectors() or []):
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    text = await elements[-1].text_content()
                    if self._is_content_ready(text):
                        return text.strip()
            except:
                continue
        return None
    
    async def _try_get_from_clipboard(self) -> Optional[str]:
        """尝试从剪贴板获取内容"""
        try:
            for selector in self._get_copy_button_selectors():
                if button := await self.page.query_selector(selector):
                    await button.click()
                    await asyncio.sleep(0.3)
                else:
                    return None
            await asyncio.sleep(0.5)
            return await self.page.evaluate("() => navigator.clipboard.readText()")
        except Exception as e:
            print(f"从剪贴板获取内容失败: {e}")
            return None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self._cleanup_browser()
