#!/usr/bin/env python3
"""Render the McDonald's data panorama from public MCP data.

    python3 scripts/build_panorama.py                  # -> out/mcd-wrapped.html
    python3 scripts/build_panorama.py --out x.html

The subject of this report is McDonald's itself, not a person: nutrition
catalogue, marketing calendar, lottery pool, coupons and the points mall.
Everything is pulled live from MNCP, so every number can be re-verified.
"""

import argparse
import html
import json
import os
import sys
from collections import Counter
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_DATA = os.path.join(ROOT, "data", "public_data.json")
DEFAULT_OUT = os.path.join(ROOT, "out", "mcd-wrapped.html")
TEMPLATE = os.path.join(ROOT, "assets", "panorama_template.html")

TOOLS_USED = ["campaign-calendar", "query-lottery-info", "mall-points-products",
              "available-coupons", "list-nutrition-foods", "now-time-info",
              "query-my-account", "order-list"]


def esc(s):
    return html.escape(str(s), quote=True)


def img(src, cls=""):
    if not src:
        return ""
    return ('<img src="%s" class="%s" loading="lazy" '
            'onerror="this.style.display=\'none\'">' % (esc(src), cls))


# ---------------------------------------------------------------- nutrition
def nutrition_stats(kcal):
    if not kcal:
        return {}, []
    vals = sorted(kcal.values())
    n = len(vals)
    avg = sum(vals) / n
    mid = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    heavy = sum(1 for v in vals if v >= 500)
    light = sum(1 for v in vals if v < 200)
    top_name = max(kcal, key=kcal.get)
    low_name = min(kcal, key=kcal.get)
    return ({
        "count": n, "avg": avg, "mid": mid, "max": vals[-1], "min": vals[0],
        "heavy": heavy, "light": light, "top_name": top_name, "low_name": low_name,
    }, vals)


def kcal_rows(pairs, top_value, red=False):
    """pairs: [(name, kcal)] already sorted"""
    rows = []
    for i, (name, v) in enumerate(pairs):
        pct = int(v * 100 / top_value) if top_value else 0
        rows.append(
            '<div class="row"><span class="rank">%02d</span>'
            '<span class="iname" title="%s">%s</span>'
            '<span class="bar%s"><i style="width:%d%%"></i></span>'
            '<span class="qty">%d</span></div>'
            % (i + 1, esc(name), esc(name), " red" if red else "", max(pct, 3), int(v)))
    return "".join(rows)


def kcal_hist(vals, width=690, height=150, bucket=100):
    if not vals:
        return '<div class="empty">暂无营养数据</div>'
    top = int(max(vals) // bucket) + 1
    counts = Counter(int(v // bucket) for v in vals)
    peak = max(counts.values()) or 1
    n = top
    slot = width / max(n, 1)
    bar_w = min(46, slot * 0.7)
    parts = []
    for b in range(n):
        c = counts.get(b, 0)
        h = int((c / peak) * (height - 40))
        x = b * slot + (slot - bar_w) / 2
        y = height - 24 - h
        fill = "#DA291C" if b * bucket >= 500 else "#FFC72C"
        parts.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="3" fill="%s"/>'
                     % (x, y, bar_w, h, fill))
        if c:
            parts.append('<text x="%.1f" y="%d" font-size="10" fill="#8b949e" '
                         'text-anchor="middle" font-family="ui-monospace,monospace">%d</text>'
                         % (x + bar_w / 2, y - 5, c))
        parts.append('<text x="%.1f" y="%d" font-size="9" fill="#6e7681" '
                     'text-anchor="middle" font-family="ui-monospace,monospace">%d</text>'
                     % (x + bar_w / 2, height - 8, b * bucket))
    return ('<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" '
            'aria-label="餐品热量分布">%s</svg>' % (width, height, height, "".join(parts)))


# ------------------------------------------------------------------ cards
def card(label, value, sub, red=False):
    return ('<div class="card"><div class="clabel">%s</div>'
            '<div class="cvalue%s">%s</div><div class="csub">%s</div></div>'
            % (esc(label), " red" if red else "", esc(value), sub))


def overview_cards(d, ns):
    lot = d.get("lottery") or {}
    return "".join([
        card("餐品营养档案", ns.get("count", 0), "官方营养库单品数"),
        card("本月营销活动", len(d.get("campaigns", [])), "来自官方活动日历"),
        card("抽奖奖品种类", len(lot.get("prizes", [])), "%s" % esc(lot.get("name") or "—")),
        card("单次抽奖积分", "%d" % int(lot.get("cost") or 0), "积分消耗 · %s"
             % esc(lot.get("status") or "")),
        card("积分商城商品", len(d.get("mall", [])), "含派对 · 周边 · 权益"),
        card("可领优惠券", len(d.get("coupons", [])), "麦麦省当前可领取"),
    ])


def nutri_cards(ns):
    if not ns:
        return '<div class="empty">暂无营养数据</div>'
    return "".join([
        card("平均单品热量", "%d" % ns["avg"], "kcal / 单品"),
        card("热量中位数", "%d" % ns["mid"], "kcal · 半数餐品低于此"),
        card("最高单品", "%d" % ns["max"], esc(ns["top_name"]), red=True),
        card("最低单品", "%d" % ns["min"], esc(ns["low_name"])),
        card("≥500 kcal 单品", "%d" % ns["heavy"], "占 %.0f%%"
             % (ns["heavy"] * 100.0 / ns["count"])),
        card("<200 kcal 单品", "%d" % ns["light"], "占 %.0f%%"
             % (ns["light"] * 100.0 / ns["count"])),
    ])


def lottery_cards(lot):
    if not lot:
        return '<div class="empty">暂无抽奖数据</div>'
    prizes = lot.get("prizes", [])
    coupon_n = sum(1 for p in prizes if "券" in p.get("type", "") or "券" in p.get("name", ""))
    point_n = sum(1 for p in prizes if "积分" in p.get("type", ""))
    return "".join([
        card("单次消耗", "%d" % int(lot.get("cost") or 0), esc(lot.get("cost_text") or "积分")),
        card("奖品种类", "%d" % len(prizes), "券类 %d · 积分类 %d" % (coupon_n, point_n)),
        card("活动状态", esc(lot.get("status") or "—"), esc(lot.get("window") or "")),
    ])


def lottery_note(lot):
    if not lot:
        return "暂无抽奖数据。"
    prizes = lot.get("prizes", [])
    cost = int(lot.get("cost") or 0)
    point_prizes = [p for p in prizes if "积分" in p.get("type", "")]
    best = max((int("".join(ch for ch in p["name"] if ch.isdigit()) or 0)
                for p in point_prizes), default=0)
    lines = ["奖池共 <b>%d</b> 种奖品，单次消耗 <b>%d 积分</b>。" % (len(prizes), cost)]
    if point_prizes and best:
        lines.append("奖池里唯一的积分奖为 <b>%d 积分</b>，即抽中它相当于 %.2f 倍返还。"
                     % (best, best / cost if cost else 0))
    lines.append("官方未公布各奖品中奖概率，因此<b>无法计算精确期望值</b>；"
                 "若假设 %d 种奖品等概率，抽中积分奖的概率约为 %.0f%%，"
                 "抽中任意优惠券类奖品约为 %.0f%%。"
                 % (len(prizes), 100.0 * len(point_prizes) / len(prizes),
                    100.0 * (len(prizes) - len(point_prizes)) / len(prizes)))
    lines.append("本页只做数据披露，不构成任何参与建议。")
    return "<br>".join(lines)


# --------------------------------------------------------------- calendar
def calendar_html(events, limit=14):
    if not events:
        return '<div class="empty">暂无活动数据</div>'
    out = []
    for e in events[-limit:][::-1]:
        past = "past" if "往期" in (e.get("tag") or "") else ""
        body = (e.get("body") or "").strip()
        if len(body) > 130:
            body = body[:130] + "…"
        out.append(
            '<div class="ev %s"><div class="when"><b>%s</b> · %s</div>'
            '<h3>%s</h3>%s%s</div>'
            % (past, esc(e.get("date") or ""), esc((e.get("tag") or "").replace("往期回顾", "往期")),
               esc(e.get("title") or ""),
               '<div class="body">%s</div>' % esc(body) if body else "",
               img(e.get("image"))))
    return "".join(out)


# ----------------------------------------------------------- mall / coupons
def prize_grid(prizes):
    if not prizes:
        return '<div class="empty">暂无奖品数据</div>'
    out = []
    for p in prizes:
        pts = "pts" if "积分" in p.get("type", "") else ""
        out.append('<div class="pz %s">%s<div class="pn">%s</div>'
                   '<div class="pt">%s</div></div>'
                   % (pts, img(p.get("image")), esc(p.get("name")), esc(p.get("type"))))
    return "".join(out)


def coupon_grid(coupons):
    if not coupons:
        return '<div class="empty">当前无可领取优惠券</div>'
    out = []
    for c in coupons:
        out.append('<div class="cp">%s<div><div class="ct">%s</div>'
                   '<div class="cs">%s</div></div></div>'
                   % (img(c.get("image")), esc(c.get("title")), esc(c.get("status") or "可领取")))
    return "".join(out)


def mall_cats(mall):
    if not mall:
        return '<div class="empty">暂无商城数据</div>'
    by_cat = Counter(m.get("cat") or "未分类" for m in mall)
    priced = [m for m in mall if m.get("price")]
    avg_price = sum(m["price"] for m in priced) / len(priced) if priced else 0
    free_point = sum(1 for m in mall if not m.get("points"))
    rows = "".join(
        '<div class="row"><span class="rank">%02d</span><span class="iname">%s</span>'
        '<span class="bar"><i style="width:%d%%"></i></span>'
        '<span class="qty">%d</span></div>'
        % (i + 1, esc(cat), max(int(n * 100 / by_cat.most_common(1)[0][1]), 4), n)
        for i, (cat, n) in enumerate(by_cat.most_common(8)))
    head = ('<div class="cards" style="margin-bottom:12px">%s%s%s</div>'
            % (card("商品总数", len(mall), "在架可兑换"),
               card("平均现金价", "¥%.0f" % avg_price, "含派对与周边"),
               card("纯现金商品", free_point, "无需积分，直接购买")))
    return head + rows


def mall_list(mall, limit=18):
    if not mall:
        return ""
    rows = ['<tr><th>商品</th><th>类目</th><th>积分</th><th>现金价</th></tr>']
    for m in mall[:limit]:
        rows.append('<tr><td class="n">%s</td><td class="c">%s</td>'
                    '<td class="p">%s</td><td class="p">%s</td></tr>'
                    % (esc(m.get("name")), esc(m.get("cat")),
                       int(m["points"]) if m.get("points") else "—",
                       "¥%g" % m["price"] if m.get("price") else "—"))
    if len(mall) > limit:
        rows.append('<tr><td colspan="4" style="color:var(--muted);font-size:11px">'
                    '…另有 %d 件商品，完整清单见 data/public_data.json</td></tr>'
                    % (len(mall) - limit))
    return "".join(rows)


# ------------------------------------------------------------------ render
def render(data, template_path=TEMPLATE):
    kcal = data.get("nutrition_kcal") or {}
    ns, vals = nutrition_stats(kcal)
    lot = data.get("lottery") or {}

    top10 = sorted(kcal.items(), key=lambda kv: -kv[1])[:10] if kcal else []
    low10 = sorted(kcal.items(), key=lambda kv: kv[1])[:10] if kcal else []
    top_val = top10[0][1] if top10 else 1

    with open(template_path, encoding="utf-8") as f:
        tpl = f.read()

    data_points = (len(kcal) + len(data.get("campaigns", []))
                   + len(lot.get("prizes", [])) + len(data.get("mall", []))
                   + len(data.get("coupons", [])))

    mapping = {
        "TITLE": "M-CODE WRAPPED",
        "SUBTITLE": "麦当劳数据全景报告 · 一次看透 MNCP 能拿到什么",
        "SOURCE_BADGE": "100% 真实数据 · MNCP",
        "GENERATED": data.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "TOOL_COUNT": len(TOOLS_USED),
        "DATA_POINTS": data_points,
        "CARDS": overview_cards(data, ns),
        "NUTRI_STATS": nutri_cards(ns),
        "KCAL_TOP": kcal_rows(top10, top_val, red=True),
        "KCAL_LOW": kcal_rows(low10, top_val),
        "KCAL_HIST": kcal_hist(vals),
        "CALENDAR": calendar_html(data.get("campaigns", [])),
        "LOTTERY_CARDS": lottery_cards(lot),
        "PRIZE_GRID": prize_grid(lot.get("prizes", [])),
        "LOTTERY_NOTE": lottery_note(lot),
        "COUPON_GRID": coupon_grid(data.get("coupons", [])),
        "MALL_CATS": mall_cats(data.get("mall", [])),
        "MALL_LIST": mall_list(data.get("mall", [])),
        "FOOTNOTE":
            "数据来源：麦当劳中国 MNCP（<span class='mono'>https://mcp.mcd.cn</span>），"
            "由本 Skill 实时调用 %s 等 %d 个官方 tool 获取，未经人工编造。<br>"
            "生成方式：<span class='mono'>scripts/public_data.py</span> 采集 → "
            "<span class='mono'>scripts/build_panorama.py</span> 渲染。<br>"
            "项目地址：<span class='mono'>github.com/lvzuojing/mcd-wrapped</span>"
            "接入个人 Token 可再生成个人消费年报（<span class='mono'>scripts/collect.py</span>）。<br>"
            "本页为麦当劳 1024 程序员节创意开发大赛参赛作品，仅作数据可视化展示，"
            "不构成任何消费或参与建议。营养数据为官方单品参考值。"
            % ("、".join(TOOLS_USED[:3]), len(TOOLS_USED)),
    }
    for k, v in mapping.items():
        tpl = tpl.replace("{{%s}}" % k, str(v))
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.exists(args.data):
        print("no data file: %s (run scripts/public_data.py first)" % args.data, file=sys.stderr)
        sys.exit(1)
    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)

    html_out = render(data)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html_out)
    print("panorama written: %s" % os.path.abspath(args.out))


if __name__ == "__main__":
    main()
