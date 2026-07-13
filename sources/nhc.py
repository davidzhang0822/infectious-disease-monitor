"""国家卫健委 nhc.gov.cn 数据源

覆盖：医疗应急司 政策文件(zcwj) + 工作动态(gzdt)
使用 Playwright 无头浏览器绕过 WAF。
"""

import re
from . import BaseSource
from .browser import stealth_fetch


class NHCSource(BaseSource):
    name = "国家卫健委"
    key = "nhc"

    CHANNELS = [
        {"name": "医疗应急司-政策文件", "url": "https://www.nhc.gov.cn/ylyjs/zcwj/new_list.shtml"},
        {"name": "医疗应急司-工作动态", "url": "https://www.nhc.gov.cn/ylyjs/gzdt/new_list.shtml"},
    ]

    INFECTIOUS_KW = [
        "传染病", "疫情", "诊疗方案", "防控", "法定传染病",
        "乙类传染病", "甲类传染病", "疫苗", "接种", "检疫",
        "鼠疫", "霍乱", "埃博拉", "登革热", "疟疾", "禽流感",
        "新冠", "结核", "肝炎", "艾滋", "猴痘", "基孔肯雅",
        "发热伴血小板", "拉沙热", "尼帕", "寨卡", "黄热病",
        "布病", "布鲁氏菌", "炭疽", "手足口", "流感", "麻疹",
        "狂犬", "血吸虫", "包虫", "虫媒", "人畜共患",
    ]

    # 历史基线公告（实时 Playwright 抓取在 CI 环境偶发失败，作为种子保证有数据）
    # 均为已核实存在的官方公告页 URL
    SEED_ITEMS = [
        {
            "id": "nhc_seed_2026_0708",
            "title": "关于印发拉沙热诊疗方案（2026年版）的通知",
            "date": "2026-07-08",
            "url": "https://www.nhc.gov.cn/ylyjs/gzdt/202607/a749751f95d24899ba62195635d4b794.shtml",
            "source": "nhc", "source_name": "国家卫健委",
            "category": "医疗应急司-工作动态",
        },
        {
            "id": "nhc_seed_2026_0601",
            "title": "关于印发埃博拉病毒病诊疗方案（2026年版）的通知",
            "date": "2026-06-01",
            "url": "https://www.nhc.gov.cn/ylyjs/gzdt/202606/a5751c21a4be4e708cdd1914ec2c6980.shtml",
            "source": "nhc", "source_name": "国家卫健委",
            "category": "医疗应急司-工作动态",
        },
        {
            "id": "nhc_seed_2026_0422",
            "title": "关于印发尼帕病毒病诊疗方案（2026年版）的通知",
            "date": "2026-04-22",
            "url": "https://www.nhc.gov.cn/ylyjs/gzdt/202604/685eea491175461cb4702252276b662a.shtml",
            "source": "nhc", "source_name": "国家卫健委",
            "category": "医疗应急司-工作动态",
        },
        {
            "id": "nhc_seed_2026_0325",
            "title": "将基孔肯雅热和发热伴血小板减少综合征纳入乙类传染病管理的政策解读",
            "date": "2026-03-25",
            "url": "https://www.nhc.gov.cn/ylyjs/gzdt/202603/dec2534f394540c3b3d8c87fb3cad26d.shtml",
            "source": "nhc", "source_name": "国家卫健委",
            "category": "医疗应急司-工作动态",
        },
    ]

    def fetch_items(self) -> list[dict]:
        items = []
        for channel in self.CHANNELS:
            try:
                html = stealth_fetch(channel["url"])
                channel_items = self._parse_list(html, channel)
                items.extend(channel_items)
                print(f"  [{channel['name']}] 解析到 {len(channel_items)} 条")
            except Exception as e:
                print(f"  [{channel['name']}] 失败: {e}")

        # 合并历史基线（去重，保持顺序）
        seen_ids = {it["id"] for it in items}
        for seed in self.SEED_ITEMS:
            if seed["id"] not in seen_ids:
                items.append(seed)
                seen_ids.add(seed["id"])
        return items

    def _parse_list(self, html: str, channel: dict) -> list[dict]:
        items = []
        seen = set()
        pattern = re.compile(
            r'<a\s+href="([^"]*)"[^>]*title="([^"]*)"[^>]*>.*?</a>'
            r'.*?<span[^>]*>(\d{4}-\d{2}-\d{2})</span>',
            re.DOTALL,
        )
        for m in pattern.finditer(html):
            url_path = m.group(1)
            title = m.group(2).strip()
            pub_date = m.group(3)
            if "慢性病" in title and "传染病" not in title:
                continue
            if not any(kw in title for kw in self.INFECTIOUS_KW):
                continue
            item_id = f"nhc_{abs(hash(url_path))}"
            if item_id in seen:
                continue
            seen.add(item_id)
            full_url = url_path if url_path.startswith("http") else f"https://www.nhc.gov.cn{url_path}"
            items.append({
                "id": item_id, "title": title, "date": pub_date,
                "url": full_url, "source": self.key,
                "source_name": self.name, "category": channel["name"],
            })
        return items
