#!/usr/bin/env python3
"""生成 GitHub Pages 静态站点。

站点分两大板块：
  一、标准与方法（墨绿系）—— 检验检测标准、计量规范、方法发布/废止动态
  二、传染病公文（靛蓝系）—— 疾控政策、疫情通报、口岸与诊疗公告

顶部"最新更新"拆成两个独立面板，各自只显示本板块的新增条目，
避免标准和传染病公文混在一张榜单里。
"""

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

DATA_FILE = Path(__file__).parent / "data" / "all_items.json"
LATEST_FILE = Path(__file__).parent / "data" / "latest_updates.json"
SITE_DIR = Path(__file__).parent / "site"
SITE_DIR.mkdir(exist_ok=True)

# ---- 板块定义 ----
# color 决定该板块的主色（统计数字、卡片标题边框、最新面板配色）
SOURCE_GROUPS = [
    {
        "key": "standard",
        "title": "标准与方法",
        "subtitle": "检验检测标准 · 计量规范 · 方法发布与废止",
        "color": "#00695c",
        "color_light": "#e0f2f1",
        "sources": [
            ("samr_spcjs", "市场监管总局·食品抽检司"),
            ("samr_jls", "市场监管总局·计量司"),
            ("samr_method", "市场监管总局·食品检验方法库"),
            ("jjg", "国家计量技术规范全文公开系统"),
            ("cfsa", "国家食品安全风险评估中心"),
        ],
    },
    {
        "key": "infectious",
        "title": "传染病公文",
        "subtitle": "疾控政策 · 疫情通报 · 口岸与诊疗公告",
        "color": "#1a237e",
        "color_light": "#e8eaf6",
        "sources": [
            ("ndcpa", "国家疾控局"),
            ("chinacdc", "中国疾控中心"),
            ("ivdc", "国家流感中心"),
            ("customs", "海关总署"),
            ("nhc", "国家卫健委"),
        ],
    },
]

# key → (所属板块, 显示名)
SOURCE_INDEX = {
    key: (group, label)
    for group in SOURCE_GROUPS
    for key, label in group["sources"]
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>传染病公文 · 标准方法 每日监测</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:#f5f5f5;color:#333;line-height:1.6}}
.container{{max-width:1000px;margin:0 auto;padding:20px}}
.header{{background:linear-gradient(135deg,#1a237e 0%,#00695c 100%);color:white;padding:26px 20px;border-radius:12px;margin-bottom:20px}}
.header h1{{font-size:25px;font-weight:600;letter-spacing:.5px}}
.header p{{margin-top:8px;opacity:0.9;font-size:13px}}
.header .groups{{margin-top:14px;display:flex;gap:10px;flex-wrap:wrap}}
.header .gtag{{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);padding:4px 12px;border-radius:14px;font-size:12px}}

.card{{background:white;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08);scroll-margin-top:16px}}
.card h2{{font-size:16px;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #eceff1;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
.card h2 .stime{{font-size:11px;color:#9e9e9e;font-weight:400;margin-left:auto}}
.item{{padding:10px 0;border-bottom:1px solid #f0f0f0}}
.item:last-child{{border-bottom:none}}
.item a{{color:#1565c0;text-decoration:none;font-weight:500}}
.item a:hover{{text-decoration:underline}}
.meta{{font-size:12px;color:#888;margin-top:4px}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;margin-right:6px}}
.empty{{color:#999;font-style:italic}}

/* 统计卡片：按板块分段 */
.stats-group{{margin-bottom:18px}}
.stats-group-head{{display:flex;align-items:baseline;gap:10px;margin-bottom:10px;padding-left:2px}}
.stats-group-head .t{{font-size:14px;font-weight:600}}
.stats-group-head .s{{font-size:12px;color:#999}}
.stats{{display:flex;gap:14px;flex-wrap:wrap}}
a.statlink{{text-decoration:none;color:inherit;flex:1;min-width:96px}}
.stat{{background:white;border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,0.08);text-align:center;transition:transform .15s ease,box-shadow .15s ease;height:100%;border-top:3px solid var(--c)}}
a.statlink:hover .stat{{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.16)}}
.stat .num{{font-size:26px;font-weight:700;color:var(--c)}}
.stat .label{{font-size:12px;color:#888;margin-top:4px}}

/* 最新更新：两个独立面板 */
.panel{{border-radius:10px;padding:18px 20px;margin-bottom:16px;border:1px solid var(--cl);border-left:4px solid var(--c);background:var(--cbg)}}
.panel h2{{font-size:16px;color:var(--c);margin-bottom:4px;display:flex;align-items:center;gap:8px}}
.panel .subtitle{{font-size:12px;color:#8a8a8a;margin-bottom:10px}}
.panel .badge{{background:var(--c);color:#fff;font-size:12px;padding:2px 9px;border-radius:10px;font-weight:600}}
.panel .none{{color:#666;font-style:italic;margin-top:6px}}
.panel .item a{{color:var(--c)}}
.panel .tag{{background:var(--cl);color:var(--c)}}

/* 板块标题条 */
.sect{{display:flex;align-items:center;gap:12px;margin:28px 0 14px}}
.sect .bar{{width:5px;height:22px;border-radius:3px;background:var(--c)}}
.sect .t{{font-size:19px;font-weight:600;color:var(--c)}}
.sect .s{{font-size:12px;color:#999}}

.footer{{text-align:center;padding:24px 10px;color:#aaa;font-size:12px;line-height:1.9}}
.footer a{{color:#78909c}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>传染病公文 · 标准方法 每日监测</h1>
<p>两个板块并行抓取：标准方法动态 + 传染病公文公告，每日北京时间 00:00 自动更新</p>
<div class="groups">
<div class="gtag">标准与方法 5 源</div>
<div class="gtag">传染病公文 5 源</div>
<div class="gtag">最近更新：{update_time}</div>
</div>
</div>

{latest_html}

{cards_html}

<div class="footer">
<p>Powered by GitHub Actions · 每日 北京时间 00:00 自动更新（实际约 03:00 完成）</p>
<p>数据来源：市场监管总局 / 国家计量技术规范全文公开系统 / 国家食品安全风险评估中心 / 国家疾控局 / 中国疾控中心 / 国家流感中心 / 海关总署 / 国家卫健委</p>
</div>
</div>
</body>
</html>"""


def load_data():
    if not DATA_FILE.exists():
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _esc(s: str) -> str:
    """HTML 转义，防止标题中的特殊字符破坏页面结构。"""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_stats(data: dict) -> str:
    """按板块分段渲染统计卡片。"""
    html = ""
    for group in SOURCE_GROUPS:
        cards = ""
        total = 0
        for key, label in group["sources"]:
            src = data.get(key, {})
            count = len(src.get("items", []))
            total += count
            cards += (f'<a class="statlink" href="#src-{key}" title="跳转到{_esc(label)}栏目">'
                      f'<div class="stat"><div class="num">{count}</div>'
                      f'<div class="label">{_esc(label)}</div></div></a>')
        html += (f'<div class="stats-group" style="--c:{group["color"]}">'
                 f'<div class="stats-group-head">'
                 f'<span class="t" style="color:{group["color"]}">{_esc(group["title"])}</span>'
                 f'<span class="s">{_esc(group["subtitle"])} · 合计 {total} 条</span>'
                 f'</div><div class="stats">{cards}</div></div>')
    return html


def _latest_panel(group: dict, items: list[dict], updated: str, is_init: bool,
                  group_seeded: bool = False) -> str:
    """渲染单个板块的"最新更新"面板。

    group_seeded：该板块的源是否已有历史基线。
    新板块刚上线时所有条目都进了基线（不刷屏），此时面板显示"暂无新增记录"
    比"自上次检查以来无新增内容"更准确——后者会让人误以为监控没在工作。
    """
    color = group["color"]
    html = (f'<div class="panel" style="--c:{color};--cl:{group["color_light"]};'
            f'--cbg:linear-gradient(135deg,{group["color_light"]},#ffffff)">')
    html += f'<h2>{_esc(group["title"])}最新更新 <span class="badge">{len(items)}</span></h2>'
    html += f'<p class="subtitle">{_esc(group["subtitle"])}</p>'

    if not items:
        if is_init:
            note = "系统初始化完成，首次收录历史数据。"
        elif group_seeded:
            note = "本板块已建立监测基线，暂无新增记录。"
        else:
            note = "自上次检查以来无新增内容。"
        html += f'<p class="none">{note}</p>'
        html += f'<p class="meta">检查时间：{_esc(updated)}</p>'
        return html + "</div>"

    shown = items[:15]
    html += f'<p class="meta">检查时间：{_esc(updated)}'
    if is_init:
        html += ' · 系统初始化，首次收录以下历史数据'
    html += '</p>'
    for it in shown:
        html += (f'<div class="item"><a href="{_esc(it.get("url", "#"))}" target="_blank">'
                 f'{_esc(it.get("title", ""))}</a>'
                 f'<div class="meta"><span class="tag">{_esc(it.get("source_name", ""))}</span>'
                 f'{_esc(it.get("category", ""))} · 日期：{_esc(it.get("date", ""))}</div></div>')
    if len(items) > len(shown):
        html += f'<p class="meta">… 仅显示前 {len(shown)} 条，完整列表见下方栏目</p>'
    return html + "</div>"


def build_latest(data: dict) -> str:
    """渲染顶部"最新更新"：按板块拆成两个独立面板。"""
    if not LATEST_FILE.exists():
        empty = '<div class="panel"><p class="none">暂无更新记录（尚未运行过监测）</p></div>'
        return empty + empty

    with open(LATEST_FILE, encoding="utf-8") as f:
        d = json.load(f)
    updated = d.get("updated_at", "")
    is_init = d.get("is_init", False)
    all_items = d.get("items", [])

    # 按板块归类条目
    by_group = {g["key"]: [] for g in SOURCE_GROUPS}
    for it in all_items:
        key = it.get("source_key", "")
        group, _label = SOURCE_INDEX.get(key, (None, None))
        if group:
            by_group[group["key"]].append(it)

    html = ""
    for group in SOURCE_GROUPS:
        # 该板块是否已有历史基线（用于区分"刚上线暂无记录"与"真的没新增"）
        group_seeded = any(
            data.get(key, {}).get("ids")
            for key, _ in group["sources"]
        )
        html += _latest_panel(group, by_group[group["key"]], updated, is_init, group_seeded)
    return html


def build_cards(data: dict) -> str:
    """按板块分节渲染各源卡片。"""
    html = ""
    for group in SOURCE_GROUPS:
        color = group["color"]
        html += (f'<div class="sect" style="--c:{color}">'
                 f'<div class="bar"></div><div class="t">{_esc(group["title"])}</div>'
                 f'<div class="s">{_esc(group["subtitle"])}</div></div>')

        for key, label in group["sources"]:
            src = data.get(key, {})
            items = src.get("items", [])[:10]
            last_update = src.get("last_update", "")
            stime = ""
            if last_update:
                # ISO 格式 → 只取到分钟，去掉秒和微秒
                stime = f'<span class="stime">更新于 {_esc(last_update[:16].replace("T", " "))}</span>'

            html += (f'<div class="card" id="src-{key}" style="border-left:4px solid {color}">'
                     f'<h2 style="color:{color};border-bottom-color:{group["color_light"]}">'
                     f'{_esc(label)}{stime}</h2>')
            if not items:
                html += '<p class="empty">暂无数据（新源待首次抓取）</p>'
            else:
                for item in items:
                    title = item.get("title", "未知")
                    pub_date = item.get("date", "?")
                    url = item.get("url", "#")
                    cat = item.get("category", "")
                    html += (f'<div class="item"><a href="{_esc(url)}" target="_blank">{_esc(title)}</a>'
                             f'<div class="meta"><span class="tag" '
                             f'style="background:{group["color_light"]};color:{color}">'
                             f'{_esc(cat)}</span> 日期：{_esc(pub_date)}</div></div>')
            html += "</div>"
    return html


def main():
    data = load_data()
    # GitHub runner 本地时区为 UTC，显式加 8 小时得到北京时间
    update_time = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M (北京时间)")

    latest_html = build_latest(data)
    cards_html = build_cards(data)
    stats_html = build_stats(data)

    # 统计卡片插到板块标题之前：先渲染 stats，再渲染各板块卡片
    page = HTML_TEMPLATE.format(
        update_time=update_time,
        latest_html=latest_html,
        cards_html=f'<div class="stats-wrap">{stats_html}</div>{cards_html}',
    )

    (SITE_DIR / "index.html").write_text(page, encoding="utf-8")
    print(f"站点已生成: {SITE_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
