"""中国疾控中心 chinacdc.cn 数据源

覆盖栏目：
- jksj01: 全国法定传染病疫情概况（月报）
- xgbdyq: 全国新冠感染疫情情况（月报）
- jksj04_14275: 全国急性呼吸道传染病哨点监测（周报）
"""

import re
from . import BaseSource


class ChinacdcSource(BaseSource):
    name = "中国疾控中心"
    key = "chinacdc"

    CHANNELS = [
        {
            "name": "全国法定传染病疫情概况",
            "url": "https://www.chinacdc.cn/jksj/jksj01/",
            "url_pattern": r"jksj01/(\d{6})/t(\d{8})_(\d+)\.html",
        },
        {
            "name": "全国新冠感染疫情情况",
            "url": "https://www.chinacdc.cn/jksj/xgbdyq/",
            "url_pattern": r"xgbdyq/(\d{6})/t(\d{8})_(\d+)\.html",
        },
        {
            "name": "急性呼吸道传染病哨点监测",
            "url": "https://www.chinacdc.cn/jksj/jksj04_14275/",
            "url_pattern": r"jksj04_14275/(\d{6})/t(\d{8})_(\d+)\.html",
        },
    ]

    def fetch_items(self) -> list[dict]:
        items = []
        for channel in self.CHANNELS:
            try:
                html = self.fetch_html(channel["url"])
                channel_items = self._parse_list(html, channel)
                items.extend(channel_items)
                print(f"  [{channel['name']}] 解析到 {len(channel_items)} 条")
            except Exception as e:
                print(f"  [{channel['name']}] 抓取失败: {e}")
        return items

    def _parse_list(self, html: str, channel: dict) -> list[dict]:
        """解析 CDC 列表页 HTML

        结构：<dd><a href="./202607/t20260708_1837979.html" target="_blank">
              标题<span>日期</span></a></dd>
        """
        import re
        items = []
        seen = set()

        # 匹配：<a href="./YYYYMM/tYYYYMMDD_ID.html" ...>标题<span>日期</span></a>
        pattern = re.compile(
            r'<a\s+href="([^"]*t(\d{8})_(\d+)\.html)"[^>]*>'
            r'(.+?)'
            r'</a>',
            re.DOTALL,
        )

        for m in pattern.finditer(html):
            url_path = m.group(1)
            date_in_url = m.group(2)
            item_id = f"cdc_{m.group(3)}"

            if item_id in seen:
                continue
            seen.add(item_id)

            # 提取标题（去除 span 标签和日期）
            raw_title = m.group(4).strip()
            raw_title = re.sub(r'<span[^>]*>.*?</span>', '', raw_title, flags=re.DOTALL)
            raw_title = re.sub(r'<[^>]+>', '', raw_title).strip()

            # 提取日期（从 span 中）
            date_match = re.search(r'<span[^>]*>(\d{4}-\d{2}-\d{2})', m.group(4))
            pub_date = date_match.group(1) if date_match else ""

            # 构造完整 URL
            if url_path.startswith("http"):
                full_url = url_path
            elif url_path.startswith("/"):
                full_url = f"https://www.chinacdc.cn{url_path}"
            else:
                base = channel["url"].rstrip("/")
                full_url = f"{base}/{url_path.lstrip('./')}"

            items.append({
                "id": item_id,
                "title": raw_title,
                "date": pub_date,
                "url": full_url,
                "source": self.key,
                "source_name": self.name,
                "category": channel["name"],
            })

        return items
