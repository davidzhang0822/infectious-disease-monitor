"""Playwright 无头浏览器工具（GitHub Actions 环境使用）

替换 browser-act stealth-extract，在 CI/CD 环境中绕过 WAF。

提供两种使用方式：
1. ``stealth_fetch(url)``   —— 单页抓取，每次调用独立启动浏览器（原有语义，保持不变）
2. ``StealthSession``       —— 上下文管理器，一次启动浏览器抓多个页面

为什么保留两种：
``stealth_fetch`` 每次调用都启一个独立会话，故障隔离在调用级——某个站点把
浏览器搞挂时不会影响其他源。若改成全局共享会话，一旦浏览器失效，后续所有
源都会一起失败，把"单源故障"升级成"全站故障"，对生产监测系统不可接受。
需要批量抓取时，由调用方在自己的 ``fetch_items()`` 内开启 session，
故障范围就限制在该源内部。
"""

import asyncio
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")


class StealthSession:
    """可复用的无头浏览器会话：一次启动，抓多个页面。

    用法::

        with StealthSession() as sess:
            html_a = sess.fetch(url_a)
            html_b = sess.fetch(url_b)
    """

    def __init__(self, timeout: int = 60, wait_ms: int = 3000):
        self._pw = None
        self._browser = None
        self._context = None
        self.timeout = timeout
        self.wait_ms = wait_ms

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._context = self._browser.new_context(
            user_agent=UA,
            viewport={"width": 1920, "height": 1080},
        )
        return self

    def __exit__(self, *exc):
        # 必须确保 pw.stop() 被调用，否则 Playwright 子进程会挂住 CI
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
        finally:
            if self._pw:
                self._pw.stop()
        return False

    def fetch(self, url: str, timeout: int = None) -> str:
        """获取页面渲染后的完整 HTML。

        每个 URL 使用独立 page，避免站点之间 cookie / localStorage 串味。
        """
        timeout = timeout or self.timeout
        page = self._context.new_page()
        try:
            page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(self.wait_ms)  # 等待 JS 渲染
            return page.content()
        finally:
            page.close()

    def fetch_many(self, urls, timeout: int = None) -> dict:
        """批量抓取，返回 {url: html}。单个 URL 失败不中断其余。"""
        out = {}
        for u in urls:
            try:
                out[u] = self.fetch(u, timeout)
            except Exception as e:
                print(f"  [browser] 抓取失败 {u}: {e}")
        return out


class StealthBrowser:
    """轻量级 stealth 浏览器，用于绕过 WAF 抓取页面"""

    def __init__(self):
        self._playwright = None
        self._browser = None

    def fetch(self, url: str, timeout: int = 60) -> str:
        """获取页面渲染后的完整 HTML（每次调用独立启动浏览器）"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=UA,
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
    """便捷函数：stealth 抓取页面 HTML（单页，每次独立启动浏览器）"""
    return get_browser().fetch(url)


def stealth_fetch_many(urls, timeout: int = 60) -> dict:
    """便捷函数：一次浏览器启动，抓多个页面，返回 {url: html}"""
    with StealthSession(timeout=timeout) as sess:
        return sess.fetch_many(urls, timeout)
