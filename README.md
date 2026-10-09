# M-CODE WRAPPED

**麦当劳数据全景报告。**

基于 [麦当劳 MCP](https://github.com/M-China/mcd-mcp-server) 开放能力，把散落在多个官方接口里的公共数据聚合成一份可截图、可转发的全景报告：
158 个餐品营养档案、当月营销活动日历、积分抽奖池、麦麦省可领券、积分商城商品——一次看透 MNCP 到底能拿到什么。

也支持接入你自己的 Token，生成**个人年度消费年报**，并配上粤语/方言语音播报。

> 麦当劳 1024 程序员节创意开发大赛参赛作品 · 非麦当劳官方产品

![报告预览](out/preview.png)

> 上图由真实 MCP 公共数据实时生成。标有 `100% 真实数据 · MNCP` 徽章，所有数字可复现。

## 为什么不是"又一个点餐助手"

大赛里绝大多数作品在做同一件事：怎么更便宜地下单。这个项目换个方向——
**把 MCP 能拿到的数据摊开来，做成一份值得点星的数据报告。**

| | 点餐助手 | M-CODE WRAPPED |
|---|---|---|
| 视角 | 省钱、下单 | 数据可视化、全景 |
| 是否需要消费记录 | 需要 | **不需要，公共数据即可出报告** |
| 产物 | 一个订单 | 一份可转发的 HTML 报告 + 方言语音 |
| 独特性 | 红海撞车 | 几乎没人做 |

## 快速开始

### 方式 A：公共全景报告（不需要消费记录）

```bash
export MCD_MCP_TOKEN=你的token
git clone https://github.com/lvzuojing/mcd-wrapped.git
cd mcd-wrapped
python3 scripts/public_data.py        # 采集麦当劳公共数据
python3 scripts/build_panorama.py       # -> out/mcd-wrapped.html
```

### 方式 B：个人年度消费年报

```bash
export MCD_MCP_TOKEN=你的token
python3 scripts/collect.py            # 采集本人订单/积分/券/商城
python3 scripts/build_report.py       # -> out/mcd-wrapped.html
```

> 所有 Token 只通过环境变量传入，不会写进任何会被 git 跟踪的文件。

### 没有 Token 也能看样张

```bash
python3 scripts/demo_data.py          # 生成确定性演示数据
python3 scripts/build_report.py       # 个人年报样张
```

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

## 报告里有什么

公共全景模式：

- 158 个餐品的营养数据库
- 热量 TOP10 / 低卡 TOP10 / 热量分布直方图
- 当月营销活动日历（含标题、摘要、图片）
- 积分抽奖池：单次消耗、奖品清单、概率说明
- 麦麦省当前可领券
- 麦麦积分商城：商品、类目、积分/现金价

个人年报模式：

- 年度下单总数、消费总额、客单价
- 深夜订单占比、最常去门店、连续打卡纪录
- 高频单品 Top 6、月度趋势、周几偏好
- 可用积分与即将过期积分
- 已领奖、优惠券、商城订单

## 目录结构

```
mcd-wrapped/
├── SKILL.md                      Skill 定义，供 Agent 驱动全流程
├── MCP_INTEGRATION.md            使用的 MCP tool、调用流程与踩坑记录
├── CONTEST_DECLARATION.md        参赛声明（官方原文，未修改）
├── workbuddy.md                  使用 WorkBuddy 参赛的补充说明
├── mcp-config.example.json       脱敏配置，仅环境变量占位符
├── scripts/
│   ├── mcp_client.py             MCP Streamable HTTP 客户端
│   ├── public_data.py            公共数据采集与解析
│   ├── build_panorama.py         全景报告渲染
│   ├── collect.py                个人数据采集 + 字段归一化
│   ├── demo_data.py              演示数据（dry-run）
│   ├── build_report.py           个人年报渲染
│   └── speak.py                  方言语音播报
├── references/
│   ├── mcp_tools.md              tool 清单与字段归一化说明
│   └── compliance.md             输出内容合规红线
├── assets/
│   ├── panorama_template.html    全景报告模板
│   └── report_template.html      个人年报模板
└── out/
    ├── mcd-wrapped.html          最新报告
    └── preview.png               README 预览图
```

## 合规说明

- 项目**只读**官方数据，不创建、不取消、不支付任何订单
- 配置文件仅使用环境变量占位符，不含任何凭证
- `draw-lottery` 会真实消耗积分，默认流程不调用
- 能量数值按公开营养信息估算，仅供参考，不构成健康或营养建议
- 抽奖期望值官方未公布概率，本页按等概率假设做披露性说明，不构成参与建议
- 完整红线见 `references/compliance.md`

## License

MIT
