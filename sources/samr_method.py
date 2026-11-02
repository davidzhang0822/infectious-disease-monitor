"""国家市场监督管理总局 · 食品检验方法库 数据源

覆盖两个方法库（同一套表结构、同一发布方、同一更新节奏，故合并为一个源，
用 category 区分）：
- 食品补充检验方法数据库（BJS）：samr.gov.cn/spcjs/bcjyff/
- 食品快速检测方法数据库（KJ）：samr.gov.cn/spcjs/ksjcff/

为什么重要：
- BJS 是国标方法未覆盖项目时**唯一合法的检测依据**，依据其出具的报告
  可直接用于食品安全监督执法
- KJ 用于现场快速筛查，阳性结果须实验室确证，不可直接作为执法依据
- 两者都需关注方法废止动态，避免用已废止方法出具报告

条目结构（实测）：
    <div class="listcon">
      <div class="xh">1</div>
      <div class="ffmc">方法名称</div>
      <div class="bzbh">BJS 202606</div>
      <div class="ggh">2026年第24号</div>
      <div class="gbrq">2026-07-16</div>
      <div class="ffxz"><a href="/cms_files/.../xxx.pdf">下载</a></div>
    </div>

注意：
- 方法库只有 PDF 直链、没有详情页，url 直接指向 PDF（可直接下载方法文本）
- bzbh 有约 10% 为空（"第1号修改单"类，标准号写在 ffmc 里），
  故 id 必须用「库名|标准号|方法名」三元组生成
"""

import re

from . import BaseSource, sha1_id
from .samr_common import PAGE_IDS, absolutize, fetch_samr_column


class SamrMethodSource(BaseSource):
    name = "市场监管总局·食品检验方法库"
    key = "samr_method"

    DATABASES = [
        {"db": "BJS", "category": "食品补充检验方法",
         "url": "https://www.samr.gov.cn/spcjs/bcjyff/",
         "page_id": PAGE_IDS["spcjs_bcjyff"]},
        {"db": "KJ", "category": "食品快速检测方法",
         "url": "https://www.samr.gov.cn/spcjs/ksjcff/",
         "page_id": PAGE_IDS["spcjs_ksjcff"]},
    ]

    def fetch_items(self) -> list[dict]:
        items = []
        for d in self.DATABASES:
            try:
                html = fetch_samr_column(d["url"], page_size=20,
                                         fallback_page_id=d["page_id"])
                got = self._parse(html, d)
                items.extend(got)
                print(f"  [{d['db']} 方法库] 解析到 {len(got)} 条")
            except Exception as e:
                print(f"  [{d['db']} 方法库] 抓取失败: {e}")
        return items

    def _parse(self, html: str, d: dict) -> list[dict]:
        from . import clean_text

        items = []
        seen = set()

        # 按 listcon 切块比整块正则更稳（实测 20/20 解析成功）
        for blk in html.split('<div class="listcon">')[1:]:
            def field(cls):
                m = re.search(r'<div class="%s">(.*?)</div>' % cls, blk, re.S)
                return clean_text(m.group(1)) if m else ""

            ffmc = field("ffmc")     # 方法名称
            bzbh = field("bzbh")     # 标准编号（可能为空）
            ggh = field("ggh")       # 公告号
            gbrq = field("gbrq")     # 公布日期

            pdf = re.search(r'<div class="ffxz"[^>]*>.*?<a href="([^"]+)"', blk, re.S)
            if not ffmc or not pdf:
                continue

            # id 用三元组：库名 + 标准号 + 方法名（标准号可能为空）
            item_id = f"{self.key}_{d['db']}_{sha1_id(d['db'], bzbh, ffmc)}"
            if item_id in seen:
                continue
            seen.add(item_id)

            title = f"{bzbh} {ffmc}".strip() if bzbh else ffmc
            if ggh:
                title = f"{title}（{ggh}）"

            items.append({
                "id": item_id,
                "title": title,
                "date": gbrq,
                "url": absolutize(pdf.group(1)),
                "source": self.key,
                "source_name": self.name,
                "category": d["category"],
            })

        return items
