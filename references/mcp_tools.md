# 用到的麦当劳 MCP Tool

麦当劳 MCP Server 共开放 33 个 tool（`M-China/mcd-mcp-server`）。本项目实际使用其中 7 个。

## 实际调用清单

| Tool | 用途 | 在报告中的落点 |
|---|---|---|
| `order-list` | 查询近期到店/外送历史订单 | 年度概览、月度趋势、高频单品、深夜订单、门店排行、连续打卡 |
| `mall-order-list` | 查询麦麦商城近一年兑换/购买订单 | 积分与券板块 |
| `query-my-account` | 积分账户：可用、累计、冻结、即将过期 | 可用积分、即将过期积分 |
| `query-my-coupons` | 我的优惠券列表 | 在手优惠券数量 |
| `query-my-prizes` | 积分抽奖获得的奖品记录 | 抽奖获得奖品数量 |
| `list-nutrition-foods` | 餐品营养成分（能量/蛋白质/脂肪/碳水/钠/钙） | 订单热量估算，换算为中性参照值 |
| `now-time-info` | 当前时间 | 报告生成时间戳 |

## 实测返回结构（2026-10-09）

`order-list` 入参为空对象，无必填参数。真实返回路径为 `data.list[]`：

```
data.list[].orderId            订单编码
data.list[].orderType          订单类型
data.list[].createTime         下单时间
data.list[].storeName          门店名称
data.list[].storeCode / beCode / beType
data.list[].orderStatus        订单状态
data.list[].realTotalAmount    实付总金额
data.list[].orderProductList[] 商品
    .productCode / .productName / .quantity / .comboItemList
```

`mall-order-list` 路径为 `data[].list[]`（外层还有 `hasNext`、`lastId`），
商品在 `.goods[]`，入参支持 `size`（默认 10，上限 10）与 `lastId` 分页。

`query-my-account` 路径为 `data`，字段：
`availablePoint` `accumulativePoint` `usedPoint` `frozenPoint`
`expiredPoint` `currentMouthExpirePoint` `nextMouthExpirePoint` `lastMouthExpirePoint`
（均为字符串类型的数字）

`query-my-prizes` 路径为 `data.prizes[]`，字段 `name` `recordTime` `statusText`。

`list-nutrition-foods` 的 `data` 是文本表格，表头：
`productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium`

## 未使用但可扩展

- `query-nearby-stores` / `delivery-query-stores`：门店维度分析
- `campaign-calendar`：把营销活动叠加到时间轴上
- `query-lottery-info` / `draw-lottery`：抽奖战绩（调用会真实消耗积分，需显式确认）
- `query-meal-detail`：拆解套餐组成，细化单品统计
- `query-party-*`：团建派对场景

## 字段归一化说明

麦当劳 MCP 返回的字段名以服务端为准，`scripts/collect.py` 采用候选键匹配 +
递归遍历的方式提取，避免硬绑定。当前候选键：

- 时间：`orderTime` `createTime` `createdAt` `payTime` `gmtCreate` `time` `date` `orderDate` `createAt`
- 名称：`mealName` `productName` `itemName` `goodsName` `name` `title`
- 金额：`price` `amount` `payAmount` `totalAmount` `realAmount` `sellPrice`
- 数量：`quantity` `qty` `num` `count`
- 门店：`storeName` `shopName` `store` `shop` `restaurantName`
- 渠道：`channel` `orderType` `scene` `deliveryType` `dineType`

若真实返回字段不在此列，读 `data/raw/*.json` 后把新键名补进对应列表即可。

## 调用约束

- 传输：Streamable HTTP，端点 `https://mcp.mcd.cn`
- 鉴权：`Authorization: Bearer <token>`
- 限流：每 Token 600 次/分钟，超限返回 429
- 支付：MCP 只返回支付链接，不能代付。本项目只读，不创建任何订单
