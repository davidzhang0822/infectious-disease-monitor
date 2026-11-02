"""传染病监测数据源基类"""

import re
import json
import html
import hashlib
import requests
from datetime import datetime
from pathlib import Path
from abc import ABC, abstractmethod

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 证书校验需降级的域名白名单。
#
# 背景：www.cfsa.net.cn 多节点证书轮换不一致，部分节点的叶证书已于
# 2026-09-14 过期，导致严格校验时随机抛 SSLError（实测 10 次采样失败 2 次）。
# 这是服务端证书的事实，与运行环境 CA bundle 是否新鲜无关，CI 上同样会失败。
#
# 策略：默认严格校验，仅当校验失败且域名在白名单内时降级重试一次，
# 并打印醒目日志。站点一旦修复证书，代码会自动回到严格模式，无需改代码。
INSECURE_HOSTS = {
    "www.cfsa.net.cn",
}


def _is_insecure(url: str) -> bool:
    """判断 URL 的主机是否在证书降级白名单内。"""
    from urllib.parse import urlparse
    return urlparse(url).hostname in INSECURE_HOSTS


def _disable_ssl_warnings():
    """屏蔽 urllib3 的证书告警（仅在确实降级时调用）。"""
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass


def sha1_id(*parts) -> str:
    """生成稳定条目 id：sha1 前 12 位，跨进程、跨机器一致。

    ⚠️ 禁止使用 abs(hash(...))：Python 字符串 hash 受 PYTHONHASHSEED 影响，
    每个进程都不同，会导致同一条目每次都被判为"新增"。
    """
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def clean_text(s: str) -> str:
    """清洗 HTML 文本：去标签、解实体、压空白（含全角空格与不换行空格）。

    部分政府站点的 title 属性里带真实换行符与全角空格，直接使用会导致
    标题在站点上显示错乱。
    """
    if not s:
        return ""
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


class BaseSource(ABC):
    """监测源基类"""

    name: str = ""
    key: str = ""

    @abstractmethod
    def fetch_items(self) -> list[dict]:
        """抓取并返回条目列表 [{id, title, date, url, source}]"""
        pass

    def fetch_html(self, url: str, timeout: int = 30, verify: bool = True) -> str:
        """通用 HTML 抓取。

        证书严格校验失败时，对白名单域名降级重试一次。
        """
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=verify)
        except requests.exceptions.SSLError:
            if not _is_insecure(url):
                raise
            print(f"  [SSL] {url} 证书校验失败，降级重试（不校验证书）")
            _disable_ssl_warnings()
            resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    def fetch_json(self, url: str, timeout: int = 30, verify: bool = True) -> dict:
        """通用 JSON 抓取（JJG 等提供 JSON 接口的站点使用）。

        证书严格校验失败时，对白名单域名降级重试一次。
        """
        headers = dict(HEADERS)
        headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, verify=verify)
        except requests.exceptions.SSLError:
            if not _is_insecure(url):
                raise
            print(f"  [SSL] {url} 证书校验失败，降级重试（不校验证书）")
            _disable_ssl_warnings()
            resp = requests.get(url, headers=headers, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.json()


class SeenStore:
    """跨数据源的统一记录存储"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(exist_ok=True)
        self._file = self.data_dir / "all_items.json"

    def load(self) -> dict:
        """{source_key: {ids: set, items: list}}"""
        if self._file.exists():
            with open(self._file, "r", encoding="utf-8") as f:
                raw = json.load(f)
                result = {}
                for key, data in raw.items():
                    result[key] = {
                        "ids": set(data.get("ids", [])),
                        "items": data.get("items", []),
                        "last_update": data.get("last_update", ""),
                    }
                return result
        return {}

    def save(self, store: dict):
        """保存全部数据。

        items 按日期倒序并截断到最近 MAX_ITEMS 条以控制文件体积；
        ⚠️ ids 集合绝不截断 —— 一旦截断，被丢弃的条目会被重新判为新增。
        """
        MAX_ITEMS = 500
        serializable = {}
        for key, data in store.items():
            items = sorted(data["items"], key=lambda x: x.get("date", ""), reverse=True)
            serializable[key] = {
                "ids": list(data["ids"]),
                "items": items[:MAX_ITEMS],
                "last_update": datetime.now().isoformat(),
            }
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)


def detect_new(store: dict, source_key: str, items: list[dict]) -> list[dict]:
    """检测新增条目"""
    src = store.get(source_key, {"ids": set(), "items": []})
    seen = src["ids"]
    new = []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            src["items"].append(item)
            new.append(item)
    store[source_key] = src
    return new
