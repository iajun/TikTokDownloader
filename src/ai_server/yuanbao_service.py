"""腾讯元宝 Service - 使用 Playwright 访问 yuanbao.tencent.com"""

from typing import Optional
from .base_service import BaseAIService


class YuanBaoService(BaseAIService):
    """腾讯元宝服务"""
    
    def __init__(self, cookies: Optional[str] = None):
        super().__init__(cookies, "https://yuanbao.tencent.com")
    
    def _get_service_name(self) -> str:
        return "腾讯元宝"
    
    def _get_headless_mode(self) -> bool:
        return True
    
    def _get_input_selectors(self) -> list[str]:
        return ['.chat-input-editor > .ql-editor']

    async def _init_page(self):
        if button := await self.page.query_selector('div[dt-button-id="deep_think"]'):
            await button.click()
    
    def _get_submit_selectors(self) -> list[str]:
        return ['#yuanbao-send-btn']
    
    def _get_wait_success_selector(self) -> Optional[str]:
        return '#chat-content div.agent-chat__toolbar__copy__arrow-container > span'
    
    def _get_copy_button_selectors(self) -> list[str]:
        return [
            '#chat-content div.agent-chat__toolbar__copy__arrow-container > span',
            '#hunyuan-bot > div.t-portal-wrapper.enter-done > div > div > div > div:nth-child(2) > li > span'
        ]
    
    async def _check_login_status(self):
        page_content = await self.page.content()
        if "login" in self.page.url.lower() or "未登录" in page_content:
            print("检测到需要登录，请确保cookies有效")
