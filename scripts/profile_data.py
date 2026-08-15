"""数据剖析：读取 CSV/Excel，输出列类型、缺失、分布、异常、分组与相关性。

用法:
    python profile_data.py <data.csv|data.xlsx> [--group col1 col2] [--out report.txt]

输出:
    控制台打印剖析摘要；--out 时同时写入文本报告。
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd


def load_table(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_csv(path, sep=None, engine="python")


def iqr_outliers(series: pd.Series) -> int:
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((series < lo) | (series > hi)).sum())


def profile(df: pd.DataFrame, group_cols: list[str]) -> str:
    lines: list[str] = []
    lines.append(f"形状: {df.shape[0]} 行 x {df.shape[1]} 列")
    lines.append(f"列名: {list(df.columns)}")

    lines.append("\n== 逐列概要 ==")
    num_cols: list[str] = []
    for col in df.columns:
        s = df[col]
        missing = int(s.isna().sum())
        dtype = str(s.dtype)
        uniq = int(s.nunique())
        info = f"{col}: dtype={dtype}, 缺失={missing}, 唯一值={uniq}"
        if pd.api.types.is_numeric_dtype(s) and missing < len(s):
            num_cols.append(col)
            skew = float(s.skew())
            out = iqr_outliers(s.dropna())
            info += (
                f", min={s.min():.4g}, max={s.max():.4g}, "
                f"mean={s.mean():.4g}, skew={skew:.3f}, IQR异常≈{out}"
            )
        lines.append(info)

    if num_cols:
        lines.append("\n== 数值列相关性（Pearson）==")
        corr = df[num_cols].corr()
        lines.append(corr.round(3).to_string())
        strong = np.where((corr.abs() > 0.8) & (corr.abs() < 1.0))
        pairs = [
            (num_cols[i], num_cols[j])
            for i, j in zip(*strong)
            if i < j
        ]
        if pairs:
            lines.append(f"高相关对(|r|>0.8): {pairs}（注意多重共线性）")

    for gc in group_cols:
        if gc in df.columns:
            lines.append(f"\n== 分组样本量: {gc} ==")
            lines.append(df[gc].value_counts(dropna=False).to_string())

    lines.append("\n== 初步图表建议 ==")
    n_num = len(num_cols)
    n_cat = sum(
        1
        for c in df.columns
        if not pd.api.types.is_numeric_dtype(df[c]) or df[c].nunique() <= 12
    )
    suggestions = []
    if n_num >= 2:
        suggestions.append("相关性热力图 / 散点矩阵")
    if n_cat >= 1 and n_num >= 1:
        suggestions.append("分组箱线图 + 散点（注意样本量，小样本避免均值柱）")
    if n_num >= 1:
        suggestions.append("分布直方图 / KDE；如含时间列加折线趋势")
    if not suggestions:
        suggestions.append("以频数条形图展示分类分布")
    lines.append("、".join(suggestions))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="数据剖析")
    ap.add_argument("source", help="CSV 或 Excel 文件")
    ap.add_argument("--group", nargs="*", default=[], help="分组列名")
    ap.add_argument("--out", default=None, help="报告输出文件")
    args = ap.parse_args()

    try:
        df = load_table(args.source)
    except Exception as exc:  # noqa: BLE001
        print(f"读取失败: {exc}", file=sys.stderr)
        return 1

    report = profile(df, args.group)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"\n报告已写入: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
