#!/usr/bin/env python3
"""Expected-value calculator for the McDonald's points lottery.

    python3 scripts/lottery_ev.py                 # use cached public data
    python3 scripts/lottery_ev.py --live          # re-pull from MCP
    python3 scripts/lottery_ev.py --draws 10 --trials 20000
    python3 scripts/lottery_ev.py --base-price 45 # discount-voucher baseline

The prize pool and per-draw cost are real (query-lottery-info). The winning
probabilities are NOT published by McDonald's, so this script simulates under
an explicit equal-probability assumption and says so in every output. Coupon
face values are parsed from prize names; discount vouchers are valued against
a configurable basket price because the pool carries no prices.

It never calls draw-lottery. Simulation only, no points are spent.
"""

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_DATA = os.path.join(ROOT, "data", "public_data.json")
OUT_MD = os.path.join(ROOT, "out", "lottery-ev.md")

DISCOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*折")
CASH_RE = re.compile(r"立减\s*(\d+(?:\.\d+)?)\s*元")
POINTS_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*积分$")


def parse_markdown_payload(raw):
    from collect import parse_markdown_payload as _p
    return _p(raw)


# A 5-off voucher is worth very different amounts depending on what it applies
# to, so pick a basket price that matches the prize name before falling back.
BASE_HINTS = [
    ("麦旋风", 9.0), ("甜筒", 7.0), ("薯条", 13.0), ("麦辣鸡翅", 15.0),
    ("四件套", 46.0), ("三件套", 40.0), ("小食", 26.0), ("套餐", 36.0),
    ("咖啡", 18.0), ("早餐", 20.0),
]


def estimate_value(name, base_price):
    """Return (yuan, points, kind) parsed from a prize name.

    Yuan figures are estimates: the pool carries no prices, so discount
    vouchers are valued against a basket price inferred from the prize name
    (or --base-price when nothing matches).
    """
    name = (name or "").strip()
    m = POINTS_RE.match(name)
    if m:
        return 0.0, float(m.group(1)), "积分"
    m = CASH_RE.search(name)
    if m:
        return float(m.group(1)), 0.0, "立减券"
    m = DISCOUNT_RE.search(name)
    if m:
        rate = float(m.group(1)) / 10.0
        if 0 < rate < 1:
            price = base_price
            for hint, p in BASE_HINTS:
                if hint in name:
                    price = p
                    break
            return round(price * (1 - rate), 2), 0.0, "折扣券"
    return 0.0, 0.0, "未识别"


def load_lottery(args):
    if args.live:
        from mcp_client import McpClient, unwrap
        c = McpClient()
        c.initialize()
        return parse_markdown_payload(unwrap(c.call_tool("query-lottery-info", {})))
    with open(DEFAULT_DATA, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("lottery") or {}


def normalise(lot):
    if not lot:
        return None
    prizes = lot.get("prizes") or []
    cost = float(lot.get("cost") or 0)
    return {
        "name": lot.get("name") or "麦麦积分抽奖",
        "status": lot.get("status") or "",
        "window": lot.get("window") or "",
        "cost": cost,
        "prizes": [p.get("name") for p in prizes if isinstance(p, dict)],
    }


def simulate(prizes, trials, draws, seed=42):
    """Equal-probability Monte Carlo over `trials` runs of `draws` draws."""
    rnd = random.Random(seed)
    n = len(prizes)
    yuan_tot, point_tot = 0.0, 0.0
    hit_any = 0
    hit_points = 0
    per_prize = {p["name"]: 0 for p in prizes}
    for _ in range(trials):
        got_yuan = got_points = 0.0
        got_any = False
        for _ in range(draws):
            p = prizes[rnd.randrange(n)]
            got_yuan += p["yuan"]
            got_points += p["points"]
            if p["kind"] != "未识别":
                got_any = True
            if p["kind"] == "积分":
                hit_points += 1
            per_prize[p["name"]] += 1
        yuan_tot += got_yuan
        point_tot += got_points
        if got_any:
            hit_any += 1
    return {
        "avg_yuan": yuan_tot / trials,
        "avg_points": point_tot / trials,
        "p_any": hit_any / trials,
        "p_points": hit_points / (trials * draws),
        "per_prize": {k: v / (trials * draws) for k, v in per_prize.items()},
    }


def render_md(info, prizes, sim, args, generated_at):
    cost = info["cost"]
    draws = args.draws
    spend = cost * draws
    L = ["# 麦麦积分抽奖 · 期望值精算", "",
         "由 `scripts/lottery_ev.py` 生成 · %s" % generated_at, "",
         "## 活动信息", "",
         "| 项 | 值 |", "|---|---|",
         "| 活动 | %s |" % info["name"],
         "| 状态 | %s |" % info["status"],
         "| 周期 | %s |" % info["window"],
         "| 单次消耗 | %g 积分 |" % cost,
         "| 奖品种类 | %d |" % len(prizes), "",
         "## 奖池明细（等概率假设）", "",
         "| 奖品 | 类型 | 估值 | 单次中签率 |",
         "|---|---|---|---|"]
    for p in prizes:
        val = ("¥%.2f" % p["yuan"]) if p["yuan"] else ("%g 积分" % p["points"])
        L.append("| %s | %s | %s | %.1f%% |"
                 % (p["name"], p["kind"], val, 100.0 / len(prizes)))
    L += ["", "## 模拟结果", "",
          "- 场景：每次抽 **%d** 连抽，共模拟 **%s** 次" % (draws, format(args.trials, ",")),
          "- 每轮消耗：**%g 积分**" % spend,
          "- 每轮期望券面额：**¥%.2f**" % sim["avg_yuan"],
          "- 每轮期望积分返还：**%.1f 积分**（回本率 %.1f%%）"
          % (sim["avg_points"], 100.0 * sim["avg_points"] / spend if spend else 0),
          "- 至少中 1 个有效奖的概率：**%.1f%%**" % (100 * sim["p_any"]),
          "- 单次抽中积分奖的概率：**%.1f%%**" % (100 * sim["p_points"]), "",
          "## 结论", ""]
    if sim["avg_points"] and spend:
        L.append("- 只算积分返还的话，每 %g 积分只能换回 %.1f 积分，"
                 "**净亏 %.1f 积分**。抽奖的真实价值在券，不在积分。"
                 % (spend, sim["avg_points"], spend - sim["avg_points"]))
    L.append("- 券只有真正用掉才产生价值。抽到不用的券，等于 %g 积分打水漂。" % spend)
    L.append("- 折扣券按单均 ¥%g 估算面额，实际价值随你点的东西浮动。" % args.base_price)
    L += ["", "> **重要**：麦当劳未公布各奖品中奖概率，以上均基于**等概率假设**模拟，",
          "> 不代表真实中奖率。本脚本只做模拟，从不调用 `draw-lottery`，不消耗任何积分。"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="重新从 MCP 拉取奖池")
    ap.add_argument("--draws", type=int, default=10, help="每轮抽几次（默认 10）")
    ap.add_argument("--trials", type=int, default=10000, help="模拟轮数（默认 10000）")
    ap.add_argument("--base-price", type=float, default=40.0,
                    help="折扣券的基准单价（默认 40 元）")
    args = ap.parse_args()

    raw = load_lottery(args)
    if isinstance(raw, dict) and "data" in raw:
        node = raw["data"]
        info = {
            "name": node.get("activityName") or "麦麦积分抽奖",
            "status": node.get("activityStatusText") or "",
            "window": "%s ~ %s" % (str(node.get("beginTime") or "")[:10],
                                   str(node.get("endTime") or "")[:10]),
            "cost": float(node.get("drawPoint") or 0),
            "prizes": [p.get("name") for p in (node.get("prizes") or [])
                       if isinstance(p, dict)],
        }
    else:
        info = normalise(raw)
    if not info or not info["prizes"]:
        print("没有拿到奖池数据，先跑 scripts/public_data.py 或加 --live", file=sys.stderr)
        sys.exit(1)

    prizes = []
    for name in info["prizes"]:
        yuan, points, kind = estimate_value(name, args.base_price)
        prizes.append({"name": name, "yuan": yuan, "points": points, "kind": kind})

    sim = simulate(prizes, args.trials, args.draws)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = render_md(info, prizes, sim, args, generated_at)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    print("活动: %s（%s）" % (info["name"], info["status"]))
    print("单次消耗: %g 积分 · 奖池 %d 种" % (info["cost"], len(prizes)))
    print()
    print("%-24s %-8s %-12s" % ("奖品", "类型", "估值"))
    for p in prizes:
        val = ("¥%.2f" % p["yuan"]) if p["yuan"] else ("%g 积分" % p["points"])
        print("%-24s %-8s %-12s" % (p["name"][:24], p["kind"], val))
    print()
    print("每轮 %d 连抽 = %g 积分，模拟 %s 轮：" % (args.draws, info["cost"] * args.draws,
                                                    format(args.trials, ",")))
    print("  期望券面额      ¥%.2f" % sim["avg_yuan"])
    print("  期望积分返还    %.1f 积分" % sim["avg_points"])
    print("  至少中一奖      %.1f%%" % (100 * sim["p_any"]))
    print("\n报告: %s" % OUT_MD)


if __name__ == "__main__":
    main()
