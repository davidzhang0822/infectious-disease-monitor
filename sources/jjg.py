"""国家计量技术规范全文公开系统（JJG）数据源

覆盖栏目（通过 JSON API 抓取，无需浏览器渲染）：
- 规范动态：最新上线(latest) / 最新被代替(current) / 最新废止(abolished)
- 公告：公告发布(publish) / 征求意见(opinion)

接口
----
    GET https://jjg.spc.org.cn/resmea/api/standard/dynamic/page
        ?kind={latest|current|abolished}&pageNum=1&pageSize=20
    → {total, rows:[{id, code, stdType, title, status,
                     publishDate, implementDate, modiDate}]}

    GET https://jjg.spc.org.cn/resmea/api/notices
        ?type={publish|opinion}&page=1
    → {items:[{id, ym, day, title, detailUrl, external}], total}

关于"即将实施"(upcoming)
-----------------------
不抓。实测全量重叠：latest∩upcoming = 95/115 —— 同一批规范因为尚未生效
会同时出现在两个列表，若同时监控会导致同一规范被报两次新增。而
latest∩current = latest∩abolished = current∩abolished = 0，即三个事件型
列表互斥，各代表一个独立事件（新发布 / 被代替 / 被废止），各报一次语义清晰。

日期字段
--------
- latest：用 publishDate（新规范的发布日）
- current：用 modiDate（代替的实际发生日）
- abolished：⚠️ 该列表的 modiDate 质量有问题 —— 实测全量 154 条中 86 条为空、
  62 条为占位值 2001-01-01（甚至早于规范自身的发布日期，逻辑上不成立），
  只有极少数条目带真实日期。因此 abolished 采用"多字段回退 + 有效性校验"：
  modiDate 若为空、为占位值、或早于 publishDate，则依次退回 publishDate，
  避免站点上出现"1991 年被废止"这种误导性排序。
分页
----
各列表 total 分别为 latest=176 / current=30 / abolished=154，单页取 20 条
不足以覆盖事件流，因此按 pageSize=50 逐页取全量（实测 4 次请求内完成，
总耗时约 1 秒）。条目 id 基于规范编号，重复抓取不会产生假新增。
"""

from urllib.parse import quote

from . import BaseSource, clean_text, sha1_id

JJG_BASE = "https://jjg.spc.org.cn/resmea"

# modiDate 的占位值：早于规范自身发布日期，逻辑上不成立
PLACEHOLDER_DATES = {"2001-01-01", "1900-01-01", "1970-01-01"}


class JjgSource(BaseSource):
    name = "国家计量技术规范全文公开系统"
    key = "jjg"

    # 规范动态：只监控事件型列表
    KINDS = [
        {"kind": "latest", "category": "最新上线", "date_field": "publishDate"},
        {"kind": "current", "category": "最新被代替", "date_field": "modiDate"},
        {"kind": "abolished", "category": "最新废止", "date_field": "modiDate"},
    ]

    # 公告与征求意见
    NOTICE_TYPES = [
        {"type": "publish", "category": "计量公告"},
        {"type": "opinion", "category": "征求意见"},
    ]

    def fetch_items(self) -> list[dict]:
        items = []

        for k in self.KINDS:
            try:
                rows = self._fetch_all_dynamic(k["kind"])
                got = self._parse_dynamic(rows, k)
                items.extend(got)
                print(f"  [JJG/{k['kind']}] 解析到 {len(got)} 条（接口总量 {len(rows)}）")
            except Exception as e:
                print(f"  [JJG/{k['kind']}] 失败: {e}")

        for t in self.NOTICE_TYPES:
            try:
                url = f"{JJG_BASE}/api/notices?type={t['type']}&page=1"
                data = self.fetch_json(url)
                got = self._parse_notices(data, t)
                items.extend(got)
                print(f"  [JJG/{t['type']}] 解析到 {len(got)} 条（total={data.get('total')}）")
            except Exception as e:
                print(f"  [JJG/{t['type']}] 失败: {e}")

        return items

    def _fetch_all_dynamic(self, kind: str) -> list[dict]:
        """分页取回某类规范动态的全部条目。

        单页 20 条不足以覆盖事件流（latest=176 / current=30 / abolished=154），
        按 pageSize=50 逐页取全量。
        """
        rows = []
        page = 1
        total = None
        while page <= 10:  # 上限保护，最多 10 页
            url = (f"{JJG_BASE}/api/standard/dynamic/page"
                   f"?kind={kind}&pageNum={page}&pageSize=50")
            data = self.fetch_json(url)
            batch = data.get("rows", [])
            if total is None:
                total = data.get("total", 0)
            if not batch:
                break
            rows.extend(batch)
            if len(rows) >= total:
                break
            page += 1
        return rows

    def _pick_date(self, r: dict, date_field: str) -> str:
        """选择条目的有效日期。

        modiDate 在"最新废止"列表中存在占位值（2001-01-01）与空值，且部分
        条目的 modiDate 早于规范自身发布日期（逻辑上不成立）。这类值一律
        视为无效，依次回退到 publishDate、implementDate。

        回退到 publishDate 的语义：废止事件的真实发生日不可考，退而使用
        该规范的发布日期作为排序依据。这在"最新废止"列表中会表现为若干
        较早年份，属预期行为（该批规范本就是早年发布的老标准），而非数据
        错误——真正的"废止发生日"仅对少数带有效 modiDate 的条目可得。
        """
        publish = r.get("publishDate") or ""
        for field in (date_field, "publishDate", "implementDate"):
            value = (r.get(field) or "").strip()
            if not value:
                continue
            if value in PLACEHOLDER_DATES:
                continue
            # 变更日期早于发布日期 → 判为无效数据
            if field != "publishDate" and publish and value < publish:
                continue
            return value
        return publish

    def _parse_dynamic(self, rows: list[dict], k: dict) -> list[dict]:
        items = []
        for r in rows:
            code = (r.get("code") or "").strip()
            if not code:
                continue
            # 规范编号是业务主键，稳定且唯一
            item_id = f"{self.key}_{k['kind']}_{code.replace(' ', '')}"
            title = f"{code} {r.get('title', '')}".strip()
            items.append({
                "id": item_id,
                "title": title,
                "date": self._pick_date(r, k["date_field"]),
                "url": f"{JJG_BASE}/standard/detail.html?standno={quote(code)}",
                "source": self.key,
                "source_name": self.name,
                "category": k["category"],
            })
        return items

    def _parse_notices(self, data: dict, t: dict) -> list[dict]:
        items = []
        for it in data.get("items", []):
            title = clean_text(it.get("title", ""))
            if not title:
                continue
            # 日期由 ym("2026.10") + day("08") 拼接
            ym = (it.get("ym") or "").replace(".", "-")
            day = (it.get("day") or "").zfill(2)
            date = f"{ym}-{day}" if ym and day else ""

            detail = it.get("detailUrl") or ""
            if it.get("external"):
                # 公告正文在 samr.gov.cn（external 标记），detailUrl 已是绝对地址
                url = detail
            else:
                url = f"{JJG_BASE}{detail}" if detail.startswith("/") else detail

            api_id = it.get("id")
            item_id = (f"{self.key}_notice_{t['type']}_{api_id}" if api_id
                       else f"{self.key}_notice_{t['type']}_{sha1_id(title)}")

            items.append({
                "id": item_id,
                "title": title,
                "date": date,
                "url": url,
                "source": self.key,
                "source_name": self.name,
                "category": t["category"],
            })
        return items
