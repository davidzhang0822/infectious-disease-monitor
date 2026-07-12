"""Playwright 无头浏览器工具（GitHub Actions 环境使用）

替换 browser-act stealth-extract，在 CI/CD 环境中绕过 WAF。
"""

import asyncio
from playwright.sync_api import sync_playwright


class StealthBrowser:
    """轻量级 stealth 浏览器，用于绕过 WAF 抓取页面"""

    def __init__(self):
        self._playwright = None
        self._browser = None

    def fetch(self, url: str, timeout: int = 60) -> str:
        """获取页面渲染后的完整 HTML"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            try:
                page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)  # 等待 JS 渲染
                html = page.content()
                return html
            finally:
                context.close()
                browser.close()


# 全局实例
_stealth = None


def get_browser() -> StealthBrowser:
    global _stealth
    if _stealth is None:
        _stealth = StealthBrowser()
    return _stealth


def stealth_fetch(url: str) -> str:
    """便捷函数：stealth 抓取页面 HTML"""
    return get_browser().fetch(url)
