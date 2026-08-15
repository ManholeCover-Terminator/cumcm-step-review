# 绘图参考（scipilot 资料库 + 用户图表知识库）

本目录文档吸收自 `scipilot-figure-skill`（MIT License, Copyright (c) 2026 Haojae），
作为绘图知识参考：图表选择、避坑、期刊规格、绘图配方、投稿清单、视觉复核、数据剖析解读。
另含用户新增的 `chart_knowledge_base.md`（60+ 图表速查：图级评级、数据类型要求、适用条件、避坑）。
它们描述的是**通用科研绘图原理**；其中出现的 scipilot 旧脚本名与本技能脚本的映射如下，
执行时一律使用本技能 `scripts/` 下的真实工具：

| scipilot 旧写法 | 本技能等价物 |
| --- | --- |
| `setup_style()` | `scripts/plot_style.py :: apply_publication_style(journal=..., lang=..., width=...)` |
| `visual_qa.audit_layout(fig)` | `plot_style.audit_layout(fig)`（含 <7.5pt 检查） |
| `layout_tools.finalize_figure(fig)` / `add_panel_labels(...)` | `plot_style.finalize_figure(fig)` / `plot_style.add_panel_labels(...)`（保留但默认不使用） |
| `export_figure(...)` | `plot_style.export_figure(...)`（默认只输出一个 300 DPI PNG） |
| `scripts/check_figure.py --strict` | `scripts/figure_audit.py <figures> --questions q1 q2 ... --strict` |
| `scripts/profile_data.py` | `scripts/profile_data.py` |

> 注意：本技能按用户定制，"图内不写标题、不画面板编号"，字号按最终印刷尺寸
> （正文标签 8.5–11pt、最小 ≥7.5pt）；同一类型图全篇不超过 3 张、同类图不连续
> 出现 3 张以上（避免审美疲劳）；文档示例中若出现 `title(...)` 或大字号
> （10.5–13 pt）写法，以本技能规范为准。

## 非数据图（技术路线图/流程图）

技术路线图、子问题求解流程图、数据处理流程图、模型结构图等非数据图，统一使用本技能内置的
`tools/drawio/`（drawio-skill v2.1.0），硬性规则与论文落位见 `drawio_flowchart.md`；
执行前先读 `tools/drawio/SKILL.md` 的完整工作流。
