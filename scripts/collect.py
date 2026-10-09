#!/usr/bin/env python3
"""Pull real data from the McDonald's MCP server and normalise it into
data/report_data.json (the exact shape build_report.py consumes).

    export MCD_MCP_TOKEN=xxx
    python3 scripts/collect.py

Raw responses are always kept under data/raw/ so field mappings can be fixed
without another round of live calls.
"""

import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_client import McpClient, McpError, unwrap  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RAW_DIR = os.path.join(ROOT, "data", "raw")

TOOLS = [
    "now-time-info",
    "query-my-account",
    "order-list",
    "mall-order-list",
    "query-my-coupons",
    "query-my-prizes",
    "list-nutrition-foods",
]

TIME_KEYS = ["orderTime", "createTime", "createdAt", "payTime", "gmtCreate",
             "time", "date", "orderDate", "createAt"]
NAME_KEYS = ["mealName", "productName", "itemName", "goodsName", "name", "title"]
PRICE_KEYS = ["realTotalAmount", "payAmount", "totalAmount", "realAmount",
              "orderAmount", "amount", "price", "sellPrice"]
QTY_KEYS = ["quantity", "qty", "num", "count", "amount_num"]
STORE_KEYS = ["storeName", "shopName", "store", "shop", "restaurantName"]
CHANNEL_KEYS = ["channel", "orderType", "scene", "deliveryType", "dineType"]


def parse_markdown_payload(raw):
    """McDonald's MCP returns Markdown, not JSON.

    The tool content looks like:
        ## Response Structure
        ...field docs...
        ## Original Response
        {"success":true,...,"data":{...}}

    Pull the JSON out of the "Original Response" block and return a python
    object. Falls back to the raw string when no JSON is present (some tools
    answer with plain text such as "暂无可用优惠券").
    """
    if not isinstance(raw, str):
        return raw
    marker = "## Original Response"
    chunk = raw.split(marker, 1)[1] if marker in raw else raw
    decoder = json.JSONDecoder()
    for start in (i for i, ch in enumerate(chunk) if ch in "{["):
        try:
            obj, _ = decoder.raw_decode(chunk[start:])
            return obj
        except ValueError:
            continue
    return raw


def parse_nutrition_text(text):
    """Nutrition comes back as a delimited text table, not JSON.

        [160]{productName,nutritionDescription,energyKj,energyKcal,...}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
    """
    if not isinstance(text, str):
        return {}
    m = re.search(r"\{([^}]*)\}\s*:", text)
    if not m:
        return {}
    cols = [c.strip() for c in m.group(1).split(",")]
    try:
        kcal_i = next(i for i, c in enumerate(cols)
                      if c.lower() in ("energykcal", "kcal", "能量"))
        name_i = next(i for i, c in enumerate(cols)
                      if c.lower() in ("productname", "name", "餐品名称"))
    except StopIteration:
        return {}
    out = {}
    for line in text[m.end():].splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != len(cols):
            continue
        try:
            out[parts[name_i]] = float(parts[kcal_i])
        except (ValueError, IndexError):
            continue
    return out


def save_raw(name, payload):
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, "%s.json" % name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    return path


def walk(obj):
    """Yield every dict/list node in a nested structure."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        yield obj
        for v in obj:
            yield from walk(v)


def pick(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    low = {str(k).lower(): v for k, v in d.items()}
    for k in keys:
        if k.lower() in low and low[k.lower()] not in (None, ""):
            return low[k.lower()]
    return None


def find_dict_lists(payload, required_keys):
    """Return every list-of-dict whose entries carry one of required_keys."""
    out = []
    for node in walk(payload):
        if not isinstance(node, list) or not node:
            continue
        if not all(isinstance(x, dict) for x in node):
            continue
        hits = sum(1 for x in node if pick(x, required_keys) is not None)
        if hits >= max(1, int(len(node) * 0.6)):
            out.append(node)
    out.sort(key=len, reverse=True)
    return out


def to_number(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:\.\d+)?", v.replace(",", ""))
        if m:
            return float(m.group())
    return 0.0


def norm_time(v):
    if not v:
        return ""
    if isinstance(v, (int, float)):
        ts = v / 1000 if v > 1e12 else v
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError, OverflowError):
            return str(v)
    s = str(v).strip()
    m = re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T]\d{1,2}:\d{2}(:\d{2})?)?", s)
    return m.group().replace("/", "-").replace("T", " ") if m else s


def extract_orders(payload, nutrition_kcal):
    orders = []
    for lst in find_dict_lists(payload, TIME_KEYS):
        for d in lst:
            ts = norm_time(pick(d, TIME_KEYS))
            if not re.match(r"\d{4}-\d{2}-\d{2}", ts or ""):
                continue
            items = []
            for sub in walk(d):
                if isinstance(sub, dict):
                    nm = pick(sub, NAME_KEYS)
                    pr = pick(sub, PRICE_KEYS)
                    if nm and pr is not None:
                        items.append({
                            "name": str(nm),
                            "qty": int(to_number(pick(sub, QTY_KEYS) or 1) or 1),
                            "price": round(to_number(pr), 2),
                        })
                elif isinstance(sub, list):
                    for x in sub:
                        if isinstance(x, dict):
                            nm = pick(x, NAME_KEYS)
                            pr = pick(x, PRICE_KEYS)
                            if nm and pr is not None:
                                items.append({
                                    "name": str(nm),
                                    "qty": int(to_number(pick(x, QTY_KEYS) or 1) or 1),
                                    "price": round(to_number(pr), 2),
                                })
            # de-duplicate items while preserving order
            seen, uniq = set(), []
            for it in items:
                if it["name"] in seen:
                    continue
                seen.add(it["name"])
                uniq.append(it)
            total = to_number(pick(d, ["payAmount", "realAmount", "totalAmount",
                                       "orderAmount", "amount", "price"]))
            if not total:
                total = sum(i["price"] for i in uniq)
            orders.append({
                "order_id": str(pick(d, ["orderId", "orderNo", "id", "orderSn"]) or ""),
                "time": ts,
                "store": str(pick(d, STORE_KEYS) or "未知门店"),
                "channel": str(pick(d, CHANNEL_KEYS) or "下单"),
                "items": uniq,
                "discount": round(to_number(pick(d, ["discountAmount", "discount",
                                                     "couponAmount"])), 2),
                "total": round(total, 2),
                "kcal": sum(nutrition_kcal.get(i["name"], 0) * i["qty"] for i in uniq),
            })
        if orders:
            break
    orders.sort(key=lambda o: o["time"])
    return orders


def extract_nutrition(payload):
    kcal, price = {}, {}
    for lst in find_dict_lists(payload, NAME_KEYS):
        for d in lst:
            nm = pick(d, NAME_KEYS)
            if not nm:
                continue
            energy = None
            for k, v in d.items():
                if any(w in str(k).lower() for w in ["energy", "kcal", "calorie", "热量", "能量"]):
                    energy = v
                    break
            if energy is not None:
                kcal[str(nm)] = to_number(energy)
            pr = pick(d, PRICE_KEYS)
            if pr is not None:
                price[str(nm)] = to_number(pr)
    return kcal, price


def extract_simple_list(payload, name_keys, time_keys=None):
    out = []
    for lst in find_dict_lists(payload, name_keys):
        for d in lst:
            nm = pick(d, name_keys)
            if not nm:
                continue
            row = {"name": str(nm)}
            if time_keys:
                row["time"] = norm_time(pick(d, time_keys))
            for extra in ("points", "status"):
                v = pick(d, [extra, extra.capitalize()])
                if v is not None:
                    row[extra] = v
            out.append(row)
        if out:
            break
    return out


def extract_account(payload):
    acc = {}
    for d in walk(payload):
        if not isinstance(d, dict):
            continue
        for k, v in d.items():
            lk = str(k).lower()
            if "available" in lk or "usable" in lk or lk in ("points", "point"):
                acc.setdefault("points_available", to_number(v))
            elif "accumulative" in lk or ("total" in lk and "point" in lk):
                acc.setdefault("points_total", to_number(v))
            elif "expir" in lk or "过期" in str(k):
                acc.setdefault("points_expiring", to_number(v))
    return acc


def collect(token=None):
    client = McpClient(token=token)
    client.initialize()
    raw = {}
    for tool in TOOLS:
        try:
            raw[tool] = parse_markdown_payload(unwrap(client.call_tool(tool, {})))
            print("  ok   %s" % tool)
        except McpError as e:
            print("  fail %s -> %s" % (tool, e))
            raw[tool] = None
        save_raw(tool, raw[tool])

    nutrition_kcal, nutrition_price = {}, {}
    n_raw = raw.get("list-nutrition-foods")
    if isinstance(n_raw, str):
        nutrition_kcal = parse_nutrition_text(n_raw)
    elif isinstance(n_raw, dict) and isinstance(n_raw.get("data"), str):
        nutrition_kcal = parse_nutrition_text(n_raw["data"])
    elif n_raw:
        nutrition_kcal, nutrition_price = extract_nutrition(n_raw)

    orders = extract_orders(raw.get("order-list"), nutrition_kcal) if raw.get("order-list") else []
    mall = extract_simple_list(raw.get("mall-order-list"), NAME_KEYS, TIME_KEYS) \
        if raw.get("mall-order-list") else []
    coupons = extract_simple_list(raw.get("query-my-coupons"), NAME_KEYS) \
        if raw.get("query-my-coupons") else []
    prizes = extract_simple_list(raw.get("query-my-prizes"), NAME_KEYS, TIME_KEYS) \
        if raw.get("query-my-prizes") else []

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "mcp",
        "range_days": 365,
        "account": extract_account(raw.get("query-my-account")) if raw.get("query-my-account") else {},
        "orders": orders,
        "mall_orders": mall,
        "coupons": coupons,
        "prizes": prizes,
        "nutrition_price": nutrition_price,
        "nutrition_kcal": nutrition_kcal,
    }
    out = os.path.join(ROOT, "data", "report_data.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("collected %d orders -> %s" % (len(orders), out))
    print("  points      : %s" % data["account"])
    print("  mall orders : %d" % len(mall))
    print("  coupons     : %d" % len(coupons))
    print("  prizes      : %d" % len(prizes))
    print("  nutrition   : %d items mapped" % len(nutrition_kcal))
    if not orders:
        print("! no orders parsed. two possible causes:")
        print("  1. the account really has no order history (check data/raw/order-list.json)")
        print("  2. field mapping drifted -> extend the *_KEYS lists in collect.py")
    return data


def main():
    try:
        collect()
    except McpError as e:
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
