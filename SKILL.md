---
name: mcd-wrapped
description: 生成麦当劳年度报告（M-CODE WRAPPED）——基于麦当劳 MCP 拉取本人真实点餐、积分、优惠券与抽奖数据，聚合成一份可分享的年度数据年报网页，并可选用方言语音播报。当用户说"麦当劳年度报告""麦麦年报""今年在麦当劳花了多少钱""M-CODE WRAPPED""帮我看看我的麦当劳消费"时使用本技能。
agent_created: true
---

# M-CODE WRAPPED

把用户本人的麦当劳账户数据，变成一份可截图转发的年度报告网页，并可选生成方言语音版。

## 何时使用

- 想看自己在麦当劳一年的消费、点餐习惯、积分与券的情况
- 要一份能分享到社交平台的年度报告
- 要求用方言（粤语、四川话等）把报告念出来

## 前置条件

需要麦当劳 MCP Token（open.mcd.cn 用手机号申请）。没有 Token 时走 dry-run，用演示数据出样张。

## 工作流程

### 第一步：确认数据来源

- 有 Token：走真实采集（第二步）
- 无 Token：执行 `python3 scripts/demo_data.py` 生成演示数据，并明确告知用户当前是演示数据

### 第二步：采集真实数据

```bash
export MCD_MCP_TOKEN=<用户的token>
python3 scripts/collect.py
```

依次调用 `order-list`、`mall-order-list`、`query-my-account`、`query-my-coupons`、
`query-my-prizes`、`list-nutrition-foods`、`now-time-info`。原始响应全部落盘到
`data/raw/`，归一化结果写入 `data/report_data.json`。

若麦当劳 MCP 已作为连接器接入当前会话，也可直接调用这些 tool 并把结果交给
`collect.py` 的解析函数处理。两条路径二选一，不要重复调用。

解析出的订单数为 0 时，读 `data/raw/order-list.json`，按真实字段扩展 `collect.py`
顶部的 `TIME_KEYS` / `NAME_KEYS` / `PRICE_KEYS` 等候选键列表，不要改动数据结构。

### 第三步：生成报告

```bash
python3 scripts/build_report.py            # -> out/mcd-wrapped.html
python3 scripts/build_report.py --json     # 只看指标，不渲染
```

产出单文件 HTML，无外部依赖，可直接打开或截图。

### 第四步：方言播报（可选）

```bash
python3 scripts/speak.py --dialect cantonese    # 粤语
python3 scripts/speak.py --dialect voxcpm --ref /path/to/dialect.wav
python3 scripts/speak.py --dry-run              # 只打印播报稿
```

后端按 VoxCPM2 → macOS 内置中文嗓音顺序自动回退。VoxCPM2 需 `VOXCPM_API_URL`
指向本地 Gradio 服务，`VOXCPM_REF_AUDIO` 指向方言参考音频以克隆音色。

## 输出口径

只陈述事实，不做健康评价。禁止出现"垃圾食品""不健康""罪恶""发胖"等表述，
能量数字一律标注为估算参考值。完整红线见 `references/compliance.md`。

## 资源

- `scripts/mcp_client.py` — MCP Streamable HTTP 客户端，也可命令行列出/调用工具
- `scripts/collect.py` — 采集与字段归一化
- `scripts/demo_data.py` — 确定性演示数据，无 Token 也能出样张
- `scripts/build_report.py` — 指标计算与 HTML 渲染
- `scripts/speak.py` — 方言语音播报
- `assets/report_template.html` — 报告模板
- `references/mcp_tools.md` — 用到的 MCP tool 清单与字段说明
- `references/compliance.md` — 输出内容的合规红线
