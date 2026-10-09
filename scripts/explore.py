#!/usr/bin/env python3
"""Probe the whole McDonald's MCP surface and write a readable inventory.

    export MCD_MCP_TOKEN=xxx
    python3 scripts/explore.py                 # -> out/mcp-explorer.md + data/tool_inventory.json
    python3 scripts/explore.py --no-arg-only   # skip tools that need parameters

Why this exists: the official docs list the tools but not what they actually
return. In practice the server answers with Markdown wrappers, delimited text
tables and Chinese "no data" strings -- none of which is documented. This
script calls every read-only tool, records the real response shape, and chains
values across tools (an orderId from order-list feeds query-order, a storeCode
feeds query-meals) so parametrised tools get exercised too.

SAFETY: tools that spend points, place, cancel or redeem orders are never
called. They are listed with their parameter schema only.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collect import parse_markdown_payload  # noqa: E402
from mcp_client import McpClient, McpError, unwrap  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_MD = os.path.join(ROOT, "out", "mcp-explorer.md")
OUT_JSON = os.path.join(ROOT, "data", "tool_inventory.json")

# Never call these. They spend points, create/cancel orders or mutate the
# account. Listed in the report with their schema only.
WRITE_TOOLS = {
    "draw-lottery": "消耗积分抽奖",
    "create-order": "创建点餐订单",
    "cancel-order": "取消订单",
    "mall-create-order": "积分兑换下单（扣积分）",
    "auto-bind-coupons": "一键领取全部优惠券（改变账户状态）",
    "party-order-create": "创建派对订单",
    "delivery-create-address": "新增配送地址",
}

# Where to find a value for a required parameter, by digging into an earlier
# response. (source tool, json path)
ARG_SOURCES = {
    "storeCode": ("order-list", ["data", "list", 0, "storeCode"]),
    "orderId": ("order-list", ["data", "list", 0, "orderId"]),
    "spuId": ("mall-points-products", ["data", 0, "spuId"]),
    "code": ("order-list", ["data", "list", 0, "orderProductList", 0, "productCode"]),
    "skuId": ("mall-points-products", ["data", 0, "spuId"]),
    "addressId": ("delivery-query-addresses", ["data", 0, "addressId"]),
}
# Literal fallbacks for enum-ish parameters.
ARG_DEFAULTS = {
    "beType": "1",
    "orderType": "1",
    "searchType": "1",
    "page": "1",
    "pageSize": "20",
    "pageNum": "1",
    "size": "10",
    "count": "1",
    "spuCategory": "1",
    "dateStr": datetime.now().strftime("%Y-%m-%d"),
    "specifiedDate": datetime.now().strftime("%Y-%m-%d"),
    "reservationDate": datetime.now().strftime("%Y-%m-%d"),
    "city": "合肥",
    "keyword": "麦当劳",
}

EMPTY_CN = ("暂无", "没有找到", "无可用", "未查询到", "no data", "无数据")


def dig(obj, path):
    cur = obj
    for p in path:
        try:
            cur = cur[p]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def classify(text):
    """Guess what the server actually sent back."""
    if not isinstance(text, str):
        return "json"
    if "## Original Response" in text or "# API Response Information" in text:
        return "markdown-wrapper"
    if re.search(r"\{[^}]*productName[^}]*\}\s*:", text):
        return "text-table"
    if any(w in text for w in EMPTY_CN):
        return "empty-cn"
    if text.strip().startswith("{") or text.strip().startswith("["):
        return "json"
    return "text"


def count_items(obj):
    """Best-effort row count for the payload."""
    if obj is None:
        return 0
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        best = 0
        for v in obj.values():
            if isinstance(v, list):
                best = max(best, len(v))
            elif isinstance(v, dict):
                best = max(best, count_items(v))
        return best
    return 0


def probe(client, tools, ctx, call_parametrised=True):
    results = []
    for t in tools:
        name = t["name"]
        schema = t.get("inputSchema") or {}
        props = list((schema.get("properties") or {}).keys())
        required = schema.get("required") or []
        row = {
            "tool": name,
            "desc": (t.get("description") or "")[:120],
            "required": required,
            "properties": props,
        }

        if name in WRITE_TOOLS:
            row.update(category="write", status="skipped",
                       reason=WRITE_TOOLS[name], shape="-", items=0)
            results.append(row)
            continue

        args = {}
        missing = []
        for p in required:
            if p in ARG_DEFAULTS:
                args[p] = ARG_DEFAULTS[p]
                continue
            src = ARG_SOURCES.get(p)
            val = None
            if src:
                raw = ctx.get(src[0])
                if raw is not None:
                    val = dig(raw, src[1])
            if val not in (None, ""):
                args[p] = val
            else:
                missing.append(p)

        if missing:
            row.update(category="read-param", status="needs-param",
                       reason="缺少 " + ",".join(missing), shape="-", items=0,
                       args=args)
            results.append(row)
            continue

        if required and not call_parametrised:
            row.update(category="read-param", status="skipped",
                       reason="--no-arg-only", shape="-", items=0)
            results.append(row)
            continue

        try:
            raw = unwrap(client.call_tool(name, args))
            shape = classify(raw)
            # Cache the *parsed* payload so later tools can borrow values
            # (storeCode, orderId, spuId) out of it.
            parsed = parse_markdown_payload(raw) if isinstance(raw, str) else raw
            if shape != "empty-cn":
                ctx[name] = parsed
            row.update(category="read" if not required else "read-param",
                       status="ok", shape=shape,
                       items=count_items(parsed) if isinstance(parsed, (dict, list)) else 0,
                       size=len(json.dumps(parsed, ensure_ascii=False, default=str))
                       if not isinstance(parsed, str) else len(parsed),
                       args=args,
                       sample=json.dumps(parsed, ensure_ascii=False, default=str)[:400]
                       if not isinstance(parsed, str) else parsed[:400])
        except McpError as e:
            row.update(category="read" if not required else "read-param",
                       status="error", reason=str(e)[:120], shape="-", items=0,
                       args=args)
        results.append(row)
    return results


SHAPE_NOTE = {
    "markdown-wrapper": "返回 Markdown，真 JSON 在 `## Original Response` 之后",
    "text-table": "返回逗号分隔文本表格，不是 JSON",
    "empty-cn": "无数据时返回中文文案，不是空数组",
    "json": "标准 JSON",
    "text": "纯文本",
}


def render_md(results, generated_at):
    ok = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skipped"
               and r["category"] == "write"]
    need = [r for r in results if r["status"] == "needs-param"]
    err = [r for r in results if r["status"] == "error"]

    L = ["# 麦当劳 MCP 能力探测报告", "",
         "由 `scripts/explore.py` 实时调用生成 · %s" % generated_at, "",
         "## 总览", "",
         "| 类别 | 数量 |", "|---|---|",
         "| 只读工具（无参数） | %d |" % len([r for r in ok if not r["required"]]),
         "| 只读工具（需参数，已自动串联） | %d |" % len([r for r in ok if r["required"]]),
         "| 需参数但未取到值 | %d |" % len(need),
         "| 调用失败 | %d |" % len(err),
         "| 写操作（已跳过，不调用） | %d |" % len(skipped), "",
         "## 已成功调用的工具", "",
         "| Tool | 入参 | 返回形态 | 数据条数 | 响应大小 |",
         "|---|---|---|---|---|"]
    for r in ok:
        L.append("| `%s` | %s | %s | %d | %s |"
                 % (r["tool"], ", ".join(r["required"]) or "无",
                    r["shape"], r["items"], r.get("size", "-")))
    if need:
        L += ["", "## 需要参数（本次未取到值）", "",
              "| Tool | 缺少 | 参数定义 |", "|---|---|---|"]
        for r in need:
            L.append("| `%s` | %s | %s |" % (r["tool"], r["reason"],
                                             ", ".join(r["properties"]) or "-"))
    if err:
        L += ["", "## 调用失败", "", "| Tool | 错误 |", "|---|---|"]
        for r in err:
            L.append("| `%s` | %s |" % (r["tool"], r.get("reason", "")))
    L += ["", "## 写操作（安全起见不调用）", "",
          "| Tool | 风险 | 必填入参 |", "|---|---|---|"]
    for r in skipped:
        L.append("| `%s` | %s | %s |" % (r["tool"], r["reason"],
                                         ", ".join(r["required"]) or "-"))
    L += ["", "## 返回形态说明", ""]
    for k, v in SHAPE_NOTE.items():
        L.append("- **%s**：%s" % (k, v))
    L += ["", "> 这些行为官方文档均未说明，均为实测所得。",
          "> 写操作工具（下单/取消/抽奖/兑换/领券）本脚本一律不调用，仅展示参数定义。"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-arg-only", action="store_true",
                    help="只调用不需要参数的工具")
    args = ap.parse_args()

    client = McpClient()
    client.initialize()
    tools = client.list_tools()
    tools.sort(key=lambda t: (bool((t.get("inputSchema") or {}).get("required")),
                              t["name"]))
    print("probing %d tools..." % len(tools))

    ctx = {}
    results = probe(client, tools, ctx, call_parametrised=not args.no_arg_only)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = render_md(results, generated_at)
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"generated_at": generated_at, "tools": results},
                  f, ensure_ascii=False, indent=2)

    ok = [r for r in results if r["status"] == "ok"]
    print("\n%-28s %-8s %-18s %s" % ("TOOL", "STATUS", "SHAPE", "ITEMS"))
    for r in results:
        print("%-28s %-8s %-18s %s"
              % (r["tool"], r["status"], r.get("shape", "-"), r.get("items", 0)))
    print("\n成功 %d / 共 %d" % (len(ok), len(results)))
    print("报告: %s" % OUT_MD)
    print("数据: %s" % OUT_JSON)


if __name__ == "__main__":
    main()
