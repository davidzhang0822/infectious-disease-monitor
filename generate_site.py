#!/usr/bin/env python3
"""生成 GitHub Pages 静态站点，展示最近7天的监测报告。"""

import json
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

DATA_FILE = Path(__file__).parent / "data" / "all_items.json"
LATEST_FILE = Path(__file__).parent / "data" / "latest_updates.json"
SITE_DIR = Path(__file__).parent / "site"
SITE_DIR.mkdir(exist_ok=True)

SOURCE_LABELS = {
    "ndcpa": "国家疾控局",
    "chinacdc": "中国疾控中心",
    "customs": "海关总署",
    "nhc": "国家卫健委",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>传染病公文监测日报</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f5f5;color:#333;line-height:1.6}}
.container{{max-width:900px;margin:0 auto;padding:20px}}
.header{{background:#1a237e;color:white;padding:24px 20px;border-radius:12px;margin-bottom:20px}}
.header h1{{font-size:24px;font-weight:600}}
.header p{{margin-top:8px;opacity:0.85;font-size:14px}}
.card{{background:white;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08)}}
.card h2{{font-size:16px;color:#1a237e;margin-bottom:12px;border-bottom:2px solid #e8eaf6;padding-bottom:8px}}
.item{{padding:10px 0;border-bottom:1px solid #f0f0f0}}
.item:last-child{{border-bottom:none}}
.item a{{color:#1565c0;text-decoration:none;font-weight:500}}
.item a:hover{{text-decoration:underline}}
.meta{{font-size:12px;color:#888;margin-top:4px}}
.tag{{display:inline-block;background:#e8eaf6;color:#1a237e;padding:2px 8px;border-radius:4px;font-size:11px;margin-right:6px}}
.empty{{color:#999;font-style:italic}}
.stats{{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap}}
.stat{{background:white;border-radius:10px;padding:16px 20px;box-shadow:0 1px 3px rgba(0,0,0,0.08);text-align:center;flex:1;min-width:100px}}
.stat .num{{font-size:28px;font-weight:700;color:#1a237e}}
.stat .label{{font-size:12px;color:#888;margin-top:4px}}
.footer{{text-align:center;padding:20px;color:#aaa;font-size:12px}}
.latest{{background:linear-gradient(135deg,#e8f5e9,#f4fbf4);border:1px solid #c8e6c9;border-left:4px solid #2e7d32;border-radius:10px;padding:20px;margin-bottom:20px}}
.latest h2{{font-size:17px;color:#1b5e20;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.latest .badge{{background:#2e7d32;color:#fff;font-size:12px;padding:2px 9px;border-radius:10px;font-weight:600}}
.latest .none{{color:#666;font-style:italic;margin-top:6px}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>传染病公文每日监测</h1>
<p>数据源：国家疾控局 / 中国疾控中心 / 海关总署 / 国家卫健委</p>
<p>最近更新：{update_time}</p>
</div>

{latest_html}

<div class="stats">
{stats_html}
</div>

{cards_html}

<div class="footer">
<p>Powered by GitHub Actions · 每日 北京时间 00:00 自动更新（实际约 03:00 完成）</p>
</div>
</div>
</body>
</html>"""


def load_data():
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def build_stats(data: dict) -> str:
    html = ""
    for key, label in SOURCE_LABELS.items():
        src = data.get(key, {})
        count = len(src.get("items", []))
        html += f'<div class="stat"><div class="num">{count}</div><div class="label">{label}</div></div>'
    return html


def build_latest() -> str:
    """渲染顶部'最新更新'栏目：展示本次运行新增的条目"""
    if not LATEST_FILE.exists():
        return '<div class="latest"><h2>最新更新</h2><p class="none">暂无更新记录（尚未运行过监测）</p></div>'
    with open(LATEST_FILE, encoding="utf-8") as f:
        d = json.load(f)
    updated = d.get("updated_at", "")
    items = d.get("items", [])
    is_init = d.get("is_init", False)

    if not items:
        note = "系统初始化完成，首次收录历史数据。" if is_init else "自上次检查以来无新增内容。"
        return (f'<div class="latest"><h2>最新更新 <span class="badge">0</span></h2>'
                f'<p class="none">{note}</p>'
                f'<p class="meta">检查时间：{updated}</p></div>')

    shown = items[:20]
    html = f'<div class="latest"><h2>最新更新 <span class="badge">{len(items)}</span></h2>'
    html += f'<p class="meta">检查时间：{updated}'
    if is_init:
        html += ' · 系统初始化，首次收录以下历史数据'
    html += '</p>'
    for it in shown:
        title = it.get("title", "")
        url = it.get("url", "#")
        src = it.get("source_name", "")
        cat = it.get("category", "")
        date = it.get("date", "")
        html += f'<div class="item"><a href="{url}" target="_blank">{title}</a>'
        html += f'<div class="meta"><span class="tag">{src}</span> {cat} · 日期：{date}</div></div>'
    if len(items) > len(shown):
        html += f'<p class="meta">… 仅显示前 {len(shown)} 条，完整列表见下方各源栏目</p>'
    html += '</div>'
    return html


def build_cards(data: dict) -> str:
    html = ""
    for key, label in SOURCE_LABELS.items():
        src = data.get(key, {})
        items = src.get("items", [])[:10]
        html += f'<div class="card"><h2>{label}</h2>'
        if not items:
            html += '<p class="empty">暂无数据（新源待首次抓取）</p>'
        else:
            for item in items:
                title = item.get("title", "未知")
                pub_date = item.get("date", "?")
                url = item.get("url", "#")
                cat = item.get("category", "")
                html += f'<div class="item"><a href="{url}" target="_blank">{title}</a>'
                html += f'<div class="meta"><span class="tag">{cat}</span> 日期：{pub_date}</div></div>'
        html += "</div>"
    return html


def main():
    data = load_data()
    # GitHub runner 本地时区为 UTC，显式加 8 小时得到北京时间
    update_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M (北京时间)")

    stats_html = build_stats(data)
    cards_html = build_cards(data)
    latest_html = build_latest()

    page = HTML_TEMPLATE.format(
        update_time=update_time,
        latest_html=latest_html,
        stats_html=stats_html,
        cards_html=cards_html,
    )

    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"站点已生成: {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
