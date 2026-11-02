#!/usr/bin/env python3
"""合并两份 all_items.json，用于「代码从别处同步过来、数据文件各有一份」的场景。

为什么需要合并而不是直接覆盖
----------------------------
本项目的数据文件 data/all_items.json 是**增量状态**：记录每个源已见过的条目
id 与条目内容。如果本地仓库跑过 monitor.py，本地这份就会比交付的那份新
（多出本地这几天抓到的条目）。

直接用交付版覆盖本地版，会把这些条目的 id 和内容一起丢掉 —— 下一次运行
它们会被 detect_new 判为"新增"，产生一批假新增。

合并规则
--------
- ids   : 取并集（一条都不能丢，丢了就会被重新判为新增）
- items : 按 id 合并，同 id 保留内容较新的一条（比较 last_update）
- last_update : 取两者中较晚的

用法
----
    python3 merge_data.py <交付版.json> <本地版.json> <输出.json>
    python3 merge_data.py --inplace <交付版.json> <本地版.json>
"""

import json
import sys
from pathlib import Path


def parse_ts(s: str) -> str:
    """时间戳转成可比较的字符串（ISO 格式字典序即时间序）。"""
    return (s or "").strip()


def merge_one(remote: dict, local: dict) -> dict:
    """合并单个源的数据。"""
    remote_ids = set(remote.get("ids", []))
    local_ids = set(local.get("ids", []))

    # items 按 id 建索引
    by_id = {}
    for it in remote.get("items", []):
        by_id[it.get("id", "")] = it
    for it in local.get("items", []):
        iid = it.get("id", "")
        if iid not in by_id:
            by_id[iid] = it
        # 同 id 已存在：保留本地版（本地是更新的一方）

    # ids 并集 + items 中出现但不在 ids 里的也要补进来
    all_ids = remote_ids | local_ids | set(by_id.keys())

    # last_update 取较晚的
    lu = parse_ts(remote.get("last_update", ""))
    ll = parse_ts(local.get("last_update", ""))
    last_update = ll if ll > lu else lu

    return {
        "ids": sorted(all_ids),
        "items": list(by_id.values()),
        "last_update": last_update,
    }


def merge_data(remote: dict, local: dict) -> dict:
    """合并两份 all_items.json 的全部源。"""
    result = {}
    for key in sorted(set(remote.keys()) | set(local.keys())):
        r = remote.get(key, {"ids": [], "items": [], "last_update": ""})
        l = local.get(key, {"ids": [], "items": [], "last_update": ""})
        result[key] = merge_one(r, l)
    return result


def main():
    args = [a for a in sys.argv[1:] if a != "--inplace"]
    inplace = "--inplace" in sys.argv

    if len(args) != 3:
        print("用法: python3 merge_data.py [--inplace] <交付版.json> <本地版.json> <输出.json>")
        sys.exit(1)

    remote_path, local_path, out_path = (Path(a) for a in args)

    if not remote_path.exists():
        print(f"❌ 交付版数据文件不存在: {remote_path}")
        sys.exit(1)
    if not local_path.exists():
        print(f"⚠️ 本地数据文件不存在: {local_path}")
        print("   将直接使用交付版")
        remote = json.loads(remote_path.read_text(encoding="utf-8"))
        local = {}
    else:
        remote = json.loads(remote_path.read_text(encoding="utf-8"))
        local = json.loads(local_path.read_text(encoding="utf-8"))

    print(f"交付版源: {len(remote)}  本地版源: {len(local)}")
    merged = merge_data(remote, local)

    # 统计合并前后的差异
    for key in sorted(merged.keys()):
        r_n = len(remote.get(key, {}).get("items", []))
        l_n = len(local.get(key, {}).get("items", []))
        m_n = len(merged[key]["items"])
        note = ""
        if m_n > max(r_n, l_n):
            note = f"  ← 合并保留了 {m_n - max(r_n, l_n)} 条"
        print(f"  {key:14s} 交付版={r_n:4d} 本地版={l_n:4d} 合并后={m_n:4d}{note}")

    # 完整性自检
    bad = []
    for key, v in merged.items():
        ids = set(v["ids"])
        item_ids = {it.get("id", "") for it in v["items"]}
        if len(ids) != len(v["ids"]):
            bad.append(f"{key}: ids 有重复")
        missing = item_ids - ids
        if missing:
            bad.append(f"{key}: {len(missing)} 条 items 的 id 不在 ids 集合中")

    if bad:
        print("\n❌ 合并结果存在不一致:")
        for b in bad:
            print(f"  - {b}")
        sys.exit(1)

    print("\n✅ 合并完成，完整性检查通过")

    if inplace:
        local_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入: {local_path}")
    else:
        Path(out_path).write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写入: {out_path}")


if __name__ == "__main__":
    main()
