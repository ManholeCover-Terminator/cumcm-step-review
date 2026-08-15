"""检查数学建模工作流所需的环境与依赖。

用法:
    python check_env.py

退出码:
    0  核心依赖齐全
    1  缺少核心 Python 包（建议先安装再继续）
    2  仅缺少可选工具（可继续，但部分验证会受限）
"""

from __future__ import annotations

import importlib.util
import shutil
import sys


CORE_PACKAGES = [
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "sklearn",
    "openpyxl",
]

OPTIONAL_TOOLS = [
    ("python", "数值计算与绘图"),
    ("typst", "Typst 论文编译（可选）"),
    ("xelatex", "LaTeX 论文编译（可选）"),
    ("drawio", "DrawIO 流程图导出（可选）"),
    ("draw.io", "DrawIO 备用命令（可选）"),
    ("pdftoppm", "PDF 转 PNG 视觉检查（可选）"),
    ("mutool", "PDF 转 PNG 备用（可选）"),
    ("magick", "PDF 转 PNG 备用（可选）"),
    ("pandoc", "文档转换（可选）"),
    ("soffice", "LibreOffice（Excel 公式重算，可选）"),
    ("matlab", "MATLAB 实现与绘图（可选）"),
]


def main() -> int:
    print("== Python ==")
    print(f"python: {sys.version.split()[0]}")

    print("\n== 核心 Python 包 ==")
    missing_core: list[str] = []
    for pkg in CORE_PACKAGES:
        ok = importlib.util.find_spec(pkg) is not None
        print(f"{pkg}: {'OK' if ok else 'MISSING'}")
        if not ok:
            missing_core.append(pkg)

    print("\n== 可选外部工具 ==")
    missing_tools: list[str] = []
    for tool, desc in OPTIONAL_TOOLS:
        path = shutil.which(tool)
        print(f"{tool}: {path or 'MISSING'}  ({desc})")
        if path is None:
            missing_tools.append(tool)

    print()
    if missing_core:
        print(f"缺少核心包: {', '.join(missing_core)}")
        print("建议安装: pip install numpy scipy pandas matplotlib scikit-learn openpyxl")
        return 1
    if missing_tools:
        print(f"缺少可选工具: {', '.join(missing_tools)}")
        print("可继续，但相关验证会受限；请按 doctor 思路补齐需要的能力。")
        return 2
    print("环境完整。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
