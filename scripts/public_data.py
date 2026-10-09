#!/usr/bin/env python3
"""Collect the PUBLIC slice of McDonald's MCP data.

Unlike scripts/collect.py (which needs a personal order history), these four
tools return brand-level data that works for any token, even a fresh account:

    campaign-calendar       marketing calendar for the current month
    query-lottery-info      live points lottery: cost per draw + prize pool
    mall-points-products    points-mall catalogue (name / points / price / cat)
    available-coupons       麦麦省 coupons currently claimable

Plus list-nutrition-foods (158 real products) reused from collect.py.

    export MCD_MCP_TOKEN=xxx
    python3 scripts/public_data.py           # -> data/public_data.json
    python3 scripts/public_data.py --offline # re-parse data/raw only

Every number in the generated report comes from here, so it stays verifiable.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collect import (  # noqa: E402
    RAW_DIR, ROOT, parse_markdown_payload, parse_nutrition_text, to_number,
)
from mcp_client import McpClient, McpError, unwrap  # noqa: E402

PUBLIC_TOOLS = [
    "campaign-calendar",
    "query-lottery-info",
    "mall-points-products",
    "available-coupons",
    "list-nutrition-foods",
]

IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"')


# --------------------------------------------------------------------------
# parsers: each tool has its own response dialect
# --------------------------------------------------------------------------
def parse_campaign_calendar(raw):
    """Markdown grouped by day:

        #### 2026年10月9日 今日
        - **活动标题**：xxx
          **活动内容介绍**：...
          **活动图片介绍**：
          <img src="...">
    """
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    events, cur_date, cur_tag = [], None, ""
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^#{2,6}\s*(\d{4}年\d{1,2}月\d{1,2}日)(.*)", line)
        if m:
            cur_date = m.group(1).replace("年", "-").replace("月", "-").replace("日", "")
            cur_tag = m.group(2).strip()
            continue
        m = re.match(r"^[-*]\s*\**活动标题\**\s*[:：]\s*(.+?)\s*$", line)
        if m:
            events.append({"date": cur_date, "tag": cur_tag,
                           "title": re.sub(r"\**$", "", m.group(1)).strip(),
                           "body": "", "image": ""})
            continue
        m = re.match(r"^\**活动内容介绍\**\s*[:：]\s*(.*)$", line)
        if m and events:
            clean = re.sub(r"<img[^>]*>", "", m.group(1)).strip()
            clean = re.sub(r"\s{2,}", " ", clean)
            events[-1]["body"] = clean
            continue
        m = re.match(r"^\**活动图片介绍\**\s*[:：]\s*(.*)$", line)
        if m and events:
            g = IMG_RE.search(m.group(1))
            if g:
                events[-1]["image"] = g.group(1)
            continue
        if events and line and not line.startswith("#") and not line.startswith("---"):
            # continuation lines belong to the body
            if events[-1]["body"]:
                events[-1]["body"] += " " + line
    # dedupe by (date, title)
    seen, uniq = set(), []
    for e in events:
        key = (e["date"], e["title"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


def parse_lottery(raw):
    """data: {activityName, drawPoint, activityStatusText, prizes:[{name,typeText}]}"""
    obj = parse_markdown_payload(raw)
    if not isinstance(obj, dict):
        return {}
    node = obj.get("data") if isinstance(obj.get("data"), dict) else obj
    prizes = []
    for p in (node.get("prizes") or []):
        if isinstance(p, dict) and p.get("name"):
            prizes.append({"name": str(p["name"]),
                           "type": str(p.get("typeText") or ""),
                           "image": str(p.get("imageUrl") or "")})
    return {
        "name": str(node.get("activityName") or ""),
        "status": str(node.get("activityStatusText") or ""),
        "cost": to_number(node.get("drawPoint")),
        "cost_text": str(node.get("drawTypeText") or ""),
        "window": "%s ~ %s" % (str(node.get("beginTime") or "")[:10],
                               str(node.get("endTime") or "")[:10]),
        "prizes": prizes,
    }


def parse_mall(raw):
    """data: [{spuName, point, price, catName, selling, status, spuImage, ...}]"""
    obj = parse_markdown_payload(raw)
    if not isinstance(obj, dict):
        return []
    rows = obj.get("data")
    if not isinstance(rows, list):
        return []
    out = []
    for d in rows:
        if not isinstance(d, dict) or not d.get("spuName"):
            continue
        out.append({
            "name": str(d["spuName"]),
            "id": d.get("spuId"),
            "points": to_number(d.get("point")),
            "price": to_number(d.get("price")),
            "cat": str(d.get("catName") or "未分类"),
            "selling": str(d.get("selling") or ""),
            "image": str(d.get("spuImage") or ""),
            "status": {1: "仓库中", 2: "上架", 3: "售罄", 4: "下架", 5: "预热"}
                       .get(d.get("status"), ""),
            "window": "%s ~ %s" % (str(d.get("upTime") or "")[:10],
                                   str(d.get("downTime") or "")[:10]),
        })
    return out


def parse_coupons(raw):
    """Plain markdown list:

        - 优惠券标题：麦旋风任选
          状态：可领取
          优惠券图片：
          <img src="...">
    """
    if not isinstance(raw, str):
        raw = json.dumps(raw, ensure_ascii=False)
    out, cur = [], None
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"^[-*]\s*优惠券标题\s*[:：]\s*(.+?)\s*\\?$", line)
        if m:
            cur = {"title": m.group(1).strip(), "status": "", "image": ""}
            out.append(cur)
            continue
        m = re.match(r"^状态\s*[:：]\s*(.+?)\s*$", line)
        if m and cur:
            cur["status"] = m.group(1).strip()
            continue
        g = IMG_RE.search(line)
        if g and cur and not cur["image"]:
            cur["image"] = g.group(1)
    seen, uniq = set(), []
    for c in out:
        if c["title"] in seen:
            continue
        seen.add(c["title"])
        uniq.append(c)
    return uniq


def parse_nutrition(raw):
    if isinstance(raw, str):
        return parse_nutrition_text(raw)
    if isinstance(raw, dict):
        if isinstance(raw.get("data"), str):
            return parse_nutrition_text(raw["data"])
        return parse_nutrition_text(json.dumps(raw, ensure_ascii=False))
    return {}


# --------------------------------------------------------------------------
def fetch(token=None):
    client = McpClient(token=token)
    client.initialize()
    raw = {}
    for tool in PUBLIC_TOOLS:
        try:
            raw[tool] = unwrap(client.call_tool(tool, {}))
            print("  ok   %s" % tool)
        except McpError as e:
            print("  fail %s -> %s" % (tool, e))
            raw[tool] = None
        os.makedirs(RAW_DIR, exist_ok=True)
        with open(os.path.join(RAW_DIR, "%s.json" % tool), "w", encoding="utf-8") as f:
            json.dump(raw[tool], f, ensure_ascii=False, indent=2, default=str)
    return raw


def load_offline():
    raw = {}
    for tool in PUBLIC_TOOLS:
        p = os.path.join(RAW_DIR, "%s.json" % tool)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                raw[tool] = json.load(f)
    return raw


def build(raw):
    kcal = parse_nutrition(raw.get("list-nutrition-foods"))
    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "mcp-public",
        "nutrition_kcal": kcal,
        "campaigns": parse_campaign_calendar(raw.get("campaign-calendar")),
        "lottery": parse_lottery(raw.get("query-lottery-info")),
        "mall": parse_mall(raw.get("mall-points-products")),
        "coupons": parse_coupons(raw.get("available-coupons")),
    }
    out = os.path.join(ROOT, "data", "public_data.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="re-parse data/raw without calling MCP")
    args = ap.parse_args()

    raw = load_offline() if args.offline else fetch()
    data = build(raw)
    print("public data -> data/public_data.json")
    print("  nutrition   : %d products" % len(data["nutrition_kcal"]))
    print("  campaigns   : %d events" % len(data["campaigns"]))
    print("  lottery     : %s (%s prizes, %s pts/draw)"
          % (data["lottery"].get("name"), len(data["lottery"].get("prizes", [])),
             data["lottery"].get("cost")))
    print("  mall        : %d products" % len(data["mall"]))
    print("  coupons     : %d" % len(data["coupons"]))


if __name__ == "__main__":
    main()
