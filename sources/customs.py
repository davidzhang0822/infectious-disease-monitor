"""海关总署 customs.gov.cn 数据源

覆盖：口岸疫情防控公告（防止XX疫情传入我国）
使用 Playwright 无头浏览器绕过 WAF，适配 GitHub Actions 环境。
"""

import re
from . import BaseSource
from .browser import stealth_fetch


class CustomsSource(BaseSource):
    name = "海关总署"
    key = "customs"

    LIST_URLS = [
        "http://jckspj.customs.gov.cn/customs/302249/302266/index.html",
        "http://jckspj.customs.gov.cn/customs/xwfb34/302425/index.html",
    ]

    EPIDEMIC_KW = [
        "防止", "疫情传入", "防控", "埃博拉", "登革热", "猴痘",
        "疟疾", "黄热病", "寨卡", "禽流感", "鼠疫", "霍乱",
        "新冠", "基孔肯雅", "炭疽", "口蹄疫", "猪瘟",
        "非洲马瘟", "小反刍兽疫", "牛传染性胸膜肺炎",
        "绵羊痘", "山羊痘",
    ]

    def fetch_items(self) -> list[dict]:
        items = []
        for url in self.LIST_URLS:
            try:
                html = stealth_fetch(url)
                items.extend(self._parse_list(html))
            except Exception:
                pass

        if not items:
            print("  [海关总署] 当前无新增疫情相关公告")
        return items

    def _parse_list(self, html: str) -> list[dict]:
        items = []
        seen = set()
        pattern = re.compile(
            r'<a\s+href="(/customs/\d{4}-\d{2}/\d{2}/article_\d+\.html)"'
            r'[^>]*title="([^"]*)"',
            re.DOTALL,
        )
        for m in pattern.finditer(html):
            url_path = m.group(1)
            title = m.group(2).strip()
            if not self._is_epidemic(title):
                continue
            date_m = re.search(r'/customs/(\d{4}-\d{2})/', url_path)
            pub_date = date_m.group(1) if date_m else ""
            id_m = re.search(r'article_(\d+)', url_path)
            item_id = f"customs_{id_m.group(1)}" if id_m else f"customs_{abs(hash(url_path))}"
            if item_id in seen:
                continue
            seen.add(item_id)
            items.append({
                "id": item_id, "title": title, "date": pub_date,
                "url": f"http://jckspj.customs.gov.cn{url_path}",
                "source": self.key, "source_name": self.name,
                "category": "口岸疫情防控公告",
            })
        return items

    def _is_epidemic(self, title: str) -> bool:
        return any(kw in title for kw in self.EPIDEMIC_KW)
