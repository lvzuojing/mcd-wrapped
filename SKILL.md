---
name: mcd-wrapped
description: 麦当劳 MCP 工具箱：探测全部 35 个 tool 的真实返回、生成个人年度消费年报、生成麦当劳数据全景报告、精算积分抽奖期望值，并可选方言语音播报。当用户说"麦当劳 MCP 有哪些能力""麦当劳年度报告""麦麦数据""麦当劳全景""抽奖值不值""今年在麦当劳花了多少钱""M-CODE WRAPPED"时使用本技能。
agent_created: true
---

# M-CODE WRAPPED

麦当劳数据全景报告 + 个人年度消费年报 + 方言语音播报。

## 何时使用

- 想搞清楚麦当劳 MCP 的 35 个 tool 各自返回什么、需要什么参数
- 要一份可分享/可发朋友圈的麦当劳年报或全景报告
- 想看自己在麦当劳一年的消费记录
- 想知道积分抽奖到底值不值得抽
- 想让 AI 用粤语/方言把报告念出来

## 前置条件

- 麦当劳 MCP Token：在 open.mcd.cn 用手机号激活后复制 Token
- 无 Token 时也能用演示数据出样张

## 工作流程

### 探测 MCP 能力（调试优先）

```bash
export MCD_MCP_TOKEN=<用户的token>
python3 scripts/explore.py       # -> out/mcp-explorer.md + data/tool_inventory.json
```

自动串联参数：从 `order-list` 取 `storeCode` / `orderId`，从 `mall-points-products`
取 `spuId`，喂给需要参数的 tool。
`draw-lottery`、`create-order`、`cancel-order`、`mall-create-order`、`auto-bind-coupons`、
`party-order-create`、`delivery-create-address` 属于写操作，**一律不调用**。

### 抽奖 EV 精算

```bash
python3 scripts/lottery_ev.py                    # 10 连抽 × 10000 轮
python3 scripts/lottery_ev.py --draws 50 --trials 50000
```

输出必须说明：官方未公布中奖概率，结果为等概率假设下的模拟。

### 公共全景报告（不需要消费记录）

```bash
export MCD_MCP_TOKEN=<用户的token>
python3 scripts/public_data.py      # 采集公共数据 -> data/public_data.json
python3 scripts/build_panorama.py    # -> out/mcd-wrapped.html
```

### 个人年度消费年报

```bash
export MCD_MCP_TOKEN=<用户的token>
python3 scripts/collect.py          # 采集个人数据 -> data/report_data.json
python3 scripts/build_report.py     # -> out/mcd-wrapped.html
```

### 演示模式（无 Token）

```bash
python3 scripts/demo_data.py
python3 scripts/build_report.py
```

### 方言播报（可选）

```bash
python3 scripts/speak.py --dialect cantonese
python3 scripts/speak.py --dialect voxcpm --ref /path/to/dialect.wav
python3 scripts/speak.py --dry-run
```

后端按 VoxCPM2 → macOS 内置中文嗓音顺序自动回退。

## 输出口径

只陈述事实，不做健康评价。禁止出现"垃圾食品""不健康""罪恶""发胖"等表述，
能量数字一律标注为估算参考值。完整红线见 `references/compliance.md`。

## 资源

- `scripts/mcp_client.py` — MCP Streamable HTTP 客户端
- `scripts/public_data.py` — 公共数据采集与解析
- `scripts/build_panorama.py` — 全景报告渲染
- `scripts/collect.py` — 个人数据采集与字段归一化
- `scripts/demo_data.py` — 确定性演示数据
- `scripts/build_report.py` — 个人年报渲染
- `scripts/speak.py` — 方言语音播报
- `assets/panorama_template.html` — 全景报告模板
- `assets/report_template.html` — 个人年报模板
- `references/mcp_tools.md` — MCP tool 清单与踩坑记录
- `references/compliance.md` — 合规红线
