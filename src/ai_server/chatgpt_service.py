"""ChatGPT Service - 使用 Playwright 访问 ChatGPT"""

from typing import Optional
from .base_service import BaseAIService


class ChatGPTService(BaseAIService):
    """ChatGPT服务"""
    
    def __init__(self, cookies: Optional[str] = None):
        super().__init__(cookies, "https://chat.openai.com")
    
    def _get_service_name(self) -> str:
        return "ChatGPT"
    
    def _get_headless_mode(self) -> bool:
        return True
    
    def _get_input_selectors(self) -> list[str]:
        return [
            '#prompt-textarea'
        ]
    
    def _get_submit_selectors(self) -> list[str]:
        return ['composer-submit-button'] 
    def _get_wait_success_selector(self) -> Optional[str]:
        return '#thread article:nth-child(2) button[aria-label="Copy"]'
    
    def _get_copy_button_selectors(self) -> list[str]:
        return ['#thread article:nth-child(2) button[aria-label="Copy"]']
