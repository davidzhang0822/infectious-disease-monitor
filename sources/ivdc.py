"""国家流感中心（IVDC）数据源

覆盖栏目：
- lgzb: 流感监测周报（每周一期，核心数据）
- lggzdt: 工作动态（疫苗组分推荐、技术指南、会议通知等）
"""

import re
from . import BaseSource


class IvdcSource(BaseSource):
    name = "国家流感中心"
    key = "ivdc"

    BASE_URL = "https://ivdc.chinacdc.cn/cnic"

    CHANNELS = [
        {
            "name": "流感监测周报",
            "url": f"{BASE_URL}/zyzx/lgzb/",
            "url_pattern": r"zyzx/lgzb/(\d{{6}})/t(\d{{8}})_(\d+)\.htm",
        },
        {
            "name": "工作动态",
            "url": f"{BASE_URL}/lggzdt/",
            "url_pattern": r"lggzdt/(\d{{6}})/t(\d{{8}})_(\d+)\.htm",
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
        """解析 IVDC 列表页 HTML

        周报列表结构：
          <li><span class="span_01"><a href="202608/t20260827_1839553.htm">2026 第34周</a></span><span class="span_02">(2026-08-27)</span></li>

        工作动态结构：
          <li>MM-YYYY<a href="...">标题</a></li>
        """
        items = []
        seen = set()

        if channel["name"] == "流感监测周报":
            items = self._parse_weekly(html, channel, seen)
        else:
            items = self._parse_work_dynamic(html, channel, seen)

        return items

    def _parse_weekly(self, html: str, channel: dict, seen: set) -> list[dict]:
        """解析流感周报列表

        实际HTML结构：
          <li><span class="span_01"><a href="./202608/t20260821_1839077.htm">2026 第33周</a></span>
              <span class="span_02">(2026-08-20)</span></li>
        """
        items = []
        # 匹配：href="./YYYYMM/tYYYYMMDD_ID.htm">标题</a> ... <span...>(YYYY-MM-DD)
        pattern = re.compile(
            r'<a\s+href="([^"]*t(\d{8})_(\d+)\.htm)"[^>]*>'
            r'([^<]+)'
            r'</a>.*?'
            r'<span[^>]*class="[^"]*span_02[^"]*"[^>]*>\((\d{4}-\d{2}-\d{2})\)',
            re.DOTALL,
        )

        for m in pattern.finditer(html):
            url_path = m.group(1)
            date_in_url = m.group(2)
            item_id = f"ivdc_w_{m.group(3)}"

            if item_id in seen:
                continue
            seen.add(item_id)

            title = m.group(4).strip()
            pub_date = m.group(5)

            full_url = f"{self.BASE_URL}/zyzx/lgzb/{url_path}"

            items.append({
                "id": item_id,
                "title": title,
                "date": pub_date,
                "url": full_url,
                "source": self.key,
                "source_name": self.name,
                "category": channel["name"],
            })

        return items

    def _parse_work_dynamic(self, html: str, channel: dict, seen: set) -> list[dict]:
        """解析工作动态列表

        <li>MM-YYYY<a href="202602/t20260227_315222.htm">标题</a></li>
        日期需要从 URL 路径中提取或从邻近文本推断
        """
        items = []
        # 匹配：<a href="YYYYMM/tYYYYMMDD_ID.htm">标题</a>
        pattern = re.compile(
            r'<a\s+href="([^"]*t(\d{8})_(\d+)\.htm)"[^>]*>'
            r'([^<]+)'
            r'</a>',
            re.DOTALL,
        )

        for m in pattern.finditer(html):
            url_path = m.group(1)
            date_in_url = m.group(2)
            item_id = f"ivdc_d_{m.group(3)}"

            if item_id in seen:
                continue
            seen.add(item_id)

            raw_title = m.group(4).strip()

            # 从 URL 中的日期推断发布日期 (YYYYMMDD -> YYYY-MM-DD)
            try:
                pub_date = f"{date_in_url[:4]}-{date_in_url[4:6]}-{date_in_url[6:8]}"
            except (IndexError, ValueError):
                pub_date = ""

            full_url = f"{self.BASE_URL}/lggzdt/{url_path}"

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
