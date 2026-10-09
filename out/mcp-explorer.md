# 麦当劳 MCP 能力探测报告

由 `scripts/explore.py` 实时调用生成 · 2026-10-09 20:04:54

## 总览

| 类别 | 数量 |
|---|---|
| 只读工具（无参数） | 12 |
| 只读工具（需参数，已自动串联） | 15 |
| 需参数但未取到值 | 1 |
| 调用失败 | 0 |
| 写操作（已跳过，不调用） | 7 |

## 已成功调用的工具

| Tool | 入参 | 返回形态 | 数据条数 | 响应大小 |
|---|---|---|---|---|
| `available-coupons` | 无 | text | 0 | 2903 |
| `campaign-calendar` | 无 | text | 0 | 8747 |
| `delivery-query-addresses` | 无 | text | 0 | 2 |
| `list-nutrition-foods` | 无 | markdown-wrapper | 0 | 6319 |
| `mall-order-list` | 无 | markdown-wrapper | 1 | 186 |
| `mall-points-products` | 无 | markdown-wrapper | 50 | 14572 |
| `now-time-info` | 无 | markdown-wrapper | 0 | 406 |
| `order-list` | 无 | markdown-wrapper | 10 | 5121 |
| `query-lottery-info` | 无 | markdown-wrapper | 10 | 1594 |
| `query-my-account` | 无 | markdown-wrapper | 0 | 425 |
| `query-my-coupons` | 无 | text | 0 | 8833 |
| `query-my-prizes` | 无 | markdown-wrapper | 7 | 1389 |
| `calculate-price` | storeCode, orderType, beType | markdown-wrapper | 0 | 137 |
| `mall-order-detail` | orderId | markdown-wrapper | 0 | 131 |
| `mall-product-detail` | spuId | markdown-wrapper | 1 | 3058 |
| `query-meal-assistance` | storeCode | markdown-wrapper | 0 | 147 |
| `query-meal-detail` | storeCode, orderType, beType, code | markdown-wrapper | 0 | 148 |
| `query-meals` | storeCode, orderType, beType | markdown-wrapper | 15 | 30405 |
| `query-nearby-stores` | beType, searchType | text | 0 | 2 |
| `query-order` | orderId | markdown-wrapper | 1 | 1080 |
| `query-party-city` | spuId | markdown-wrapper | 281 | 31585 |
| `query-party-store` | code | markdown-wrapper | 0 | 132 |
| `query-party-store-date` | spuId, storeCode | markdown-wrapper | 0 | 143 |
| `query-party-store-session` | spuId, storeCode, dateStr | markdown-wrapper | 0 | 143 |
| `query-promotions` | storeCode, orderType, beType | markdown-wrapper | 12 | 5570 |
| `query-store-coupons` | orderType, beType, storeCode | text | 0 | 2 |
| `query-survey-coupon` | orderId | markdown-wrapper | 0 | 137 |

## 需要参数（本次未取到值）

| Tool | 缺少 | 参数定义 |
|---|---|---|
| `delivery-query-stores` | 缺少 addressId | addressId, beType |

## 写操作（安全起见不调用）

| Tool | 风险 | 必填入参 |
|---|---|---|
| `auto-bind-coupons` | 一键领取全部优惠券（改变账户状态） | - |
| `draw-lottery` | 消耗积分抽奖 | - |
| `cancel-order` | 取消订单 | orderId, cancelReasonCode |
| `create-order` | 创建点餐订单 | storeCode, orderType, beType |
| `delivery-create-address` | 新增配送地址 | address, addressDetail, city, contactName, phone |
| `mall-create-order` | 积分兑换下单（扣积分） | skuId, spuCategory |
| `party-order-create` | 创建派对订单 | partyType |

## 返回形态说明

- **markdown-wrapper**：返回 Markdown，真 JSON 在 `## Original Response` 之后
- **text-table**：返回逗号分隔文本表格，不是 JSON
- **empty-cn**：无数据时返回中文文案，不是空数组
- **json**：标准 JSON
- **text**：纯文本

> 这些行为官方文档均未说明，均为实测所得。
> 写操作工具（下单/取消/抽奖/兑换/领券）本脚本一律不调用，仅展示参数定义。