# WorkBuddy 开发上下文

本文件记录使用腾讯 WorkBuddy 开发 `mcd-wrapped` 项目的过程，
用于麦当劳程序员节创意开发大赛的 WorkBuddy 专项奖励核验。

## 开发目标

基于麦当劳 MCP 能力，开发一个实用且有创意的 Skill：
**把麦当劳 MCP 的公共数据聚合成一份可分享的全景报告，并支持个人年度消费年报 + 方言语音播报。**

## 关键决策与执行过程

### 1. 选题决策

用户给出麦当劳大赛信息后，首先指示"先找到合适的 Agent 和 Skill 来分析，不要直接用裸大模型跑"。

执行动作：
- 加载 `skill-creator`（WorkBuddy 官方 Skill 开发方法论）
- 加载 `recommend-experts` 搜索匹配专家
- 派 general-purpose 子代理做深度赛情调研
- 通过 GitHub API 实测官方仓库 `M-China/mcd-developer-innovation-challenge` 与 MCP Server 仓库

调研结论：
- 比赛排名 100% 由 GitHub Star 数决定
- 现有 4 个真实项目中 3 个是"省钱优化器"，赛道拥挤
- 派对、积分抽奖、麦麦商城、活动日历、餐品营养等方向完全空白
- 前 100 名门槛目前接近 0 star

推荐方案：① 年度账单（可晒）+ ④ 方言语音播报（用户已有 VoxCPM2 TTS + 570 个方言音频资产，壁垒最强），合成一个项目。

### 2. 真实 MCP 联调与关键转向

拿到 Token 后执行 `scripts/collect.py`，7 个 tool 全部调用成功，但发现：

1. **返回体是 Markdown 而非 JSON**，真正的 JSON 在 `## Original Response` 段落之后
2. **`list-nutrition-foods` 的 `data` 是纯文本表格**（160 行逗号分隔），不是 JSON
3. **无数据时部分 tool 返回中文文本**（如 `暂无可用优惠券`），而非空数组

修复方式：新增 `parse_markdown_payload()` 抽取 Markdown 中的 JSON，
新增 `parse_nutrition_text()` 解析文本表格，并补充真实字段名到候选键列表。

修复后验证结果：积分账户解析正确，餐品营养映射成功 158 项。

进一步发现用户账号没有历史订单。这意味着"年度消费账单"无法直接输出。
用户确认"从没吃过麦当劳"，因此切换为更稳妥且差异化的方案：
**基于 MCP 公共数据做"麦当劳数据全景报告"**，同时保留个人年报模式作为可选扩展。

### 3. 项目骨架与文件

使用 `skill-creator` 的 `init_skill.py` 初始化 `mcd-wrapped` Skill 目录。

核心文件：
- `SKILL.md`：触发条件、双模式工作流
- `scripts/mcp_client.py`：Streamable HTTP 客户端
- `scripts/public_data.py`：公共数据采集与解析
- `scripts/build_panorama.py`：全景报告渲染
- `scripts/collect.py`：个人数据采集与字段归一化
- `scripts/demo_data.py`：确定性演示数据
- `scripts/build_report.py`：个人年报渲染
- `scripts/speak.py`：VoxCPM2 → macOS 内置嗓音的方言播报
- `assets/panorama_template.html`：全景报告模板
- `assets/report_template.html`：个人年报模板
- `README.md` / `MCP_INTEGRATION.md` / `mcp-config.example.json`
- `CONTEST_DECLARATION.md`（从官方仓库原样复制，未改动）
- `references/mcp_tools.md` / `references/compliance.md`
- `.gitignore` 排除真实账户数据

### 4. 技术要点

- **零依赖**：脚本只使用 Python 标准库，不引入 requests 等第三方包
- **宽容字段解析**：麦当劳 MCP 字段名以服务端为准，用候选键列表 + 递归遍历做归一化
- **Markdown 解析器**：实测 MCP 返回 Markdown 文本，需先抽取 `## Original Response` 后的 JSON
- **公共数据模式**：不需要消费记录即可出真实数据报告，解决了新账号/小号无订单的痛点
- **双模式**：`build_panorama.py` 用于公共全景，`build_report.py` 用于个人年报
- **合规口径**：报告只陈述事实，不做健康评价；能量数值标注为参考值
- **自动回退**：方言播报优先 VoxCPM2，未启动时自动回退 macOS `say`
- **视觉产物**：用 Playwright + Chromium 生成长截图 `out/preview.png`

### 5. 验证

```bash
python3 scripts/public_data.py --offline
python3 scripts/build_panorama.py
python3 scripts/demo_data.py
python3 scripts/build_report.py
python3 scripts/speak.py --dry-run
```

全部通过，报告无残留占位符，预览图成功生成。

## 使用过的 WorkBuddy 能力

- Agent 模式（文件编辑、bash 执行）
- `Skill` 工具加载官方 Skill
- `Agent` 工具派生子代理做深度调研
- `show_widget` 展示赛道拥挤度可视化
- `present_files` 展示最终产物

## 仓库与报名

- GitHub Public 仓库：`https://github.com/lvzuojing/mcd-wrapped`
- 报名 Issue：已在 `M-China/mcd-developer-innovation-challenge` 提交
