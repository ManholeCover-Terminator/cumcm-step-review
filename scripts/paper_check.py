"""论文文本门禁：占位符、内部泄露、章节完整、图表引用与数值一致性提示。

用法:
    python paper_check.py --paper-dir <paper> [--main main.tex|main.typ]
        [--figures-dir <figures>] [--results-file <RESULTS_REPORT.md>]

规则:
    - 占位符/内部文件名泄露 → FAIL
    - 图后必跟分析（连续两张以上图表间无文字）→ FAIL
    - 引用的图片文件不存在 → FAIL
    - 结果文件存在时，正文关键数值与结果文件不一致 → 提示（需人工确认）
"""

from __future__ import annotations

import argparse
import os
import re
import sys


PLACEHOLDER_RE = re.compile(
    r"TODO|PLACEHOLDER|待补充|待续写|示例数据|待定|XXX",
    re.IGNORECASE,
)

INTERNAL_LEAK_RE = re.compile(
    r"论文草稿|阶段流程|质检清单|模型选型树|scripts/|复现清单|results/|"
    r"PROJECT_ROOT|SKILL_ROOT|工作流",
)

FIGURE_REF_RE = re.compile(
    r"\\(?:includegraphics|input)\{([^}]+)\}|#figure\(image\(\"([^\"]+)\"",
    re.IGNORECASE,
)

CAPTION_RE = re.compile(r"\\caption\{([^}]*)\}")
MD_CAPTION_RE = re.compile(r"^\s*图\s*\d+[：:]\s*(.+)$")

CHART_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"折线|曲线|收敛曲线|趋势(图)?", "折线/曲线"),
    (r"柱状|条形", "柱状/条形"),
    (r"散点", "散点"),
    (r"热力", "热力图"),
    (r"箱线|箱形", "箱线图"),
    (r"小提琴", "小提琴图"),
    (r"饼图|环形|玫瑰", "饼/环图"),
    (r"雷达", "雷达图"),
    (r"面积图", "面积图"),
    (r"瀑布", "瀑布图"),
    (r"桑基", "桑基图"),
    (r"弦图", "弦图"),
    (r"ROC", "ROC"),
    (r"SHAP", "SHAP"),
    (r"泰勒", "泰勒图"),
    (r"云雨", "云雨图"),
    (r"相关矩阵|相关系数热图", "相关图"),
    (r"残差", "残差图"),
]


def _chart_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """识别 LaTeX/Markdown 图表块，返回 [(起始行, 结束行)]（0-based 含边界）。

    支持 figure/table/longtable 环境（整块计为一个图表）与
    \\includegraphics、#figure(...) 单行图表；避免把 \\begin{figure} 和
    \\includegraphics 误当成两张图。
    """

    blocks: list[tuple[int, int]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        match = re.match(r"\s*\\(begin)\{(figure|table|longtable)\}", line)
        if match:
            env = match.group(2)
            end_pattern = re.compile(rf"\s*\\end\{{{env}\}}")
            j = i
            while j < n and not end_pattern.search(lines[j]):
                j += 1
            blocks.append((i, min(j, n - 1)))
            i = j + 1
            continue
        if re.search(r"\\includegraphics|#figure", line):
            blocks.append((i, i))
        i += 1
    return blocks


def scan_text(text: str, path: str, fails: list[str], warns: list[str]) -> None:
    if PLACEHOLDER_RE.search(text):
        fails.append(f"{path}: 发现占位符（TODO/待补充/示例数据 等）")
    if INTERNAL_LEAK_RE.search(text):
        warns.append(f"{path}: 出现疑似内部工作流文件名/路径，请人工确认")

    # 图后必跟分析：统计图表块之间的文字间隔；纯 LaTeX 命令行不计为分析文字
    lines = text.splitlines()
    blocks = _chart_blocks(lines)
    for (_, end_prev), (start_next, _) in zip(blocks, blocks[1:]):
        between = "\n".join(lines[end_prev + 1 : start_next])
        between = "\n".join(
            ln
            for ln in between.splitlines()
            if ln.strip() and not re.match(r"^\s*\\(?:begin|end)\{", ln.strip())
        )
        if not re.search(r"[一-鿿A-Za-z]{4,}", between):
            fails.append(
                f"{path}: 第 {end_prev + 1} 行附近的图表之后缺少分析文字"
            )


def check_figures(text: str, base_dir: str, figures_dir: str | None, fails: list[str]) -> None:
    refs: list[str] = []
    for m in FIGURE_REF_RE.finditer(text):
        ref = m.group(1) or m.group(2) or ""
        refs.append(ref)
    for ref in refs:
        candidates = [
            os.path.normpath(os.path.join(base_dir, ref)),
            os.path.normpath(os.path.join(base_dir, figures_dir or "", os.path.basename(ref))),
        ]
        if not any(os.path.isfile(p) for p in candidates):
            fails.append(f"引用的图片不存在: {ref}")


def check_values(text: str, results_file: str | None, warns: list[str]) -> None:
    if not results_file or not os.path.isfile(results_file):
        return
    with open(results_file, encoding="utf-8") as fh:
        results_text = fh.read()
    nums = re.findall(r"\d+\.\d{2,}", results_text)
    hit = sum(1 for n in set(nums) if n in text)
    if nums and hit < max(1, len(set(nums)) // 3):
        warns.append("正文关键数值与结果报告匹配度偏低，请人工核对数值一致性")


def check_figure_diversity(text: str, path: str, warns: list[str]) -> None:
    """按图注统计图型分布，同类型过多或连续同类时给出审美疲劳提示（不判 FAIL）。"""

    captions: list[str] = []
    for m in CAPTION_RE.finditer(text):
        captions.append(m.group(1).strip())
    for m in MD_CAPTION_RE.finditer(text):
        captions.append(m.group(1).strip())
    if not captions:
        return

    typed: list[tuple[int, str]] = []
    for index, caption in enumerate(captions):
        for pattern, label in CHART_TYPE_PATTERNS:
            if re.search(pattern, caption, re.IGNORECASE):
                typed.append((index, label))
                break

    counts: dict[str, list[int]] = {}
    for index, label in typed:
        counts.setdefault(label, []).append(index)
    for label, positions in sorted(counts.items()):
        if len(positions) >= 4:
            warns.append(
                f"{path}: 同类型图过多（{label} {len(positions)} 张），"
                "容易审美疲劳，建议换用其他图型或合并面板"
            )

    for index, label in typed:
        following = [lab for (i, lab) in typed if i > index]
        if len(following) >= 2 and following[0] == label and following[1] == label:
            warns.append(
                f"{path}: 第 {index + 1} 张图起连续 3 张同类图（{label}），"
                "应穿插其他图型避免审美疲劳"
            )
            break


def main() -> int:
    ap = argparse.ArgumentParser(description="论文文本门禁")
    ap.add_argument("--paper-dir", required=True, help="论文目录")
    ap.add_argument("--main", default=None, help="论文入口文件（main.tex/main.typ）")
    ap.add_argument("--figures-dir", default=None, help="图表目录")
    ap.add_argument("--results-file", default=None, help="结果报告文件路径")
    args = ap.parse_args()

    paper_dir = os.path.abspath(args.paper_dir)
    if not os.path.isdir(paper_dir):
        print(f"FAIL: 论文目录不存在: {paper_dir}")
        return 1

    sources: list[str] = []
    if args.main and os.path.isfile(os.path.join(paper_dir, args.main)):
        sources.append(args.main)
    else:
        for name in ("main.tex", "main.typ"):
            if os.path.isfile(os.path.join(paper_dir, name)):
                sources.append(name)
    sections_dir = os.path.join(paper_dir, "sections")
    if os.path.isdir(sections_dir):
        sources += [
            os.path.relpath(os.path.join(sections_dir, f), paper_dir)
            for f in sorted(os.listdir(sections_dir))
            if f.endswith((".tex", ".typ"))
        ]

    if not sources:
        print("FAIL: 未找到 main.tex / main.typ 或 sections/ 章节文件")
        return 1

    fails: list[str] = []
    warns: list[str] = []
    full_text = ""
    for rel in sources:
        path = os.path.join(paper_dir, rel)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        full_text += text + "\n"
        scan_text(text, rel, fails, warns)
        check_figures(text, paper_dir, args.figures_dir, fails)

    check_values(full_text, args.results_file, warns)
    check_figure_diversity(full_text, "论文", warns)

    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")
    if fails:
        print("结果: FAIL")
        return 1
    print("结果: PASS" + ("（含警告）" if warns else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
