# 非数据图（技术路线图/流程图）绘制规范 —— drawio 接入说明

本技能内置 `tools/drawio/`（drawio-skill v2.1.0，MIT 许可）。凡论文需要**技术路线图、子问题求解流程图、数据处理流程图、模型结构图、指标体系图、模型选择决策树**等非数据图，统一走这条工具链，不再手写零散的 `.drawio` XML。

## 何时用 / 何时不用

**用 drawio：**

| 图 | 论文落位 | 说明 |
| --- | --- | --- |
| 技术路线图 `fig_roadmap` | 第 8 部分 问题分析 | 题目 → 数据 → 逐问模型 → 检验 → 展示；图后紧跟分析 |
| 数据处理流程图 `fig_pipeline` | 第 2 部分 数据预处理 | 清洗 → 特征构造 → 划分；图后紧跟分析 |
| 每问求解流程图 `fig_flow_qN` | 第 3 部分 该问"模型的求解" | 输入 → 算法 → 判断 → 输出；图后紧跟分析 |
| 模型结构图 / 变量关系图 `fig_model` | 第 3 部分 模型建立 | 模块、变量、层次关系；按需 |
| 指标体系图 / 决策树 | 视题目 | 目标层-准则层-指标层、规则分支；按需 |

**不用 drawio：** 数据图（折线/柱状/散点/热力/箱线等）仍走 `scripts/plot_style.py` + `references/绘图参考/chart_knowledge_base.md`；需要公式节点、精确数学连线或 2D 几何的概念图优先 TikZ；节点极多且由数据驱动布局的网络图用 Matplotlib/networkx。

## 执行前必读（渐进式加载）

1. 本文件（国赛规则与落位）
2. `tools/drawio/SKILL.md`（完整工作流：依赖检查 → 规划 → 生成 → 导出 → 自检 → 审核循环 → 定稿）
3. 按图类型读 `tools/drawio/references/diagram-types.md`（流程图/ML/架构等预设）
4. 手写 XML 前读 `tools/drawio/references/xml-authoring.md`（文件骨架、形状/边写法、配色、网格）
5. 需要样式预设时读 `tools/drawio/references/style-presets.md`，内置预设见 `tools/drawio/styles/built-in/`
6. 导出失败或视觉自检不通过时读 `tools/drawio/references/troubleshooting.md`

## 本机工具

- draw.io CLI：`%LOCALAPPDATA%\Programs\draw.io\draw.io.exe`（示例路径，每台机器可能不同；或 PATH 中的 `drawio`；用前先 `--version` 确认可用二进制名并全程复用）
- Python 脚本：`tools/drawio/scripts/*.py`（shapesearch / validate / autolayout / edgeports / repair_png / encode_drawio_url 等）
- 自动布局（可选）：需要 Graphviz `dot`；没有时用 CLI `--layout`（ELK，draw.io ≥ v30）或手排坐标

## 硬性规则（用户定制，覆盖 drawio-skill 默认）

1. **图内无标题**：图上方、图下方都不写标题，也不画面板编号/页码，只保留节点文字、箭头和必要图例；标题信息一律放图注/图表契约。
2. **图题在图下**：正文"先引导 → 插图 → 紧随其后的分析"，图后必须有分析段（趋势、关键结构、结论含义），连续两张图之间没有文字判为硬错误。
3. **同类型 ≤3 张**：技术路线图全篇 1 张；每问求解流程图至多 1 张；同类型非数据图全篇不超过 3 张且不连续出现，避免审美疲劳。
4. **配色**：默认 `colorblind-safe` 预设（Okabe-Ito 色盲安全色板，与正文数据图 `journal="okabe-ito"` 一致）；也可用 `corporate`（期刊感）或用户指定；禁止彩虹色、装饰性阴影和过度渐变。图中文字颜色与底色对比要够。
5. **字号**：按最终印刷尺寸设定。draw.io 像素与印刷 pt 按 96 DPI 换算（12px ≈ 9pt）。节点正文 12–14px（≈9–10.5pt），最小 10px（≈7.5pt）；禁止整图默认 16px 一缩到底，也禁止 8px 以下看不清的小字。
6. **布局**：不用固定 2×2；按流程方向选择纵向（TB，技术路线/步骤）或横向（LR，时间线/层次）；对齐 10px 网格；同层节点等高；箭头方向清晰、不交叉、不穿无关节点；节点文字短、必要时双行。
7. **导出**：论文嵌入用 PDF（矢量）或 300 DPI PNG；`-e` 只用于最终交付（保持可编辑），预览自检图不带 `-e`；带 `-e` 的 PNG 导出后必须跑 `tools/drawio/scripts/repair_png.py`（修复 draw.io IEND 截断）；文件名单一、不带 v1/v2 版本号。
8. **落位**：所有 `.drawio` 与导出图放 `PROJECT_ROOT/figures/`，命名与正文引用一致（`fig_roadmap`、`fig_flow_q1` 等）；生成后在 `results/` 或工作记录里登记图清单与用途。

## 工作流（精简版）

1. 读 `tools/drawio/SKILL.md`；先定图的论证目的、节点清单与层次（≤15 节点优先手排坐标，大图用 `tools/drawio/scripts/autolayout.py`）。
2. 生成 `.drawio`（手写 XML 前先读 `tools/drawio/references/xml-authoring.md`；需要精确形状时用 `tools/drawio/scripts/shapesearch.py` 查官方 style，不靠猜）。
3. 结构检查：`python tools/drawio/scripts/validate.py <name>.drawio`。
4. 预览导出（不带 `-e`）：`drawio -x -f png --width 2000 -o <name>.png <name>.drawio`。
5. 视觉自检（最多 2 轮）：重叠、文字裁切、箭头断连、越界、线穿节点、标签遮挡；每修一次重新导出再看。
6. 用户审核（最多 5 轮定向修改）：单元素改动直接改 XML；整体换方向/重排才重新生成；修改后覆盖同一文件名，不生成 v1/v2。
7. 定稿导出：PDF +（如需）带 `-e` 的 PNG → 跑 `tools/drawio/scripts/repair_png.py`；报告 `.drawio` 与导出图路径。
8. 图后写分析段，再写入论文草稿。

## 浏览器降级（CLI 不可用时）

CLI 崩溃、无输出或 Electron 沙箱失败时（例如本会话沙箱内），不要反复重试；用 `python tools/drawio/scripts/encode_drawio_url.py <name>.drawio` 生成 diagrams.net 预览链接交给用户确认，或交付 `.drawio` 源码，导出命令留给用户在宿主环境执行。

## 常见错误（自检清单）

- 图内写了标题或面板编号 → 删掉，信息移入图注
- 图后没有分析段 → 补"结构/趋势 + 关键节点 + 结论含义"
- 同类型图超过 3 张或连续堆图 → 合并、删减或换图型
- 节点文字过小（<10px）或过长 → 放大字号 / 拆短句
- 箭头无标签、意义不明 → 补动词短语（"输入""判断""输出"）
- 彩虹色/装饰渐变 → 换回 `colorblind-safe` 或 `corporate`
