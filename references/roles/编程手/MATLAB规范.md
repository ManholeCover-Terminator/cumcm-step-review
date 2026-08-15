# MATLAB 实现规范

MATLAB 与 Python 是同等支持的实现语言，不把 MATLAB 作为仅供参考的附录。

## 环境与依赖

调用 `<SKILL_ROOT>/scripts/check_matlab_env.m`，只检查选中功能对应的工具箱。常见映射：

| 功能 | MATLAB 工具或工具箱 |
|---|---|
| 线性/非线性/整数优化 | Optimization Toolbox |
| 统计、回归、分类、聚类 | Statistics and Machine Learning Toolbox |
| 时间序列与计量 | Econometrics Toolbox |
| 符号推导 | Symbolic Math Toolbox |
| 图论与基础可视化 | MATLAB 基础环境 |

不要默认要求所有工具箱，也不要因缺少某个未使用工具箱而阻断任务。

## 代码结构

```matlab
function main(seed)
arguments
    seed (1,1) double = 42
end
rng(seed, "twister");

projectRoot = fileparts(mfilename("fullpath"));
data = readtable(fullfile(projectRoot, "data", "input.csv"));
result = solveModel(data);
writetable(result.table, fullfile(projectRoot, "results", "问题1_结果.csv"));
plotResults(result, fullfile(projectRoot, "figures"));
end
```

- 用 `fullfile` 构造路径，不依赖当前工作目录。
- 用 `arguments` 校验输入。
- 随机算法调用 `rng(seed, "twister")`。
- 函数文件与主运行脚本分离时，保持函数名和文件名一致。
- 表格使用 `readtable`、`writetable`；数值矩阵使用 `readmatrix`、`writematrix`。
- 优化结果必须检查 `exitflag` 和约束残差。

## 结果与复现

在复现清单中记录 MATLAB `version`、`ver` 中实际用到的工具箱版本、随机种子、输入 SHA-256、参数和唯一命令，例如：

```text
matlab -batch "main(42)"
```

生成清单时向 `repro_manifest.py` 传入 `--runtime matlab`、`--runtime-version` 和工具箱版本 JSON：

```powershell
python "<SKILL_ROOT>/scripts/repro_manifest.py" `
  --project-root "<PROJECT_ROOT>" --seed 42 `
  --runtime matlab --runtime-version "R2025b" `
  --dependencies '{"Optimization Toolbox":"25.2"}' `
  --command 'matlab -batch "main(42)"'
```

## 出版级绘图

将 `<SKILL_ROOT>/scripts/apply_publication_style.m`、`audit_publication_figure.m` 与 `export_publication_figure.m` 复制到 `PROJECT_ROOT/utils/`，再由项目代码 `addpath` 调用。绘图前同样完成数据剖析、单图核心结论、主次面板与图表契约，不能把 MATLAB 作为低配可视化分支。

- `apply_publication_style(fig, "zh", "report", "cell")` 统一字体、期刊色板（默认 `nature`，可选 `science`/`cell`/`ieee`/`general`/`okabe_ito`/`wong`，与 Python 侧 `JOURNAL_PALETTES` 同源；MATLAB 固定用各期刊默认主色板）、线宽、最终尺寸和无网格线基线；图内不允许出现任何标题（上方、下方均不写）。
- `audit_publication_figure(fig)` 检查标题/标签/刻度是否可能超出画布，以及长标题、超量图例、稠密逐点标记、非零基线柱状图和对应小矩阵的冗余 colorbar。
- `export_publication_figure(fig, outputStem)` 默认先执行设计门禁，再只输出一个 300 DPI PNG；需要时传 `svg=true` 追加 SVG、`grayscalePreview=true` 追加灰度预览。
- 官方模板规定的尺寸、字体和格式优先；覆盖内置值时记录实际参数。
- 导出后运行 Python 标准库审计器 `figure_audit.py`，并实际打开 PNG 检查自动门禁无法可靠判断的缺字、刻度重叠、遮挡、尺度和多面板一致性。
- 主结论和辅助证据的信息量不同时，使用非对称 `tiledlayout` 跨格布局，不机械创建等宽双子图。
- 除非官方模板有明确冲突且已记录理由，不得把 `strictDesign` 设为 `false` 绕过设计门禁。
- MATLAB 不得调用 `grid on`；确有数值意义的参考线使用 `xline`/`yline` 并在图注说明。
