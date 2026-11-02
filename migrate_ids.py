#!/usr/bin/env python3
"""一次性数据迁移：修复 nhc 源因 abs(hash(url)) 导致的 id 跨进程不稳定问题。

背景
----
旧代码用 `abs(hash(url_path))` 生成条目 id。Python 字符串 hash 受
PYTHONHASHSEED 影响，每个进程都不同 → 同一篇公文每次运行都算出不同 id
→ 每次都被 detect_new 判为"新增"。

线上表现：data/all_items.json 中 nhc 有 22 条 items 但只有 6 个唯一 URL；
data/latest_updates.json 在 2026-09-15 那天的内容全是国家卫健委的假新增。

修复
----
1. 把 id 重算为 sha1(url_path) 前 12 位（跨进程、跨机器一致）
2. 按 url 去重，历史重复项只保留一条
3. 同步 ids 集合；seed 项保持原 id 不变

用法
----
    python3 migrate_ids.py            # 执行迁移
    python3 migrate_ids.py --dry-run  # 只打印不写盘

注意：必须在修改 nhc.py 之前执行，否则改完代码第一次跑会把全部历史
条目判为新增，一次性灌进站点"最新更新"栏目。
"""

import hashlib
import json
import pathlib
import re
import sys

DATA_FILE = pathlib.Path(__file__).parent / "data" / "all_items.json"


def sha1_id(s: str) -> str:
    """稳定 id：sha1 前 12 位，跨进程跨机器一致。"""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def url_to_id_part(url: str) -> str:
    """从 URL 提取参与 id 计算的路径部分。

    nhc.py 中 item_id = f"nhc_{sha1_id(url_path)}"，url_path 是站内相对路径，
    这里必须用同样的字符串，否则迁移后的 id 与新代码算出来的不一致。
    """
    m = re.search(r"(/[^ ]+\.shtml)$", url)
    return m.group(1) if m else url


def migrate_nhc(data: dict, dry_run: bool = False) -> tuple[int, int]:
    """迁移 nhc 源的 id 并按 url 去重，返回 (id变更数, 去重删除数)。"""
    src = data.get("nhc")
    if not src:
        print("  nhc 源不存在，跳过")
        return 0, 0

    items = src.get("items", [])
    before = len(items)
    changed = 0

    # 1) 重算 id
    for it in items:
        old = it.get("id", "")
        if old.startswith("nhc_seed_"):
            continue  # seed 项 id 不参与 hash 逻辑，保持不变
        new = f"nhc_{sha1_id(url_to_id_part(it.get('url', '')))}"
        if new != old:
            it["id"] = new
            changed += 1

    # 2) 按 url 去重（保留首次出现的）
    seen_urls = set()
    kept = []
    for it in items:
        url = it.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)
        kept.append(it)

    removed = before - len(kept)

    # 3) 同步 ids 集合：保留 kept 的新 id + 所有 seed id
    #    注意 ids 不可随意截断，否则历史条目会被重新判为新增
    seed_ids = {i for i in src.get("ids", []) if i.startswith("nhc_seed_")}
    new_ids = {it["id"] for it in kept} | seed_ids

    print(f"  nhc: items {before} -> {len(kept)}（去重 -{removed}），"
          f"id 重算 {changed} 条，ids 集合 {len(src.get('ids', []))} -> {len(new_ids)}")

    if not dry_run:
        src["items"] = kept
        src["ids"] = sorted(new_ids)

    return changed, removed


def main():
    dry_run = "--dry-run" in sys.argv

    if not DATA_FILE.exists():
        print(f"数据文件不存在: {DATA_FILE}")
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    print(f"{'[试运行]' if dry_run else '[执行]'} 迁移 {DATA_FILE}")
    migrate_nhc(data, dry_run=dry_run)

    if dry_run:
        print("\n试运行模式，未写入文件。加 --dry-run 去掉即可执行。")
        return

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n迁移完成，已写入文件。")


if __name__ == "__main__":
    main()
