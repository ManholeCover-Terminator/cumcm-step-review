#!/usr/bin/env python3
"""Check the minimal environment needed to generate math-modeling DOCX papers."""

import importlib.util
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


REQUIRED_MODULES = ["docx", "lxml"]
OPTIONAL_MODULES = [
    ("defusedxml", "OOXML 安全解析增强（缺失时自动回退标准库，建议安装）"),
]
OPTIONAL_BINARIES = ["pandoc"]


def main() -> int:
    missing = [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]
    if missing:
        print("缺少 Python 依赖: " + ", ".join(missing))
        print("安装: pip install python-docx lxml")
        return 1

    print("必需环境 OK: python-docx, lxml")
    for name, desc in OPTIONAL_MODULES:
        present = importlib.util.find_spec(name) is not None
        print(f"可选 Python 模块 {name}: {'OK' if present else 'MISSING'} ({desc})")
    optional = [name for name in OPTIONAL_BINARIES if shutil.which(name)]
    if optional:
        print("可选工具 OK: " + ", ".join(optional))
    else:
        print("可选工具缺失: pandoc（Markdown/LaTeX 整篇转 docx 时需要）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
