"""国家食品安全风险评估中心（CFSA）数据源

覆盖栏目：
- 标准工作动态（spaqbz/bzgzdt）：食品安全国家标准的制修订动态、征求意见、
  问卷调查 —— 这是检验方法标准更新的一手信号
- 食品安全国家标准目录（spaqbz/spaqgjbz/spaqgjbz）：现行食安国标目录

不接 CFSA「通知公告」栏目：实测该栏目 5 条全部是招聘公告，无检验相关价值。

解析要点
--------
⚠️ 必须先切出 `<ul class="news-list">…</ul>` 再解析。
CFSA 页面顶部另有一个 article-list 轮播区，内含 2020-05-14 的旧条目；
若对全页做正则会把这类陈旧内容混进来（实测 news-list 内 20 条为 2024–2025
年，article-list 那条为 2020 年）。

列表项结构（实测）：
    <li>
      <div><i class="circular"></i>
        <a href="/spaqbz/bzgzdt/2025/15299.shtml" title="标题">标题</a>
      </div>
      <span>2025-07-03</span>
    </li>

日期在 `</div>` 之后、`<span>` 之内，不在 `<a>` 内。

证书
----
www.cfsa.net.cn 多节点证书轮换不一致，部分节点叶证书已过期，严格校验会
随机抛 SSLError。已加入 sources/__init__.py 的 INSECURE_HOSTS 白名单，
由 fetch_html 自动降级重试。
"""

import re

from . import BaseSource, clean_text, sha1_id

CFSA_BASE = "https://www.cfsa.net.cn"


class CfsaSource(BaseSource):
    name = "国家食品安全风险评估中心"
    key = "cfsa"

    CHANNELS = [
        {"category": "标准制修订动态",
         "url": f"{CFSA_BASE}/spaqbz/bzgzdt/index.shtml"},
        {"category": "食品安全国家标准目录",
         "url": f"{CFSA_BASE}/spaqbz/spaqgjbz/spaqgjbz/index.shtml"},
    ]

    def fetch_items(self) -> list[dict]:
        items = []
        for ch in self.CHANNELS:
            try:
                html = self.fetch_html(ch["url"])
                got = self._parse(html, ch)
                items.extend(got)
                print(f"  [CFSA/{ch['category']}] 解析到 {len(got)} 条")
            except Exception as e:
                print(f"  [CFSA/{ch['category']}] 失败: {e}")
        return items

    def _parse(self, html: str, ch: dict) -> list[dict]:
        # 只取正文列表区，排除顶部轮播
        m = re.search(r'<ul class="news-list">(.*?)</ul>', html, re.S)
        if not m:
            print(f"  [CFSA/{ch['category']}] 未找到 news-list 区块")
            return []
        block = m.group(1)

        rows = re.findall(
            r'<li>[\s\S]{0,400}?<a href="([^"]+)"[^>]*title="([^"]*)"[^>]*>'
            r'[\s\S]{0,200}?</a>[\s\S]{0,120}?<span>(\d{4}-\d{2}-\d{2})</span>',
            block,
        )

        items = []
        seen = set()
        for href, raw_title, pub_date in rows:
            title = clean_text(raw_title)
            if not title:
                continue

            url = href if href.startswith("http") else CFSA_BASE + href
            num = re.search(r"/(\d+)\.shtml", href)
            item_id = (f"{self.key}_{num.group(1)}" if num
                       else f"{self.key}_{sha1_id(url)}")
            if item_id in seen:
                continue
            seen.add(item_id)

            # 征求意见类单独归类，这是实验室可以参与标准制修订的信号
            category = ch["category"]
            if "征求意见" in title or "问卷" in title or "意见" in title:
                category = "标准征求意见"

            items.append({
                "id": item_id,
                "title": title,
                "date": pub_date,
                "url": url,
                "source": self.key,
                "source_name": self.name,
                "category": category,
            })
        return items
