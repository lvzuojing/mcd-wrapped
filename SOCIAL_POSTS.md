# 可直接复制的发布文案

> 本文件无引用符号，选中即可复制。仓库链接统一为：
> https://github.com/lvzuojing/mcd-wrapped

---

## 渠道 2 · V2EX / 掘金

**标题：** 对接麦当劳 MCP 踩的 3 个坑，以及一个把 35 个接口全跑了一遍的探测器

**正文：**

这几天在玩麦当劳办的「1024 程序员节创意开发大赛」，要求基于麦当劳 MCP（https://mcp.mcd.cn）开发 Skill。

官方仓库是 `M-China/mcd-developer-innovation-challenge`，MCP 指南在 `M-China/mcd-mcp-server`。文档写了有哪些 tool、入参大概长什么样，但真实对接下来发现好几处没说清楚，记录一下。

### 坑 1：返回体不是 JSON

官方示例里 tool 返回都是 JSON，但实际返回的是 Markdown 文本：

```
## 字段说明
...

## Original Response
{"code":0,"data":{...}}
```

直接 `json.loads()` 会失败。必须先切到 `## Original Response` 后面的那段文本，再交给 JSON 解析。

### 坑 2：营养数据是纯文本表格

`list-nutrition-foods` 返回的 `data` 不是数组，是一个字符串，里面是按行排列的逗号分隔表格，大概 160 行：

```
{productName,nutritionDescription,energyKj,energyKcal,...}:
猪柳麦满分,null,1288,308,16,16,24,781,213
...
```

需要按行切、按逗号 split，再自己处理表头和转义。

### 坑 3：空数据返回中文文案

比如 `query-my-coupons`，没券的时候返回的是：

```
暂无可用优惠券
```

不是空数组，不是 `{"list":[]}`，也不是 `null`。按空数组处理会漏掉这种 case，解析器要兜底。

### 坑 4：订单金额字段名

订单接口的字段名也偏。金额字段叫 `realTotalAmount`，不是常见的 `totalAmount` / `payAmount`。而且有些订单这个值是 `"0"`（全额抵扣或兑换单），求和时得区分。

### 探测器：把 35 个接口全跑了一遍

干脆写了个探测器 `scripts/explore.py`，把所有 tool 调一遍，记录真实返回形态。几个数字：

- 服务端实际暴露 **35 个** tool，官方文档写的是 33 个
- **27 个**只读接口实测调通，自动串联参数（比如从 `order-list` 取 `storeCode` 喂给 `query-meals`）
- **7 个**写操作默认不调用：`create-order` / `cancel-order` / `draw-lottery` / `auto-bind-coupons` / `mall-create-order` / `party-order-create` / `delivery-create-address`
- **1 个**缺参数：`delivery-query-stores` 需要 `addressId`，拿不到

顺带挖出几个没人用的数据源：`query-party-city` 有 **281 个城市**，`query-meals` 有 **15 个在售餐品**，`query-promotions` 有 **12 个促销**。

### 抽奖 EV 精算

`query-lottery-info` 返回的真实奖池：10 种奖品，24 积分抽一次。用蒙特卡洛跑了一下：

- 10 连抽消耗 **240 积分**
- 期望换回 **30.2 积分**
- **净亏 209.8 积分**

结论：抽奖的价值全在券，不在积分。券用不掉就是打水漂。麦当劳没公布中奖概率，以上基于等概率假设模拟，脚本本身也从不动真抽奖。

### 数据全景报告

还把公共数据聚合成了一份单文件 HTML 报告：158 个餐品营养、当月营销日历、抽奖池、麦麦省可领券、积分商城。不需要消费记录也能出报告。

### 仓库

https://github.com/lvzuojing/mcd-wrapped

零第三方依赖，纯 Python 标准库。如果对麦当劳 MCP 有兴趣，可以直接跑 `scripts/explore.py`，所有真实返回都落盘在 `data/raw/` 里，拿去用就行。觉得有用的话点个 Star 就当给踩坑费了。

---

## 渠道 3 · 朋友圈

**配图：** `out/poster.png`（横版海报，推荐）或再加 `out/preview.png`（年报长图）

### 版本 B（反直觉钩子，推荐）

用麦当劳自己的接口数据算了下他们的积分抽奖：

10 连抽 = 240 积分
期望换回 = 30.2 积分
净亏 = 209.8 积分

结论：抽奖的价值在券不在积分，券用不掉就是亏。
（官方没公布中奖概率，这是等概率假设下的模拟，脚本也从不真的抽奖）

顺手做了个项目：把麦当劳 MCP 的 35 个接口全跑了一遍，27 个调通，7 个会真下单/扣积分的一律不碰。还用它生成了年度报告和一份数据全景。

麦当劳 1024 程序员节创意开发大赛参赛作品，排名看 Star 数，觉得有意思帮我点个 Star：
https://github.com/lvzuojing/mcd-wrapped

### 版本 C（产品向钩子）

用麦当劳官方数据做了个 MCP 工具箱：158 个餐品营养档案、当月营销日历、积分抽奖池、麦麦省可领券、积分商城——一次看透。

还能用它生成年度消费年报，以及用粤语/方言把报告念出来。

数据全部来自真实接口，不是编的。麦当劳 1024 程序员节创意开发大赛参赛作品，帮我点个 Star：
https://github.com/lvzuojing/mcd-wrapped

### 评论区单独发一条（朋友圈正文的链接不一定可点）

https://github.com/lvzuojing/mcd-wrapped

> 说明：朋友圈正文里的网址在部分版本不可点击，评论区再补一条纯链接更稳妥。

---

## 渠道 4 · 小红书 / 微博

**配图：** `out/xiaohongshu.png`（竖版 3:4，图片底部已印有仓库地址）

**正文：**

麦当劳积分抽奖，240 积分换回 30.2 积分

用麦当劳自己的接口数据算了一下：

10 连抽 = 240 积分
期望换回 = 30.2 积分
净亏 = 209.8 积分

结论：抽奖的价值在券不在积分，券用不掉就是亏。

（官方没公布中奖概率，等概率假设下的模拟结果，脚本从不真抽奖）

完整项目在图片底部，也可以看评论区 👇

#麦当劳 #程序员节 #数据分析 #开源 #MCP

### 评论区第一条（小红书正文外链会被限流，放评论区）

https://github.com/lvzuojing/mcd-wrapped

> 说明：小红书正文放外链容易被限流，因此链接放在图片底部 + 评论区两处。

---

## 配图清单

| 文件 | 尺寸 | 用途 |
|---|---|---|
| `out/poster.png` | 1360×860 横版 | 朋友圈 / 开发者社群 |
| `out/xiaohongshu.png` | 1080×1440 竖版 3:4 | 小红书 / 微博 |
| `out/preview.png` | 年报长图 | 朋友圈补充图 |

三张图底部均已印有仓库地址，即使文案里的链接失效也能找到。
