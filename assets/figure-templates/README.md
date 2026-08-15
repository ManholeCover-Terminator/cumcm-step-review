# 科研绘图模板库

来自 `mathmodel-figure-templates`（已内置，自包含），提供 11 个可直接运行的科研绘图模板。

## 用法

```bash
python assets/figure-templates/scripts/render_template.py --list
python assets/figure-templates/scripts/render_template.py paired-raincloud --project <输出目录>
```

渲染器会把模板脚本复制到 `<输出目录>/scripts/` 并在其中运行，输出到 `<输出目录>/outputs/`（PNG/PDF/SVG）。

## 模板清单

`multiclass-shap-combo`、`paired-raincloud`、`cv-roc-ci`、`taylor-diagram`、`correlation-pairgrid`、`prediction-marginal-grid`、`rf-tpe-surface`、`grouped-corr-split-violin`、`grouped-circular-heatmap`、`urban-park-cooling-combo`、`nature-chord-diagram`

说明见 `references/figure-catalog.md`，配方见 `references/plot-recipes.md`。

> 预览图（约 10 MB）未内置；需要时从 `mathmodel-figure-templates/assets/previews/` 复制。
