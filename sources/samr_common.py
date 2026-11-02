"""SAMR（国家市场监督管理总局）jpaas CMS 列表抓取共享工具。

⚠️ 本模块只放模块级函数，**绝不能定义带 `key` 属性的 BaseSource 子类**——
monitor.py 的 discover_sources() 会扫描 sources/ 下的每个模块，把所有
「继承 BaseSource 且有 key」的类注册为数据源。混入基类会导致幽灵源。

站点结构
--------
samr.gov.cn 使用 jpaas CMS，列表数据由 AJAX 异步加载，直接抓列表页 HTML
拿不到条目。但每个列表页 HTML 里嵌了一个 script 标签，携带渲染该列表所需的
参数：

    <script id="32位hex" src="..." webId="32位hex" parseType="bulidstatic"
            url="/api-gateway/jpaas-publish-server/front/page/build/unit"
            queryData="{'parseType':'bulidstatic',...}"></script>

拿到参数后调用 jpaas API，响应的 data.html 字段就是渲染好的列表 HTML。

实测要点
--------
- 该 API **只接受 GET**（POST 返回 500 "不支持的HTTP方法"）
- pageSize 支持到 99，pageNo 有效（2/3/4/5 各返回不同批次）
- 四个目标栏目共用同一 webId / tplSetId，仅 pageId 不同
"""

import json
import re

import requests

SAMR_BASE = "https://www.samr.gov.cn"
SAMR_API = f"{SAMR_BASE}/api-gateway/jpaas-publish-server/front/page/build/unit"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0.0.0 Safari/537.36")

# 列表页抓取失败时的兜底常量（实测四栏目共用，仅 pageId 不同）
CACHED_WEB_ID = "29e9522dc89d4e088a953d8cede72f4c"
CACHED_TPL_SET_ID = "5c30fb89ae5e48b9aefe3cdf49853830"

# 实测的 pageId（列表页解析失败时可作为二级兜底）
PAGE_IDS = {
    "spcjs_xxfb": "6695899db9f8455187259c43b72d2e1c",
    "jls_tzgg": "17c1340968d64aa1a9fee47c32609bea",
    "spcjs_bcjyff": "a95cec2d7bde4c908af214e792047dae",
    "spcjs_ksjcff": "f63c380ea3664459b7b21b6f7965b306",
}


def _unescape(s: str) -> str:
    """还原 HTML 实体（queryData 属性里的引号被转义成 &apos; &quot; 等）。"""
    return (s.replace("&apos;", "'").replace("&quot;", '"')
             .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))


def fetch_samr_column(list_url: str, page_no: int = 1, page_size: int = 20,
                       timeout: int = 30, fallback_page_id: str = None) -> str:
    """抓取 SAMR 某个栏目的渲染后列表 HTML。

    流程：GET 列表页 → 解析 webId/tplSetId/pageId → GET jpaas API → 返回 data.html。

    列表页解析失败时退回到缓存常量（若提供了 fallback_page_id）。
    """
    web_id, tpl_set_id, page_id = CACHED_WEB_ID, CACHED_TPL_SET_ID, None

    try:
        resp = requests.get(list_url, timeout=timeout, headers={"User-Agent": UA})
        resp.raise_for_status()
        resp.encoding = "utf-8"
        m = re.search(r'queryData="([^"]+)"', resp.text)
        if m:
            params = dict(re.findall(r"'([^']+)':'([^']*)'", _unescape(m.group(1))))
            web_id = params.get("webId", web_id)
            tpl_set_id = params.get("tplSetId", tpl_set_id)
            page_id = params.get("pageId")
    except Exception as e:
        print(f"  [SAMR] 列表页获取失败，使用缓存参数: {e}")

    if not page_id:
        page_id = fallback_page_id
    if not page_id:
        raise RuntimeError(f"无法确定 SAMR 栏目 pageId: {list_url}")

    query = {
        "parseType": "bulidstatic",
        "webId": web_id,
        "tplSetId": tpl_set_id,
        "pageType": "column",
        "tagId": "ajax分页",
        "editType": "null",
        "pageId": page_id,
        "paramJson": json.dumps({"pageNo": page_no, "pageSize": page_size, "search": ""}),
    }
    headers = {
        "User-Agent": UA,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": list_url,
    }
    resp = requests.get(SAMR_API, params=query, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["data"]["html"]


def parse_samr_articles(html: str, base: str = SAMR_BASE):
    """解析 SAMR 栏目列表项。

    列表项结构（实测）：
        <li class="content-3-left-text imgContent01new">
          <a href="/spcjs/xxfb/art/2026/art_xxx.html" title="标题">标题</a>
          <div class="contentRight01time">2026-09-28</div>
        </li>

    日期在 contentRight01time 字段，已与详情页"发布时间：2026-09-28 16:30"核对一致。

    产出 (href, title, date) 三元组列表；标题已清洗（去换行与全角空格）。
    """
    from . import clean_text

    pattern = re.compile(
        r'<a\s+href="([^"]+)"[^>]*title="([^"]*)"[^>]*>.*?</a>\s*'
        r'<div class="contentRight01time">(\d{4}-\d{2}-\d{2})</div>',
        re.S,
    )
    out = []
    for m in pattern.finditer(html):
        href, raw_title, pub_date = m.group(1), m.group(2), m.group(3)
        title = clean_text(raw_title)
        if not title:
            continue
        out.append((href, title, pub_date))
    return out


def article_id_from_href(href: str, prefix: str) -> str:
    """从 SAMR 文章 URL 提取稳定 id。

    URL 形如 /spcjs/xxfb/art/2026/art_<32位hex>.html，其中的 CMS id 稳定不变，
    是最可靠的唯一标识；取不到时退回 URL 哈希。
    """
    from . import sha1_id

    art = re.search(r"art_([0-9a-f]{32})", href)
    if art:
        return f"{prefix}_{art.group(1)}"
    return f"{prefix}_{sha1_id(href)}"


def absolutize(href: str, base: str = SAMR_BASE) -> str:
    """把站内相对路径转成绝对 URL。"""
    return href if href.startswith("http") else base + href
