"""国家市场监督管理总局 · 食品安全抽检监测司 数据源

覆盖栏目：信息发布（spcjs/xxfb）
内容：BJS/KJ 检验方法发布与废止公告、立项征集公告、食品安全监督抽检通报

这一栏是检验方法库更新的第一手来源：方法发布与废止公告直接影响本实验室
可用的检测依据，抽检通报则反映当前监管重点。
"""

from . import BaseSource
from .samr_common import (
    PAGE_IDS,
    absolutize,
    article_id_from_href,
    fetch_samr_column,
    parse_samr_articles,
)


class SamrSpcjsSource(BaseSource):
    name = "市场监管总局·食品抽检司"
    key = "samr_spcjs"

    LIST_URL = "https://www.samr.gov.cn/spcjs/xxfb/index.html"

    # 分类关键词，按优先级顺序匹配（先匹配到的胜出）
    RULES = [
        ("方法废止公告", ["废止"]),
        ("方法发布公告", ["补充检验方法", "快速检测方法", "检验方法", "检测方法"]),
        ("立项征集公告", ["立项建议", "公开征集"]),
        ("抽检通报", ["抽检", "通报"]),
    ]

    def fetch_items(self) -> list[dict]:
        html = fetch_samr_column(self.LIST_URL, page_size=20,
                                 fallback_page_id=PAGE_IDS["spcjs_xxfb"])
        items = self._parse(html)
        print(f"  [抽检司·信息发布] 解析到 {len(items)} 条")
        return items

    def _parse(self, html: str) -> list[dict]:
        items = []
        seen = set()
        for href, title, pub_date in parse_samr_articles(html):
            item_id = article_id_from_href(href, self.key)
            if item_id in seen:
                continue
            seen.add(item_id)
            items.append({
                "id": item_id,
                "title": title,
                "date": pub_date,
                "url": absolutize(href),
                "source": self.key,
                "source_name": self.name,
                "category": self._categorize(title),
            })
        return items

    def _categorize(self, title: str) -> str:
        for label, keywords in self.RULES:
            if any(k in title for k in keywords):
                return label
        return "其他公告"
