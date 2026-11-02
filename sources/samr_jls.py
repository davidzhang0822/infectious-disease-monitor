"""国家市场监督管理总局 · 计量司 数据源

覆盖栏目：通知公告（jls/tzgg）
内容：国家计量技术规范发布公告、检定规程/校准规范发布、国家计量比对结果通报

对实验室的价值：
- 计量技术规范发布公告 → 仪器检定/校准依据更新，需同步作业指导书
- 国家计量比对结果通报 → 可评估本实验室在本领域同类机构中的水平定位
"""

from . import BaseSource
from .samr_common import (
    PAGE_IDS,
    absolutize,
    article_id_from_href,
    fetch_samr_column,
    parse_samr_articles,
)


class SamrJlsSource(BaseSource):
    name = "市场监管总局·计量司"
    key = "samr_jls"

    LIST_URL = "https://www.samr.gov.cn/jls/tzgg/index.html"

    # 分类关键词，按优先级顺序匹配
    RULES = [
        ("计量比对结果", ["计量比对", "比对结果"]),
        ("计量技术规范公告", ["计量技术规范", "检定规程", "校准规范", "型评大纲"]),
        ("计量基准/标准物质", ["国家计量基准", "标准物质"]),
    ]

    # 历史基线公告：jpaas 接口比普通页面更易受网关策略变更影响，
    # 保底保证站点卡片不为空。id 规则必须与实时解析完全一致
    # （article_id_from_href），否则同一 URL 会出现两个 id。
    SEED_ITEMS = [
        {
            "id": "samr_jls_0a62fbbf2a74441c8539614ef76b9c43",
            "title": "市场监管总局关于发布《容量计量器具检定系统表》等20项国家计量技术规范的公告",
            "date": "2026-10-08",
            "url": "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/jls/art/2026/"
                   "art_0a62fbbf2a74441c8539614ef76b9c43.html",
            "source": "samr_jls", "source_name": "市场监管总局·计量司",
            "category": "计量技术规范公告",
        },
        {
            "id": "samr_jls_c7c9501b96064e17a6078cc5fbe23792",
            "title": "市场监管总局关于发布《医用电子加速器辐射源检定规程》等65项国家计量技术规范的公告",
            "date": "2026-09-04",
            "url": "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/jls/art/2026/"
                   "art_c7c9501b96064e17a6078cc5fbe23792.html",
            "source": "samr_jls", "source_name": "市场监管总局·计量司",
            "category": "计量技术规范公告",
        },
    ]

    def fetch_items(self) -> list[dict]:
        items = []
        try:
            html = fetch_samr_column(self.LIST_URL, page_size=20,
                                     fallback_page_id=PAGE_IDS["jls_tzgg"])
            items = self._parse(html)
            print(f"  [计量司·通知公告] 解析到 {len(items)} 条")
        except Exception as e:
            print(f"  [计量司·通知公告] 抓取失败: {e}")

        # 合并历史基线（去重，保持实时数据优先）
        seen_ids = {it["id"] for it in items}
        for seed in self.SEED_ITEMS:
            if seed["id"] not in seen_ids:
                items.append(seed)
                seen_ids.add(seed["id"])
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
        return "其他通知"
