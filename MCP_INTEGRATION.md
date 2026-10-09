# MCP 集成说明

## 使用的 MCP Server

- **名称：** 麦当劳 MCP 服务（McDonald's China MCP Server）
- **接入地址：** `https://mcp.mcd.cn`
- **传输协议：** Streamable HTTP
- **鉴权方式：** `Authorization: Bearer <token>`，Token 在 open.mcd.cn 用手机号申请
- **限流：** 每 Token 600 次/分钟（429 表示超限）
- **文档仓库：** https://github.com/M-China/mcd-mcp-server

项目自带独立客户端 `scripts/mcp_client.py`，不依赖任何第三方 MCP SDK，
Python 3.9+ 标准库即可运行。脱敏配置见 `mcp-config.example.json`。

## 调用的 Tool 与业务价值

| Tool | 调用目的 | 业务价值 |
|---|---|---|
| `order-list` | 拉取近期到店/外送历史订单 | 年报主干数据：消费额、客单价、月度趋势、高频单品、门店排行、深夜下单、连续打卡 |
| `mall-order-list` | 拉取麦麦商城近一年兑换/购买订单 | 呈现积分的实际去向，让"积分花在哪"首次可见 |
| `query-my-account` | 读取积分账户（可用/累计/冻结/即将过期） | 提示即将过期积分，避免用户积分作废 |
| `query-my-coupons` | 读取在手优惠券 | 汇总未使用券，衔接"省了多少钱" |
| `query-my-prizes` | 读取抽奖获得的奖品记录 | 把抽奖战绩并入年度报告 |
| `list-nutrition-foods` | 获取餐品能量数据 | 为订单估算能量，换算成中性参照值（步行里程、京沪长途） |
| `now-time-info` | 获取当前时间 | 报告生成时间戳 |

合计使用 7 个 tool。全部为只读调用，项目不创建、不取消、不支付任何订单；
`draw-lottery` 会真实消耗积分，默认流程不调用。

## 调用流程

```
1. initialize            -> 建立会话，取回 Mcp-Session-Id
2. notifications/initialized
3. tools/call now-time-info
4. tools/call query-my-account
5. tools/call order-list            （年报主干）
6. tools/call mall-order-list
7. tools/call query-my-coupons
8. tools/call query-my-prizes
9. tools/call list-nutrition-foods
      |
      v
   字段归一化（候选键匹配 + 递归提取，兼容服务端字段变更）
      |
      v
   data/report_data.json
      |
      v
   指标计算 -> HTML 渲染 -> out/mcd-wrapped.html
      |
      v
   可选：方言语音播报（scripts/speak.py）
```

## MCP 能力带来的关键差异

没有 MCP 时，这些数据分散在 App 的各个页面里——订单在"我的订单"，积分在"会员中心"，
券在"卡包"，抽奖记录在活动页，用户无法把它们放在一起看，更无法回顾一整年。

麦当劳 MCP 把这些数据统一成可编程接口，`mcd-wrapped` 在此之上做了三件事：

1. **跨模块聚合**：订单 + 商城 + 积分 + 券 + 抽奖，五路数据合成一份报告，
   这是 App 内任何单个页面都给不出的视角。
2. **时间维度还原**：把一年的订单按小时、星期、月份重排，还原出下单高峰、
   深夜时段、连续打卡等行为模式。
3. **可分享的产物**：输出单文件 HTML，可截图、可转发；
   再用方言 TTS 生成语音版，让报告不只能看，还能听。

## 字段兼容策略

麦当劳 MCP 的返回字段以服务端为准。项目不做硬绑定，而是用候选键列表 +
递归遍历的方式提取（见 `references/mcp_tools.md`），每次采集都会把原始响应
落盘到 `data/raw/`，字段变化时只需补键名，无需改动数据结构。
