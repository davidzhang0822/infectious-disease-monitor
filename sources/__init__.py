"""传染病监测数据源基类"""

import re
import json
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


class BaseSource(ABC):
    """监测源基类"""

    name: str = ""
    key: str = ""

    @abstractmethod
    def fetch_items(self) -> list[dict]:
        """抓取并返回条目列表 [{id, title, date, url, source}]"""
        pass

    def fetch_html(self, url: str) -> str:
        """通用 HTML 抓取"""
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text


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
                    }
                return result
        return {}

    def save(self, store: dict):
        """保存全部数据"""
        serializable = {}
        for key, data in store.items():
            serializable[key] = {
                "ids": list(data["ids"]),
                "items": sorted(data["items"], key=lambda x: x.get("date", ""), reverse=True),
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
