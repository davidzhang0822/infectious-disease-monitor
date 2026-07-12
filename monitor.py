#!/usr/bin/env python3
"""
传染病公文多源每日监测脚本

数据源：
  Tier 1 - 已接入:
    国家疾控局 ndcpa.gov.cn     防控方案、通知公告、政策解读
    中国疾控中心 chinacdc.cn    疫情月报、新冠月报、呼吸道哨点周报
  Tier 1 - 框架就绪（需 browser-act）:
    海关总署 customs.gov.cn      口岸疫情防控公告
    国家卫健委 nhc.gov.cn        诊疗方案、法定传染病目录调整

用法:
    python3 monitor.py                 # 全源检测，生成日报
    python3 monitor.py --init          # 初始化所有数据源
    python3 monitor.py --source ndcpa  # 只检测指定源
"""

import re
import json
import sys
from datetime import datetime, date
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR = SCRIPT_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

from sources import SeenStore, detect_new
from sources.ndcpa import NdcpaSource
from sources.chinacdc import ChinacdcSource
from sources.customs import CustomsSource
from sources.nhc import NHCSource


# ---- 数据源注册 ----
ALL_SOURCES = {
    "ndcpa": NdcpaSource(),
    "chinacdc": ChinacdcSource(),
    "customs": CustomsSource(),
    "nhc": NHCSource(),
}


def run_monitor(sources: dict, init_mode: bool = False):
    """执行多源监测"""
    store = SeenStore(DATA_DIR)
    all_data = store.load()
    all_new = {}

    # 初始化每个源
    for key in sources:
        src_data = all_data.get(key, {"ids": set(), "items": []})
        if isinstance(src_data["ids"], list):
            src_data["ids"] = set(src_data["ids"])
        all_data[key] = src_data

    # 逐个抓取
    for key, source in sources.items():
        print(f"\n{'='*50}")
        print(f"  [{source.name}] {source.key}")
        print(f"{'='*50}")

        try:
            items = source.fetch_items()
        except Exception as e:
            print(f"  [错误] 抓取失败: {e}")
            continue

        if not items:
            print(f"  未抓取到任何条目（可能被WAF拦截或页面结构变化）")
            continue

        print(f"  共获取 {len(items)} 条，最新3条:")
        for item in items[:3]:
            print(f"    [{item.get('date', '?')}] {item['title'][:60]}")

        # 检测新增
        new_items = detect_new(all_data, key, items)
        if new_items:
            print(f"  [新增] {len(new_items)} 条")
            all_new[key] = new_items
        else:
            print(f"  [无新增]")

    # 保存
    store.save(all_data)

    # 生成报告
    report_path = generate_report(all_new, all_data)
    return all_new, report_path


def generate_report(all_new: dict, all_data: dict) -> Path:
    """生成多源日报"""
    today_str = date.today().isoformat()
    report_path = REPORT_DIR / f"report_{today_str}.md"

    total_new = sum(len(v) for v in all_new.values())

    lines = [
        "# 传染病公文多源监测日报",
        "",
        f"**日期**: {today_str}",
        f"**监测时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**监测源数**: {len(ALL_SOURCES)}",
        f"**新增总计**: {total_new} 条",
        "",
        "---",
        "",
    ]

    if all_new:
        lines.append("## 新增内容")
        lines.append("")
        for key, items in all_new.items():
            src = ALL_SOURCES.get(key)
            src_name = src.name if src else key
            lines.append(f"### {src_name} ({len(items)}条)")
            lines.append("")
            for item in items:
                lines.append(f"- **[{item['title']}]({item['url']})**")
                lines.append(f"  - 来源: {item.get('source_name', '')} / {item.get('category', '')}")
                lines.append(f"  - 日期: {item.get('date', '未知')}")
                lines.append("")
    else:
        lines.append("## 今日无新增")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 各源最新动态")
    lines.append("")

    for key, src_data in all_data.items():
        src = ALL_SOURCES.get(key)
        src_name = src.name if src else key
        items = src_data.get("items", [])
        if items:
            lines.append(f"### {src_name}（最近{min(3, len(items))}条）")
            lines.append("")
            for item in items[:3]:
                date_str = item.get("date", "?")
                title = item["title"][:60]
                lines.append(f"| {date_str} | [{title}]({item['url']}) |")
            lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return report_path


def main():
    init_mode = "--init" in sys.argv

    # 确定启用哪些源
    active_sources = {}
    source_filter = None
    for i, arg in enumerate(sys.argv):
        if arg == "--source" and i + 1 < len(sys.argv):
            source_filter = sys.argv[i + 1]

    if source_filter:
        if source_filter in ALL_SOURCES:
            active_sources = {source_filter: ALL_SOURCES[source_filter]}
        else:
            print(f"未知数据源: {source_filter}")
            print(f"可用: {', '.join(ALL_SOURCES.keys())}")
            sys.exit(1)
    else:
        active_sources = ALL_SOURCES

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 传染病公文多源监测启动")
    print(f"  启用数据源: {', '.join(s.name for s in active_sources.values())}")
    print(f"  模式: {'初始化' if init_mode else '日常检测'}")

    new_items, report_path = run_monitor(active_sources, init_mode)

    print(f"\n{'='*50}")
    print(f"监测完成")
    total = sum(len(v) for v in new_items.values())
    print(f"  新增条目: {total} 条")
    for key, items in new_items.items():
        print(f"    {ALL_SOURCES[key].name}: {len(items)} 条")
    print(f"  报告: {report_path}")


if __name__ == "__main__":
    main()
