# M-CODE WRAPPED

**麦当劳 MCP 工具箱：从调试接口到出报告，一条龙。**

基于 [麦当劳 MCP](https://github.com/M-China/mcd-mcp-server) 开放能力，四个模块覆盖开发者到消费者的完整链路：

| 模块 | 一句话 | 入口 |
|---|---|---|
| **MCP 能力探测器** | 一键探测全部 35 个 tool 的真实返回，自动串联参数 | `scripts/explore.py` |
| **个人年度消费年报** | 订单、消费、积分、奖品、高频单品，一页看完 | `scripts/collect.py` |
| **麦当劳数据全景报告** | 158 个餐品营养、营销日历、抽奖池、商城、优惠券 | `scripts/public_data.py` |
| **抽奖 EV 精算器** | 蒙特卡洛模拟，算清抽奖到底值不值 | `scripts/lottery_ev.py` |

并可选粤语/方言语音播报，把报告念出来。

> 麦当劳 1024 程序员节创意开发大赛参赛作品 · 非麦当劳官方产品

## 如果你正在对接麦当劳 MCP，先看这个

官方文档不太全，实测踩了 3 个坑，都在[探测器报告](out/mcp-explorer.md)里：

1. 返回体**不是 JSON**，是 Markdown，真 JSON 藏在 `## Original Response` 之后
2. `list-nutrition-foods` 的 data 是**逗号分隔文本表格**，不是 JSON
3. 无数据时返回**中文文案**（如 `暂无可用优惠券`），不是空数组

服务端实际暴露 **35 个** tool（文档写的是 33 个），探测器已跑通 **27 个**，
7 个写操作默认不调用。不想看报告也行，直接跑：

```bash
export MCD_MCP_TOKEN=你的token
python3 scripts/explore.py     # 零第三方依赖，输出 out/mcp-explorer.md
```

![个人年报预览](out/preview.png)

> 上图由真实 MCP 数据生成。样张来自授权测试账户，接入你自己的 Token 后会替换为你的真实数据。

## 为什么不是"又一个点餐助手"

大赛里绝大多数作品在做同一件事：怎么更便宜地下单。这个项目换个方向——
**先帮开发者搞清楚 MCP 到底返回了什么，再把数据做成值得点星的报告。**

| | 点餐助手 | M-CODE WRAPPED |
|---|---|---|
| 视角 | 省钱、下单 | 调试 + 数据可视化 + 决策 |
| 是否需要消费记录 | 需要 | 公共全景不需要，个人年报需要 |
| 产物 | 一个订单 | 探测报告 + 年报 + 全景 + 精算 |
| 对开发者友好度 | 一般 | **探测器专门解决这个痛点** |

## 模块一：MCP 能力探测器

官方文档列了 tool 名字，但没说清楚实际返回什么。实测下来坑不少：

- 返回的是 **Markdown 文本**，真 JSON 藏在 `## Original Response` 之后
- 营养数据是**逗号分隔文本表格**，不是 JSON
- 无数据时返回**中文文案**（如 `暂无可用优惠券`），不是空数组

探测器一键跑完所有只读工具，记录真实形态：

```bash
export MCD_MCP_TOKEN=你的token
python3 scripts/explore.py
```

**自动串联参数**：从 `order-list` 取 `storeCode` 喂给 `query-meals`，取 `orderId` 喂给 `query-order`，
取 `spuId` 喂给 `mall-product-detail`——需要参数的工具也能跑起来。

本次实测：**35 个 tool，27 个成功调用，7 个写操作跳过，1 个缺参数**。
完整报告见 [out/mcp-explorer.md](out/mcp-explorer.md)。

**安全红线**：`draw-lottery`、`create-order`、`cancel-order`、`mall-create-order`、
`auto-bind-coupons`、`party-order-create`、`delivery-create-address` 一律**不调用**，
只在报告里展示参数定义。

## 模块二：个人年度消费年报

```bash
export MCD_MCP_TOKEN=你的token
python3 scripts/collect.py
python3 scripts/build_report.py       # -> out/mcd-wrapped.html
```

包含：年度下单数、消费总额、客单价、深夜订单占比、最常去门店、连续打卡、
高频单品 Top 6、月度趋势、周几偏好、下单高峰、累计能量、可用积分、奖品数。

## 模块三：麦当劳数据全景报告

```bash
python3 scripts/public_data.py
python3 scripts/build_panorama.py     # -> out/panorama.html
```

不需要消费记录，只用公共数据：158 个餐品营养档案、热量 TOP10 / 低卡 TOP10 / 分布直方图、
当月营销日历、积分抽奖池、麦麦省可领券、积分商城商品。

## 模块四：抽奖 EV 精算器

```bash
python3 scripts/lottery_ev.py                    # 默认 10 连抽 × 10000 轮
python3 scripts/lottery_ev.py --draws 50 --trials 50000
python3 scripts/lottery_ev.py --base-price 45    # 调整折扣券基准价
```

真实奖池 + 真实单次消耗（24 积分），蒙特卡洛模拟。
券面额按奖品名智能匹配基准价（麦旋风按 ¥9、三件套按 ¥40）。

> 麦当劳**未公布**中奖概率，所有结果基于等概率假设，脚本从不调用 `draw-lottery`。
> 完整报告见 [out/lottery-ev.md](out/lottery-ev.md)。

## 方言播报

```bash
python3 scripts/speak.py --dialect cantonese    # 粤语
python3 scripts/speak.py --dialect taiwanese    # 闽南语调
python3 scripts/speak.py --dialect mandarin     # 普通话
python3 scripts/speak.py --dry-run              # 只看播报稿
```

后端按 **VoxCPM2 → macOS 内置中文嗓音** 自动回退：

```bash
export VOXCPM_API_URL=http://127.0.0.1:7860     # 本地 VoxCPM2 Gradio 服务
export VOXCPM_REF_AUDIO=/path/to/四川话参考音频.wav
python3 scripts/speak.py --dialect voxcpm
```

## 目录结构

```
mcd-wrapped/
├── SKILL.md                      Skill 定义，供 Agent 驱动全流程
├── MCP_INTEGRATION.md            使用的 MCP tool、调用流程与踩坑记录
├── CONTEST_DECLARATION.md        参赛声明（官方原文，未修改）
├── workbuddy.md                  使用 WorkBuddy 开发时的上下文
├── mcp-config.example.json       脱敏配置，仅环境变量占位符
├── scripts/
│   ├── mcp_client.py             MCP Streamable HTTP 客户端
│   ├── explore.py                ★ 35 个 tool 能力探测器
│   ├── collect.py                个人数据采集 + 字段归一化
│   ├── build_report.py           个人年报渲染
│   ├── public_data.py            公共数据采集与解析
│   ├── build_panorama.py         全景报告渲染
│   ├── lottery_ev.py             ★ 抽奖期望值精算
│   ├── demo_data.py              演示数据（dry-run）
│   └── speak.py                  方言语音播报
├── references/
│   ├── mcp_tools.md              tool 清单与字段归一化说明
│   └── compliance.md             输出内容合规红线
├── assets/
│   ├── panorama_template.html    全景报告模板
│   └── report_template.html      个人年报模板
└── out/
    ├── mcd-wrapped.html          个人年报
    ├── panorama.html             全景报告
    ├── mcp-explorer.md           能力探测报告
    ├── lottery-ev.md             抽奖精算报告
    └── preview.png               README 预览图
```

## 合规说明

- 项目**只读**官方数据，不创建、不取消、不支付任何订单
- 写操作工具（`draw-lottery` / `create-order` / `mall-create-order` 等）**从不调用**
- 配置文件仅使用环境变量占位符，不含任何凭证
- 能量数值按公开营养信息估算，仅供参考，不构成健康或营养建议
- 抽奖期望值官方未公布概率，按等概率假设做披露性说明，不构成参与建议
- 报告只陈述事实，不做健康评价
- 完整红线见 `references/compliance.md`

## License

MIT
