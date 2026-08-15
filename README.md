# cumcm-step-review ｜ 数学建模国赛 · 逐步审核版

面向全国大学生数学建模竞赛（CUMCM）的完整建模论文分步审核工作流技能，兼容 Codex、Claude Code 等支持 [Agent Skills](https://agentskills.io) 规范的 Agent。

本仓库**本身就是技能**：`SKILL.md` 位于仓库根目录，克隆或复制整个文件夹到 Agent 的 skills 目录即可使用，无需额外安装步骤。

## 主要特性

- **十部分分步审核**：问题重述 → 数据预处理 → 逐问建模与求解 → 模型分析与检验 → 模型评价与推广 → 参考文献 → 附录 → 问题分析 → 模型假设 → 符号说明 → 摘要（两阶段闭环）。每部分先给出分析与候选方案，经审核通过后再写代码，并把该部分写入 Word 论文草稿再次供用户审核，全部冻结后生成最终论文。
- **国赛优秀论文写法**：内置 `references/优秀论文写法指南.md`、`优秀论文语料分析报告.md`，以及基于 **93 篇国赛优秀摘要语料**提炼的摘要写作方法论（起草 → 二次验证 → 定稿）。
- **数据图规范（硬性）**：图内无标题、图题在图下、图后必跟分析、同类型图 ≤3 张、字号按最终印刷尺寸（正文 8.5–11pt，最小 ≥7.5pt）、默认只输出一个 300 DPI PNG；期刊配色 7 套（nature / science / cell / ieee / general / okabe-ito / wong）。
- **非数据图**：内置 **drawio-skill v2.1.0**（`tools/drawio/`），技术路线图、子问题求解流程图、数据处理流程图、模型结构图等自动生成并导出 PDF/PNG。
- **工具链全部内置、离线自包含**：DOCX / LaTeX / PDF / Excel / 论文搜索（OpenAlex + AnySearch）。
- **最终验收**：文本门禁、真实编译、页面规格、图表编号、引用双向核验等。

## 目录结构

```text
SKILL.md                   技能入口（Agent 据此识别）
references/                国赛写法指南、语料分析、阶段流程、绘图参考、摘要写作方法论
scripts/                   绘图风格、图表审计、论文门禁、复现清单等脚本
tools/                     drawio / docx / latex / pdf / xlsx / paper_search 工具链
assets/                    算法说明库、期刊配色、论文模板
agents/                    Subagent 调度配置
manifest.sha256.json       文件清单与版本（v1.6）
```

## 安装

### Windows

```powershell
git clone https://github.com/<你的用户名>/cumcm-step-review.git "$env:USERPROFILE\.codex\skills\cumcm-step-review"
```

或直接把整个文件夹复制到 `C:\Users\<你的用户名>\.codex\skills\` 下。

### macOS / Linux

```bash
git clone https://github.com/<你的用户名>/cumcm-step-review.git ~/.codex/skills/cumcm-step-review
```

安装后重启 Agent 即可在技能列表看到 `cumcm-step-review`。

## 使用

对 Agent 说"用 cumcm-step-review 做这道国赛题"，或直接给出赛题与附件，按提示逐部分推进。论文结构与格式以目标赛题当届官方规则和官方模板为准。

## 许可证与致谢

- 本技能主体：MIT License（见 [LICENSE](LICENSE)）。

## 学习与来源声明

本技能在开发过程中**学习并融合了以下既有技能与公开资料**，谨此声明并致谢；完整明细与落位见 [CREDITS.md](CREDITS.md)。

| 来源 | 融入内容 | 说明 |
| --- | --- | --- |
| math-modeling | 基础建模流程、建模手/编程手/论文手分工、工具链与算法库骨架 | 作者自建技能 |
| math-modeling-review | 分步审核工作流与“分析→审核→代码→写稿→再审→冻结”协议 | 作者自建技能 |
| math-contest-assistant | 论文各部分的组织与写作经验 | 作者自建技能 |
| math-modeling-paper-review | 论文审阅与写法经验 | 作者自建技能 |
| cumcm-abstract-writing-skill | 摘要写作方法论与摘要语料分析（`references/摘要写作/`） | 开源技能（GitHub: jjh666888/cumcm-abstract-writing-skill） |
| drawio-skill v2.1.0 | `tools/drawio/` 非数据图工具链 | MIT，Agents365-ai |
| scipilot-figure-skill | `references/绘图参考/` 科研绘图知识库 | MIT，Haojae |
| mathmodel-figure-templates | `assets/figure-templates/` 科研绘图模板 | 内置自包含 |
| 历届国赛优秀论文（公开资料） | 93 篇优秀摘要语料、写作指南、语料分析报告 | 公开资料，仅供学习研究 |
