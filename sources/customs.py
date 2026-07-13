"""海关总署 customs.gov.cn 数据源

覆盖：口岸疫情防控公告（防止XX疫情传入我国）
使用 Playwright 无头浏览器绕过 WAF，适配 GitHub Actions 环境。

注意：海关疫情公告发布频率很低（数月一条），且公告列表页近期条目多为
非疫情类（检验检疫、进口要求等），实时列表过滤经常返回 0 条。
因此这里保留 SEED_ITEMS 作为历史基线，保证仪表盘始终有数据；
同时仍通过 Playwright 实时抓取列表，捕获新发布的疫情公告。
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

    # 历史基线公告（实时列表长期不含疫情类，作为种子保证有数据）
    # 均为已核实可访问的官方公告 PDF
    SEED_ITEMS = [
        {
            "id": "customs_seed_2026_65",
            "title": "海关总署公告2026年第65号（关于防止埃博拉病毒病疫情传入我国的公告）",
            "date": "2026-05-18",
            "url": "http://www.customs.gov.cn/customs/attachDir/2026/05/"
                   "%E6%B5%B7%E5%85%B3%E6%80%BB%E7%BD%B2%E5%85%B3%E4%BA%8E%E9%98%B2%E6%AD%A2"
                   "%E5%9F%83%E5%8D%9A%E6%8B%89%E7%97%85%E6%AF%92%E7%97%85%E7%96%AB%E6%83%85"
                   "%E4%BC%A0%E5%85%A5%E6%88%91%E5%9B%BD%E7%9A%84%E5%85%AC%E5%91%8A(1).pdf",
            "source": "customs", "source_name": "海关总署",
            "category": "口岸疫情防控公告",
        },
        {
            "id": "customs_seed_2026_64",
            "title": "海关总署 农业农村部公告2026年第64号（关于防止塞拉利昂绵羊痘和山羊痘传入我国的公告）",
            "date": "2026-05-14",
            "url": "http://www.customs.gov.cn/customs/attachDir/2026/05/"
                   "%E6%B5%B7%E5%85%B3%E6%80%BB%E7%BD%B2%20%E5%86%9C%E4%B8%9A%E5%86%9C%E6%9D%91"
                   "%E9%83%A8%E5%85%B3%E4%BA%8E%E9%98%B2%E6%AD%A2%E5%A1%9E%E6%8B%89%E5%88%A9%E6%98%82"
                   "%E7%BB%B5%E7%BE%8A%E7%97%98%E5%92%8C%E5%B1%B1%E7%BE%8A%E7%97%98%E4%BC%A0%E5%85%A5"
                   "%E6%88%91%E5%9B%BD%E7%9A%84%E5%85%AC%E5%91%8A%281%29.pdf",
            "source": "customs", "source_name": "海关总署",
            "category": "口岸疫情防控公告",
        },
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

        # 合并历史基线（去重，保持顺序）
        seen_ids = {it["id"] for it in items}
        for seed in self.SEED_ITEMS:
            if seed["id"] not in seen_ids:
                items.append(seed)
                seen_ids.add(seed["id"])

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
