"""图表审计：检查目录中图表文件的完整性与基本质量。

用法:
    python figure_audit.py <figures_dir> [--questions q1 q2 ...] [--strict]

规则（用户定制）:
    - 默认只要求 PNG 非空；SVG 存在时文本检查降级为提示，不判 FAIL
    - 不强制 SVG/PNG 配对
    - --strict 时：空文件、子问题覆盖缺失判 FAIL
"""

from __future__ import annotations

import argparse
import os
import re
import sys


def audit_dir(fig_dir: str, questions: list[str], strict: bool) -> int:
    if not os.path.isdir(fig_dir):
        print(f"FAIL: 图表目录不存在: {fig_dir}")
        return 1

    files = sorted(os.listdir(fig_dir))
    pngs = [f for f in files if f.lower().endswith(".png")]
    svgs = [f for f in files if f.lower().endswith(".svg")]
    pdfs = [f for f in files if f.lower().endswith(".pdf")]

    fails: list[str] = []
    warns: list[str] = []
    print(f"目录: {fig_dir}")
    print(f"PNG: {len(pngs)} 张, SVG: {len(svgs)} 张, PDF: {len(pdfs)} 张")

    empty = [
        f
        for f in files
        if os.path.isfile(os.path.join(fig_dir, f)) and os.path.getsize(os.path.join(fig_dir, f)) == 0
    ]
    if empty:
        msg = f"空文件: {empty}"
        if strict:
            fails.append(msg)
        else:
            warns.append(msg)

    for f in pngs:
        path = os.path.join(fig_dir, f)
        try:
            from PIL import Image

            with Image.open(path) as im:
                print(f"  {f}: {im.size[0]}x{im.size[1]}px, mode={im.mode}")
        except Exception as exc:  # noqa: BLE001
            warns.append(f"{f}: 无法读取图像尺寸 ({exc})")

    if svgs:
        warns.append(
            f"检测到 {len(svgs)} 张 SVG（存在即可，文本检查降级为提示，不判 FAIL）"
        )

    if questions:
        declared = set(questions)
        found_q: set[str] = set()
        for f in pngs + svgs + pdfs:
            found_q.update(re.findall(r"q\d+", f, flags=re.IGNORECASE))
        extra = sorted(found_q - declared, key=lambda t: (len(t), t))
        if extra:
            warns.append(
                "目录包含未在 --questions 中声明的子问题图: "
                + ", ".join(extra)
                + "（若属于当前审计范围，请补传对应 --questions）"
            )
        missing_q: list[str] = []
        for q in questions:
            covered = [
                f
                for f in pngs + svgs + pdfs
                if q in f
            ]
            if not covered:
                missing_q.append(q)
        if missing_q:
            msg = f"以下子问题无图表覆盖: {missing_q}"
            if strict:
                fails.append(msg)
            else:
                warns.append(msg)
        else:
            print(f"子问题覆盖: {', '.join(questions)} 均有图表")

    for w in warns:
        print(f"WARN: {w}")
    for f in fails:
        print(f"FAIL: {f}")

    if fails:
        print("结果: FAIL")
        return 1
    print("结果: PASS" + ("（含警告）" if warns else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="图表审计")
    ap.add_argument("fig_dir", help="图表目录")
    ap.add_argument("--questions", nargs="*", default=[], help="子问题标识，如 q1 q2 q3")
    ap.add_argument("--strict", action="store_true", help="严格模式：空文件/覆盖缺失判 FAIL")
    args = ap.parse_args()
    return audit_dir(args.fig_dir, args.questions, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
