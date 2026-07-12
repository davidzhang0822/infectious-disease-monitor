"""国家疾控局 ndcpa.gov.cn 数据源

覆盖栏目：
- c100014: 通知公告（防控方案、通知通告等）
- c100013: 政策解读（配套解读问答）
"""

import re
from . import BaseSource


class NdcpaSource(BaseSource):
    name = "国家疾控局"
    key = "ndcpa"

    LIST_URL = "https://www.ndcpa.gov.cn/jbkzzx/c100014/common/list.html"

    def fetch_items(self) -> list[dict]:
        html = self.fetch_html(self.LIST_URL)
        return self._parse_items(html)

    def _parse_items(self, html: str) -> list[dict]:
        """从 JS 变量 itemObj 中提取公告列表"""
        items = []

        js_match = re.search(r'var\s+itemObj\s*=\s*(\[[\s\S]*?\]);', html)
        if not js_match:
            print("  [ndcpa] 未找到 JS 数据块")
            return []

        js_data = js_match.group(1)

        titles = re.findall(r'"aT":"([^"]+)"', js_data)
        dates = re.findall(r'"aPd":"([^"]+)"', js_data)
        content_ids = re.findall(r'content_(\d+)\.html', js_data)

        if not titles or not content_ids:
            print("  [ndcpa] JS 解析失败")
            return []

        seen = set()
        for i in range(min(len(titles), len(content_ids))):
            content_id = content_ids[i]
            if content_id in seen:
                continue
            seen.add(content_id)

            items.append({
                "id": content_id,
                "title": titles[i],
                "date": dates[i][:10] if i < len(dates) else "",
                "url": f"https://www.ndcpa.gov.cn/jbkzzx/c100014/common/content/content_{content_id}.html",
                "source": self.key,
                "source_name": self.name,
                "category": "通知公告",
            })

        return items
