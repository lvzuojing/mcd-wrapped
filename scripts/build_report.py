#!/usr/bin/env python3
"""Turn data/report_data.json into a shareable annual report page.

    python3 scripts/build_report.py                     # -> out/mcd-wrapped.html
    python3 scripts/build_report.py --data x.json --out y.html

Works on both MCP-collected data and demo data (identical schema).

Compliance note: the report is intentionally factual and upbeat. It never
judges eating habits and states that nutrition figures are estimates for
reference only.
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_DATA = os.path.join(ROOT, "data", "report_data.json")
DEFAULT_OUT = os.path.join(ROOT, "out", "mcd-wrapped.html")
TEMPLATE = os.path.join(ROOT, "assets", "report_template.html")

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
KCAL_PER_KM = 62.0  # rough walking cost per km, used for a neutral equivalence
KM_JINGHU = 1200.0  # Beijing-Shanghai by road, used as a friendly yardstick


def parse_time(s):
    try:
        return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(str(s)[:10], "%Y-%m-%d")
        except ValueError:
            return None


def compute_metrics(data):
    orders = [o for o in data.get("orders", []) if parse_time(o.get("time"))]
    orders.sort(key=lambda o: o["time"])

    total_spend = round(sum(o.get("total", 0) for o in orders), 2)
    total_discount = round(sum(o.get("discount", 0) for o in orders), 2)
    total_kcal = sum(o.get("kcal", 0) for o in orders)

    item_qty, item_spend = Counter(), Counter()
    store_counter, month_counter, weekday_counter = Counter(), Counter(), Counter()
    channel_counter = Counter()
    late_night = 0
    hours = Counter()

    for o in orders:
        dt = parse_time(o["time"])
        if dt.hour >= 22 or dt.hour < 5:
            late_night += 1
        hours[dt.hour] += 1
        month_counter[dt.strftime("%Y-%m")] += 1
        weekday_counter[WEEKDAYS[dt.weekday()]] += 1
        store_counter[o.get("store", "未知门店")] += 1
        ch = o.get("channel", "")
        channel_counter["外送" if "送" in ch else "到店"] += 1
        for it in o.get("items", []):
            item_qty[it.get("name", "未知")] += it.get("qty", 1)
            item_spend[it.get("name", "未知")] += it.get("price", 0)

    first, last = (orders[0], orders[-1]) if orders else (None, None)
    span_days = 0
    if first and last:
        span_days = max(1, (parse_time(last["time"]) - parse_time(first["time"])).days)

    # longest streak of distinct calendar days with at least one order
    days = sorted({parse_time(o["time"]).date() for o in orders})
    best = cur = 1
    prev = None
    for d in days:
        if prev and (d - prev).days == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
        prev = d
    if not days:
        best = 0

    return {
        "order_count": len(orders),
        "total_spend": total_spend,
        "total_discount": total_discount,
        "total_kcal": int(total_kcal),
        "walk_km": round(total_kcal / KCAL_PER_KM, 1),
        "walk_ref": round(total_kcal / KCAL_PER_KM / KM_JINGHU, 1),
        "avg_ticket": round(total_spend / len(orders), 2) if orders else 0,
        "top_items": [{"name": n, "qty": q, "spend": round(item_spend[n], 2)}
                      for n, q in item_qty.most_common(6)],
        "top_store": store_counter.most_common(1)[0] if store_counter else ("—", 0),
        "store_rank": store_counter.most_common(5),
        "month_series": sorted(month_counter.items())[-12:],
        "weekday_rank": [(w, weekday_counter.get(w, 0)) for w in WEEKDAYS],
        "channel": dict(channel_counter),
        "late_night": late_night,
        "late_ratio": round(late_night * 100.0 / len(orders), 1) if orders else 0,
        "peak_hour": hours.most_common(1)[0] if hours else ("—", 0),
        "best_streak": best,
        "first_time": first["time"][:10] if first else "—",
        "last_time": last["time"][:10] if last else "—",
        "span_days": span_days,
        "account": data.get("account", {}),
        "mall_count": len(data.get("mall_orders", [])),
        "coupon_count": len(data.get("coupons", [])),
        "prize_count": len(data.get("prizes", [])),
        "source": data.get("source", "demo"),
        "generated_at": data.get("generated_at", ""),
    }


def month_bars(series, width=620, height=140):
    """Hand-rolled SVG bar chart, no external dependencies."""
    if not series:
        return ""
    top = max(v for _, v in series) or 1
    n = len(series)
    slot = width / n
    bar_w = min(38, slot * 0.62)
    parts = []
    for i, (label, v) in enumerate(series):
        h = int((v / top) * (height - 34))
        x = i * slot + (slot - bar_w) / 2
        y = height - 20 - h
        parts.append(
            '<rect x="%.1f" y="%d" width="%.1f" height="%d" rx="3" fill="#FFC72C"/>'
            % (x, y, bar_w, h))
        parts.append(
            '<text x="%.1f" y="%d" font-size="10" fill="#8b949e" '
            'text-anchor="middle" font-family="ui-monospace,monospace">%s</text>'
            % (x + bar_w / 2, y - 5, v))
        parts.append(
            '<text x="%.1f" y="%d" font-size="10" fill="#6e7681" '
            'text-anchor="middle" font-family="ui-monospace,monospace">%s</text>'
            % (x + bar_w / 2, height - 6, label[-2:]))
    return ('<svg viewBox="0 0 %d %d" width="100%%" height="%d" role="img" '
            'aria-label="近一年每月下单数">%s</svg>' % (width, height, height, "".join(parts)))


def item_rows(top_items):
    if not top_items:
        return ""
    top = max(i["qty"] for i in top_items) or 1
    rows = []
    for idx, it in enumerate(top_items):
        pct = int(it["qty"] * 100 / top)
        rows.append(
            '<div class="row"><span class="rank">%02d</span>'
            '<span class="iname">%s</span>'
            '<span class="bar"><i style="width:%d%%"></i></span>'
            '<span class="qty">%d 份</span></div>' % (idx + 1, it["name"], pct, it["qty"]))
    return "".join(rows)


def weekday_cells(weekday_rank):
    top = max(v for _, v in weekday_rank) or 1
    cells = []
    for w, v in weekday_rank:
        alpha = 0.15 + 0.85 * (v / top) if top else 0.15
        cells.append(
            '<div class="cell" style="background:rgba(255,199,44,%.2f)">'
            '<b>%s</b><span>%d</span></div>' % (alpha, w, v))
    return "".join(cells)


def metric_cards(m):
    cards = [
        ("年度下单总数", "%d" % m["order_count"], "笔 · 相当于 %d 次 commit" % m["order_count"]),
        ("年度消费总额", "¥%.0f" % m["total_spend"], "客单价 ¥%.1f" % m["avg_ticket"]),
        ("优惠券省下", "¥%.0f" % m["total_discount"], "能再买 %d 个甜筒"
         % int(m["total_discount"] / 6)),
        ("深夜订单占比", "%.0f%%" % m["late_ratio"], "22:00 后的 %d 笔 · 深夜编译指数"
         % m["late_night"]),
        ("最常去的门店", m["top_store"][0], "光顾 %d 次" % m["top_store"][1]),
        ("连续打卡纪录", "%d 天" % m["best_streak"], "麦龄 %d 天" % m["span_days"]),
    ]
    out = []
    for label, value, sub in cards:
        out.append('<div class="card"><div class="clabel">%s</div>'
                   '<div class="cvalue">%s</div><div class="csub">%s</div></div>'
                   % (label, value, sub))
    return "".join(out)


def render(data, template_path=TEMPLATE):
    m = compute_metrics(data)
    with open(template_path, encoding="utf-8") as f:
        tpl = f.read()

    account = m["account"]
    points = account.get("points_available", "—")
    expiring = account.get("points_expiring", "—")

    mapping = {
        "TITLE": "M-CODE WRAPPED",
        "SUBTITLE": "你的麦当劳年度开发日志",
        "RANGE": "%s 至 %s" % (m["first_time"], m["last_time"]),
        "SOURCE_BADGE": "真实数据 · MCP" if m["source"] == "mcp" else "演示数据 · dry-run",
        "GENERATED": m["generated_at"],
        "CARDS": metric_cards(m),
        "MONTH_BARS": month_bars(m["month_series"]),
        "ITEM_ROWS": item_rows(m["top_items"]),
        "WEEKDAY_CELLS": weekday_cells(m["weekday_rank"]),
        "TOP_ITEM": m["top_items"][0]["name"] if m["top_items"] else "—",
        "TOP_ITEM_QTY": m["top_items"][0]["qty"] if m["top_items"] else 0,
        "PEAK_HOUR": m["peak_hour"][0],
        "CHANNEL": "外送 %.0f%% / 到店 %.0f%%" % (
            m["channel"].get("外送", 0) * 100.0 / max(1, m["order_count"]),
            m["channel"].get("到店", 0) * 100.0 / max(1, m["order_count"])),
        "KCAL": "%d" % m["total_kcal"],
        "WALK_KM": "%.1f" % m["walk_km"],
        "WALK_REF": "%.1f" % m["walk_ref"],
        "POINTS": "%s" % points,
        "EXPIRING": "%s" % expiring,
        "MALL_COUNT": "%d" % m["mall_count"],
        "COUPON_COUNT": "%d" % m["coupon_count"],
        "PRIZE_COUNT": "%d" % m["prize_count"],
    }
    if m["order_count"] == 0:
        mapping["CARDS"] = (
            '<div class="panel" style="grid-column:1/-1;text-align:center;'
            'padding:26px 16px">'
            '<div style="font-size:14px;margin-bottom:6px">该账号暂无历史订单数据</div>'
            '<div style="font-size:12px;color:var(--muted);line-height:1.7">'
            'MCP 连接正常，积分与餐品营养数据已读取成功。<br>'
            '换用一个有下单记录的手机号申请 Token，即可生成完整年报。</div>'
            '</div>')
        mapping["SOURCE_BADGE"] = "真实数据 · 订单为空"
    for k, v in mapping.items():
        tpl = tpl.replace("{{%s}}" % k, str(v))
    return tpl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--json", action="store_true", help="dump metrics as json")
    args = ap.parse_args()

    if not os.path.exists(args.data):
        print("no data file: %s (run scripts/demo_data.py first)" % args.data, file=sys.stderr)
        sys.exit(1)
    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)

    if args.json:
        print(json.dumps(compute_metrics(data), ensure_ascii=False, indent=2))
        return

    html = render(data)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print("report written: %s" % os.path.abspath(args.out))


if __name__ == "__main__":
    main()
