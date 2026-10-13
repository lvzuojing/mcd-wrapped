# WorkBuddy 开发上下文

本文件记录使用腾讯 WorkBuddy 开发 `mcd-wrapped` 项目的完整过程，
用于麦当劳 1024 程序员节创意开发大赛的 **WorkBuddy 专项奖励**核验。

- 项目仓库：https://github.com/lvzuojing/mcd-wrapped
- 报名 Issue：https://github.com/M-China/mcd-developer-innovation-challenge/issues/73
- 报名状态：官方账号已回复「您的作品已成功参赛」

---

## 一、选题阶段（WorkBuddy 全程参与）

用户给出大赛信息后明确要求：**先找合适的 Agent 和 Skill 分析，不要用裸大模型跑**。

WorkBuddy 执行：

| 动作 | 使用的能力 | 产出 |
|---|---|---|
| 加载官方 Skill 方法论 | `Skill: skill-creator` | Skill 目录规范、SKILL.md 写法、打包校验标准 |
| 搜索匹配专家 | `Skill: recommend-experts` | 评估专家库，结论：无黑客松/技术评审类专家 |
| 派子代理做赛事情报 | `Agent: general-purpose` | 扒取主办仓库规则、RANKING.md、全部报名 Issue、MCP Server tool 清单 |
| GitHub API 实测 | bash + curl | 确认组织名是 `M-China`（非 McDonalds-China） |
| 赛道可视化 | `show_widget` | 33 个 MCP 能力按拥挤度拆分的象限图 |

关键结论：**排名 100% 由 GitHub Star 数决定**，因此"传播属性"比"技术难度"更决定成败。
据此否决了已经拥挤的"省钱点餐助手"方向，选定「年度账单 + 方言语音播报」组合。

## 二、骨架搭建与必交文件

使用 `skill-creator` 的 `init_skill.py` 初始化目录，产出全部必交文件：

```
README.md                  项目介绍
CONTEST_DECLARATION.md     参赛声明（从官方仓库原样复制，未改动）
MCP_INTEGRATION.md         MCP 调用说明与业务价值
mcp-config.example.json    脱敏配置（仅环境变量占位符）
workbuddy.md               本文件
```

## 三、真实联调：发现并修复三个官方未说明的行为

拿到 Token 后执行 `scripts/collect.py`，7 个 tool 全部调通，但返回体与文档不符：

| # | 实际行为 | 官方说明 |
|---|---|---|
| 1 | 返回体是 **Markdown 文本**，真 JSON 藏在 `## Original Response` 段之后 | 说是 JSON |
| 2 | `list-nutrition-foods` 的 `data` 是**逗号分隔纯文本表格**（160 行） | 说是 JSON 数组 |
| 3 | 无数据时返回**中文文案**（如 `暂无可用优惠券`） | 说是空数组 |

新增 `parse_markdown_payload()` 与 `parse_nutrition_text()` 修复。
验证结果：积分账户解析正确，**餐品营养映射成功 158 项**。

> 这三项在大赛同期作品中属于普遍踩坑点，项目已将其写入 README 与 `MCP_INTEGRATION.md` 供其他参赛者参考。

## 四、方案转向

首个 Token 对应账户无历史订单（`order-list` 返回 `data:{}`，经查该 tool 入参定义为空，非调用问题）。
为避免编造数据违反"不得提交虚假参赛项目信息"，WorkBuddy 提出并实施转向：
**改用不依赖个人消费记录的 MCP 公共数据出报告**。

实测确认以下 tool 无需参数、不依赖消费记录即可返回真实数据：

| Tool | 真实数据 |
|---|---|
| `campaign-calendar` | 当月营销活动 30 场 |
| `list-nutrition-foods` | 餐品营养 158 项 |
| `query-lottery-info` | 抽奖奖池 10 种奖品 |
| `mall-points-products` | 积分商城商品 50 件 |
| `available-coupons` | 麦麦省可领券 6 张 |

## 五、个人年报链路打通

换用有消费记录的 Token 后，`collect.py` 成功解析出 **10 笔真实订单**。过程中修复三个字段映射 bug：

| bug | 现象 | 修法 |
|---|---|---|
| `realTotalAmount` 不在金额候选键里 | 消费总额恒为 0 | 候选键列表补上该字段 |
| 商品明细藏在 `comboItemList` 子项 | 高频单品为空 | 新增 `extract_line_items()` |
| 订单名与营养表名不一致 | 热量恒为 0 | 新增 `lookup_kcal()` 模糊匹配 |

修复后指标：**10 笔订单 / ¥200.7 / 5788 kcal / 可用积分 361.8 / 奖品 7 份**。

## 六、工具箱扩展

判定「同一账号多项目只取 Star 最高者」规则后，WorkBuddy 建议把能力集中到单一仓库，
新增两个模块：

**1. MCP 能力探测器 `scripts/explore.py`**
把服务端暴露的全部 **35 个** tool（文档写 33 个）跑一遍：

- 27 个只读接口实测调通，含**自动串联参数**
  （`order-list` 取 `storeCode` → `query-meals`；取 `orderId` → `query-order`；
  `mall-points-products` 取 `spuId` → `mall-product-detail`）
- 7 个写操作（`create-order` / `cancel-order` / `draw-lottery` / `auto-bind-coupons` /
  `mall-create-order` / `party-order-create` / `delivery-create-address`）**一律不调用**
- 修复"缓存未解析字符串导致取不到值"后，成功率从 13/35 提升到 **27/35**
- 顺带挖出：`query-party-city` 281 个城市、`query-meals` 15 个在售餐品、`query-promotions` 12 个促销

**2. 抽奖期望值精算器 `scripts/lottery_ev.py`**
基于真实奖池 + 真实消耗（24 积分/次）做蒙特卡洛模拟：

- 10 连抽消耗 240 积分，期望换回 **30.2 积分**，**净亏 209.8**
- 券面额按奖品名智能匹配基准价（麦旋风 ¥9、三件套 ¥40），避免一刀切高估
- 报告明确标注官方未公布概率、结果基于等概率假设
- 脚本**从不调用** `draw-lottery`

## 七、发布物料

WorkBuddy 产出可直接使用的传播物料：

- `SOCIAL_POSTS.md` — 三大渠道文案（V2EX/掘金、朋友圈、小红书），无引用符号可直接复制
- `PROMO.md` — 发布节奏 + 合规底线 + 官方渠道全集
- `assets/poster.svg` → `out/poster.png`（1360×860 横版海报）
- `assets/xiaohongshu.svg` → `out/xiaohongshu.png`（1080×1440 竖版）
- `out/preview.png`（年报长图 1520×3756）、`out/panorama.png`（全景长图 1600×10554）

所有物料均带仓库链接，确保浏览者可直达点星。

## 八、合规处理

- 能量数值只做中性换算参照，**不作健康评价**，避免触及"不得宣扬不健康饮食方式"条款
- 报告脚注改为「当前接入的麦当劳账户」，不谎称数据来源
- Token 仅通过环境变量传入，`.gitignore` 排除 `data/raw/`，未入库
- 明确规避买星、多账号等违规手段

---

## 使用过的 WorkBuddy 能力清单

| 能力 | 用途 |
|---|---|
| Agent 模式（文件编辑 / bash 执行） | 全流程开发 |
| `Skill: skill-creator` | Skill 目录规范与打包标准 |
| `Skill: recommend-experts` | 专家匹配评估 |
| `Agent: general-purpose` | 赛事情报深挖、并行调研 |
| `Agent: Explore` 类子任务 | 数据结构勘察 |
| `show_widget` | 赛道拥挤度图、多项目排名规则图、接口实测地图 |
| `present_files` | 产物交付与预览 |
| `TaskCreate / TaskUpdate` | 多步骤任务跟踪 |
| Playwright + Chromium | 报告长截图与海报渲染 |
| 本地 VoxCPM2 TTS + macOS `say` 回退 | 方言语音播报模块 |

## 技术要点总结

- **零第三方依赖**：全部脚本只用 Python 标准库
- **宽容字段解析**：候选键列表 + 递归遍历，兼容服务端字段变更
- **Markdown 返回体解析器**：抽取 `## Original Response` 后的 JSON
- **写操作红线**：7 个会产生真实后果的接口默认不调用
- **公共数据模式**：无消费记录也能出真实报告，解决新账号痛点
- **双模式渲染**：`build_panorama.py`（公共全景）/ `build_report.py`（个人年报）
- **视觉产物自动化**：Playwright 生成 2x 高清长截图，含文字溢出自动校验

## 验证命令

```bash
export MCD_MCP_TOKEN=你的token
python3 scripts/explore.py        # 35 个接口全量探测
python3 scripts/lottery_ev.py     # 抽奖期望值精算
python3 scripts/collect.py        # 个人数据采集
python3 scripts/build_report.py   # 个人年报
python3 scripts/public_data.py --offline   # 公共数据解析
python3 scripts/build_panorama.py # 全景报告
python3 scripts/speak.py --dry-run         # 方言播报
```

以上命令全部验证通过。

---

*本项目由腾讯 WorkBuddy 全程参与开发，从选题调研、代码编写、真实接口联调、
文档撰写到视觉物料生成均在其协助下完成。非麦当劳官方产品。*
