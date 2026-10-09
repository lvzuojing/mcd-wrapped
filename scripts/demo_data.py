#!/usr/bin/env python3
"""Generate a deterministic demo dataset so the report can be previewed
without an MCP token (dry-run mode).

Output shape is identical to scripts/collect.py, so build_report.py works on
both real and demo data with no branching.
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MENU = [
    ("巨无霸", 24.0, 520),
    ("板烧鸡腿堡", 22.0, 480),
    ("麦香鱼", 18.0, 390),
    ("麦辣鸡腿堡", 21.0, 570),
    ("双层吉士汉堡", 15.0, 440),
    ("麦辣鸡翅(2块)", 13.0, 260),
    ("麦乐鸡(5块)", 14.0, 230),
    ("中薯条", 12.0, 330),
    ("大薯条", 15.0, 480),
    ("玉米杯", 8.0, 90),
    ("中可乐", 9.0, 150),
    ("零度可乐", 9.0, 0),
    ("麦旋风", 12.0, 280),
    ("香芋派", 8.0, 240),
    ("猪柳蛋麦满分", 16.0, 410),
    ("热香饼(2块)", 12.0, 350),
    ("拿铁(中)", 18.0, 120),
    ("鲜煮咖啡", 12.0, 15),
    ("橙汁", 10.0, 110),
    ("脆薯饼", 7.0, 150),
]

STORES = [
    "麦当劳(望京SOHO店)",
    "麦当劳(中关村创业大街店)",
    "麦当劳(国贸三期店)",
    "麦当劳(西二旗地铁站店)",
    "麦当劳(五道口购物中心店)",
]

CHANNELS = ["到店取餐", "麦乐送", "到店取餐", "麦乐送", "到店取餐"]

NUTRITION_KCAL = {name: kcal for name, _, kcal in MENU}
NUTRITION_PRICE = {name: price for name, price, _ in MENU}


def build(days=365, orders=138, seed=1024):
    rng = random.Random(seed)
    now = datetime.now()
    start = now - timedelta(days=days)

    order_list = []
    for i in range(orders):
        # bias toward lunch (11-13) and dinner (18-20), with a late-night tail
        roll = rng.random()
        if roll < 0.34:
            hour = rng.choice([11, 12, 12, 13])
        elif roll < 0.62:
            hour = rng.choice([18, 19, 19, 20])
        elif roll < 0.72:
            hour = rng.choice([7, 8, 8, 9])
        elif roll < 0.82:
            hour = rng.choice([22, 23, 0, 1])
        else:
            hour = rng.choice([14, 15, 16, 21])

        offset = rng.random() * days
        ts = start + timedelta(days=offset)
        ts = ts.replace(hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59))

        n_items = rng.choices([1, 2, 3, 4], weights=[0.2, 0.4, 0.28, 0.12])[0]
        picks = rng.sample(MENU, n_items)
        items = []
        total = 0.0
        kcal = 0
        for name, price, kc in picks:
            qty = 1 if rng.random() < 0.85 else 2
            items.append({"name": name, "qty": qty, "price": round(price * qty, 2)})
            total += price * qty
            kcal += kc * qty

        discount = round(total * rng.choice([0, 0, 0.15, 0.25, 0.3]), 2)
        order_list.append({
            "order_id": "MCD%013d" % (2026000000000 + i),
            "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "store": rng.choice(STORES),
            "channel": rng.choice(CHANNELS),
            "items": items,
            "discount": discount,
            "total": round(total - discount, 2),
            "kcal": kcal,
        })

    order_list.sort(key=lambda o: o["time"])

    mall_orders = []
    for i in range(9):
        ts = start + timedelta(days=rng.random() * days)
        mall_orders.append({
            "order_id": "MALL%011d" % (800000000 + i),
            "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "name": rng.choice([
                "麦当劳圆筒冰淇淋兑换券", "麦麦周边·程序员徽章",
                "中薯条兑换券", "麦咖啡拿铁券", "麦麦商城·麦麦乐积木",
            ]),
            "points": rng.choice([200, 300, 500, 800, 1200]),
        })

    data = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "demo",
        "range_days": days,
        "account": {
            "points_available": 1280,
            "points_total": 5240,
            "points_expiring": 300,
        },
        "orders": order_list,
        "mall_orders": mall_orders,
        "coupons": [
            {"name": "巨无霸三件套29.9元券", "status": "unused"},
            {"name": "麦麦省·满30减5", "status": "unused"},
            {"name": "麦乐送免配送费券", "status": "unused"},
        ],
        "prizes": [
            {"name": "中可乐兑换券", "time": (now - timedelta(days=41)).strftime("%Y-%m-%d")},
            {"name": "麦旋风兑换券", "time": (now - timedelta(days=88)).strftime("%Y-%m-%d")},
        ],
        "nutrition_price": NUTRITION_PRICE,
        "nutrition_kcal": NUTRITION_KCAL,
    }
    return data


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "report_data.json")
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    data = build()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("demo data written: %s (%d orders)" % (out, len(data["orders"])))


if __name__ == "__main__":
    main()
