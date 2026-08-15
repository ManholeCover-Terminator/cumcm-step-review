# 工具链（已内置，自包含）

本目录已从 `math-modeling/tools/` 完整内置，本 Skill 不依赖外部路径：

```text
tools/
  pdf/          SKILL.md + scripts     # 题目 PDF 读取、表单、转图
  xlsx/         SKILL.md + scripts     # Excel 读取/重算
  docx/         SKILL.md + scripts     # Word 草稿/论文构建、OMML、修订、校验
  latex/        SKILL.md + scripts     # LaTeX 论文生成、编译、校验、模板
  paper_search/ SKILL.md + scripts     # 双引擎论文搜索（OpenAlex + AnySearch）
  drawio/       SKILL.md + scripts     # drawio-skill v2.1.0：技术路线图/流程图等非数据图（规则见 references/绘图参考/drawio_flowchart.md）
```

## 使用规则

1. 使用任一工具前，实际读取对应 `SKILL.md`；知道路径不等于已经执行。
2. 优先调用工具的脚本和模板，禁止为了省时手写替代实现。
3. 环境缺少某工具或依赖时，报告阻塞并继续完成仍可验证的部分；不静默跳过验证。
4. 需要升级工具时，可将 `math-modeling/tools/` 的新版本复制覆盖本目录，保持自包含。

## 与 scripts/ 的分工

- 通用数值/图表脚本（数据剖析、绘图风格、图表审计、复现清单、论文门禁）在本 Skill 的 `scripts/` 下。
- 格式专用工具（PDF/Excel/Word/LaTeX/论文搜索/drawio）在 `tools/` 下，与 `math-modeling` 保持一致。
