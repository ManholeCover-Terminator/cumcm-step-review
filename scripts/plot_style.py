"""统一绘图风格入口：期刊配色、色盲安全、按最终尺寸导出。

用法:
    from plot_style import apply_publication_style, export_figure

    apply_publication_style(journal="nature", lang="zh")
    fig, ax = plt.subplots(figsize=(3.5, 2.625))
    ...
    export_figure(fig, "figures/result_q1_xxx", dpi=300)

用户定制（硬性）:
    - 图内不写标题、不画面板编号（add_panel_labels 保留但默认不使用）。
    - 图内文字按最终印刷尺寸设定：正文标签 8.5–11pt，最小 ≥7.5pt；
      禁止 10pt 默认字号整图缩放，避免图大字小。
    - 布局按面板数量和证据权重选择（1×2、2×1、3×1、2×3、主图+辅助等），
      禁止默认 2×2；图宽以期刊栏宽为基准（国赛按正文栏宽）。
    - JOURNAL_PALETTES 多套：nature/science/cell/ieee/general/okabe-ito/wong，
      每套含主色板与可选变体（variant），默认 nature（用户定制主色板）；
      journal="okabe-ito" 时严格色盲友好。
    - 导出默认只保存一个 300 DPI PNG；svg/灰度预览/extra_formats 按需追加。
"""

from __future__ import annotations

import logging
import unicodedata
import warnings
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


# 语义色（用途命名，不绑定具体模型）。默认 Nature 风格、色盲友好。
PALETTE = {
    "primary": "#0072B2",
    "secondary": "#E69F00",
    "positive": "#009E73",
    "contrast": "#D55E00",
    "accent": "#CC79A7",
    "sky": "#56B4E9",
    "neutral": "#6B7280",
    "dark": "#222222",
}

COLOR_SEQUENCE = tuple(
    PALETTE[name]
    for name in ("primary", "secondary", "positive", "contrast", "accent", "sky", "neutral")
)

# 期刊专属色板（用户定制扩展）。主色为类别色，顺序即使用顺序；
# 色带为连续/发散数据用；variants 为同一期刊的备选色板，default_variant 为默认变体。
JOURNAL_PALETTES: dict[str, dict] = {
    "nature": {
        "main": ["#0F6BBD", "#F26F21", "#9ECAE1", "#083C5F", "#7F8C8D"],
        "variants": {
            "主色板": ["#0F6BBD", "#F26F21", "#9ECAE1", "#083C5F", "#7F8C8D"],
            "冷色板": ["#386CB0", "#7FC97F", "#BEAED4"],
            "珊瑚红板": ["#E64B35", "#4DBBD5", "#8A8A8A"],
            "多色方案": ["#0072B2", "#D55E00", "#009E73", "#F0E442"],
        },
        "default_variant": "主色板",
        "sequential": "viridis",
        "diverging": "RdBu_r",
        "semantic": {"good": "#009E73", "warn": "#F26F21", "bad": "#D55E00"},
        "note": "Nature 风格（用户定制）：蓝主橙强调；含冷色/珊瑚红/多色变体",
    },
    "science": {
        "main": ["#E41937", "#A31A30", "#2F6EB5", "#8FC1E1", "#8F8F8F"],
        "variants": {
            "主色板": ["#E41937", "#A31A30", "#2F6EB5", "#8FC1E1", "#8F8F8F"],
            "莫兰迪板": ["#8FA6B4", "#A3B693", "#E0A87C"],
        },
        "default_variant": "主色板",
        "sequential": "magma",
        "diverging": "RdBu_r",
        "semantic": {"good": "#008B45", "warn": "#F39B7F", "bad": "#E41937"},
        "note": "Science 风格（用户定制）：红色为绝对主角，蓝灰辅助",
    },
    "cell": {
        "main": ["#1E8449", "#186138", "#82E0AA", "#8E44AD", "#566573"],
        "variants": {
            "主色板": ["#1E8449", "#186138", "#82E0AA", "#8E44AD", "#566573"],
            "大地色板": ["#B07D5B", "#D9B98C", "#8A9A5B", "#7E8C8D", "#C05B4D"],
            "经典对比板": ["#2E5A88", "#D95F02"],
            "UMAP聚类色板": ["#7D8CA3", "#9FB3A0", "#C4A97E", "#B4919C", "#8A9B7C"],
            "双状态对比色板": ["#4DBBD5", "#7A8B99"],
            "多组学整合色板": ["#5B8DB8", "#8FB36E", "#C29B4D", "#9B7BB5", "#D98B8B"],
            "系统发育树色板": ["#3B7A57", "#8C6DAF", "#D9A441", "#4E79A7", "#B85450"],
            "基因表达色板": ["#E0E0E0", "#6E8B3D", "#4E79A7", "#B85450", "#C9A227"],
        },
        "default_variant": "主色板",
        "sequential": "viridis",
        "diverging": "RdBu_r",
        "semantic": {"good": "#1E8449", "warn": "#C9A227", "bad": "#B85450"},
        "note": "Cell 风格（用户定制）：绿系主色调，低饱和质感，生信友好",
    },
    "okabe-ito": {
        "main": ["#E69F00", "#56B4E9", "#009E73", "#F0E442",
                 "#0072B2", "#D55E00", "#CC79A7", "#999999"],
        "variants": {"主色板": ["#E69F00", "#56B4E9", "#009E73", "#F0E442",
                                "#0072B2", "#D55E00", "#CC79A7", "#999999"]},
        "default_variant": "主色板",
        "sequential": "viridis",
        "diverging": "RdBu_r",
        "semantic": {"good": "#009E73", "warn": "#E69F00", "bad": "#D55E00"},
        "note": "色盲友好黄金标准（Okabe-Ito 八色板）",
    },
    "wong": {
        "main": ["#0077BB", "#EE7733", "#33BBEE", "#CC3311",
                 "#009988", "#BBBBBB"],
        "variants": {"主色板": ["#0077BB", "#EE7733", "#33BBEE", "#CC3311",
                                "#009988", "#BBBBBB"]},
        "default_variant": "主色板",
        "sequential": "viridis",
        "diverging": "RdBu_r",
        "semantic": {"good": "#009988", "warn": "#EE7733", "bad": "#CC3311"},
        "note": "色盲友好（Wong 六色板）",
    },
    "ieee": {
        "main": ["#0072BD", "#D95319", "#EDB120", "#7E2F8E",
                 "#77AC30", "#4DBEEE", "#A2142F"],
        "variants": {"主色板": ["#0072BD", "#D95319", "#EDB120", "#7E2F8E",
                                "#77AC30", "#4DBEEE", "#A2142F"]},
        "default_variant": "主色板",
        "sequential": "viridis",
        "diverging": "RdBu_r",
        "semantic": {"good": "#77AC30", "warn": "#EDB120", "bad": "#A2142F"},
        "note": "参考 IEEE 论文常用配色",
    },
    "general": {
        "main": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                 "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "variants": {"主色板": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
                                "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]},
        "default_variant": "主色板",
        "sequential": "plasma",
        "diverging": "RdBu_r",
        "semantic": {"good": "#2ca02c", "warn": "#ff7f0e", "bad": "#d62728"},
        "note": "通用色板",
    },
}

# 期刊预设：只覆盖与期刊相关的结构参数（线宽、边框、字体族）。
JOURNAL_PRESETS: dict[str, dict] = {
    "nature": {
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.minor.width": 0.4,
        "ytick.minor.width": 0.4,
        "axes.spines.top": False,
        "axes.spines.right": False,
    },
    "science": {
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
    },
    "cell": {
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
    },
    "okabe-ito": {
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
    },
    "wong": {
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "axes.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
    },
    "ieee": {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "lines.linewidth": 1.0,
        "lines.markersize": 4,
        "axes.linewidth": 0.7,
        "axes.spines.top": True,
        "axes.spines.right": True,
    },
    "general": {
        "lines.linewidth": 1.2,
        "lines.markersize": 5,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
    },
}

# 图宽基准（英寸）：期刊栏宽。国赛正文版心约 5.9 in，可用 "cumcm"。
WIDTHS_IN: dict[str, float] = {
    "single": 3.5,
    "double": 7.2,
    "report": 6.3,
    "cumcm": 5.9,
}

# 字号自适应：正文标签 8.5–11pt（按最终图宽线性插值），最小 ≥7.5pt。
FONT_MIN_WIDTH = 3.5
FONT_MAX_WIDTH = 7.2
FONT_MIN_SIZE = 8.5
FONT_MAX_SIZE = 11.0

_CJK_SANS = (
    "Noto Sans CJK SC",
    "Noto Sans SC",
    "Source Han Sans SC",
    "Source Han Sans CN",
    "Microsoft YaHei",
    "SimHei",
    "PingFang SC",
    "Heiti SC",
    "WenQuanYi Zen Hei",
    "Arial Unicode MS",
)

_CJK_SERIF = (
    "Noto Serif CJK SC",
    "Noto Serif SC",
    "Source Han Serif SC",
    "Source Han Serif CN",
    "SimSun",
    "STSong",
    "Songti SC",
)


def _available_fonts() -> set[str]:
    from matplotlib import font_manager

    return {item.name for item in font_manager.fontManager.ttflist}


def choose_font(language: str = "zh", serif_for_zh: bool = True) -> str:
    """选择可用字体；中文字体缺失时给出警告并安全回退。"""

    if language not in {"zh", "en"}:
        raise ValueError("language 只能是 'zh' 或 'en'")
    available = _available_fonts()
    if language == "zh":
        priority = _CJK_SERIF + _CJK_SANS if serif_for_zh else _CJK_SANS
        for name in priority:
            if name in available:
                return name
        warnings.warn(
            "未检测到常用中文字体，已回退到 DejaVu Sans；导出前必须检查中文和特殊符号是否缺字。",
            RuntimeWarning,
            stacklevel=2,
        )
    for name in ("Arial", "Helvetica", "DejaVu Sans"):
        if name in available:
            return name
    return "DejaVu Sans"


def figure_size(width: str = "report", aspect: float = 0.62) -> tuple[float, float]:
    """按最终使用宽度返回英寸尺寸，避免在论文中二次大幅缩放。"""

    if width not in WIDTHS_IN:
        raise ValueError(f"未知宽度方案: {width}，可选 {sorted(WIDTHS_IN)}")
    if aspect <= 0:
        raise ValueError("aspect 必须大于 0")
    width_in = WIDTHS_IN[width]
    return width_in, width_in * aspect


def font_sizes_for_width(width: str = "report") -> dict[str, float]:
    """按最终图宽计算自适应字号（用户定制：正文标签 8.5–11pt，最小 ≥7.5pt）。

    正文随图宽在 8.5–11 pt 间线性变化；轴标签 = 正文 + 0.5 pt，
    刻度与图例 = 正文 − 0.4 pt（不低于 7.5 pt）。任何档位都不停留在
    10pt 默认字号整图缩放。
    """

    if width not in WIDTHS_IN:
        raise ValueError(f"未知宽度方案: {width}，可选 {sorted(WIDTHS_IN)}")
    width_in = WIDTHS_IN[width]
    ratio = (width_in - FONT_MIN_WIDTH) / (FONT_MAX_WIDTH - FONT_MIN_WIDTH)
    ratio = min(max(ratio, 0.0), 1.0)
    body = FONT_MIN_SIZE + ratio * (FONT_MAX_SIZE - FONT_MIN_SIZE)
    return {
        "body": body,
        "axes_label": min(11.0, body + 0.5),
        "tick": max(7.5, body - 0.4),
        "legend": max(7.5, body - 0.4),
    }


def _try_sciencplots(journal: str | None) -> bool:
    """SciencePlots 可用时应用其风格栈；缺省或失败时静默回退内置预设。"""
    try:
        import scienceplots  # noqa: F401
    except ImportError:
        return False
    stack = ["science"]
    if journal == "nature":
        stack.append("nature")
    elif journal == "ieee":
        stack.append("ieee")
    stack.append("no-latex")
    try:
        plt.style.use(stack)
        return True
    except OSError:
        return False


def apply_publication_style(
    language: str = "zh",
    width: str = "report",
    *,
    journal: str | None = None,
    variant: str | None = None,
    lang: str | None = None,
    serif_for_zh: bool = True,
    use_sciplots: bool = False,
) -> dict:
    """应用克制型 Nature/SCI 出版样式基线。

    journal 可选 nature/science/cell/ieee/general/okabe-ito/wong，默认 nature；
    variant 可选该期刊 variants 中的变体名（如 nature 的 冷色板/珊瑚红板/多色方案、
    cell 的 大地色板/经典对比板/UMAP聚类色板 等），缺省用 default_variant；
    lang 是 language 的别名（新老文档两种写法都兼容）；
    serif_for_zh=True 时中文使用宋体类衬线字体（宋体正文 + Times 数字混排）；
    use_sciplots=True 时优先尝试 SciencePlots，缺省或失败自动回退内置预设。
    最终物理尺寸始终由 width 决定，保证图表契约中的最终宽高可复现。
    """

    from cycler import cycler

    if lang is not None:
        language = lang
    if journal is None:
        journal = "nature"
    if journal not in JOURNAL_PALETTES:
        raise ValueError(
            f"未知期刊配色: {journal}，可选 {sorted(JOURNAL_PALETTES)}"
        )
    font_name = choose_font(language, serif_for_zh=serif_for_zh)
    size = figure_size(width)
    font_sizes = font_sizes_for_width(width)
    palette_entry = JOURNAL_PALETTES[journal]
    variants = palette_entry.get("variants") or {}
    chosen_variant = variant or palette_entry.get("default_variant") or "主色板"
    if variant is not None and chosen_variant not in variants:
        raise ValueError(
            f"未知配色变体: {journal}/{variant}，可选 {sorted(variants)}"
        )
    palette = variants.get(chosen_variant) or palette_entry["main"]
    sciplots_used = _try_sciencplots(journal) if use_sciplots else False
    plt.rcParams.update(
        {
            "figure.figsize": size,
            "figure.dpi": 100,
            "savefig.dpi": 300,
            "figure.constrained_layout.use": True,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.family": "sans-serif",
            "font.sans-serif": [font_name, "Arial", "Helvetica", "DejaVu Sans"],
            "font.size": font_sizes["body"],
            "axes.titlesize": min(11.0, font_sizes["body"] + 0.5),
            "axes.titleweight": "normal",
            "axes.titlelocation": "left",
            "axes.titlepad": 4.0,
            "axes.labelsize": font_sizes["axes_label"],
            "xtick.labelsize": font_sizes["tick"],
            "ytick.labelsize": font_sizes["tick"],
            "legend.fontsize": font_sizes["legend"],
            "axes.linewidth": 0.7,
            "lines.linewidth": 1.1,
            "lines.markersize": 3.5,
            "patch.linewidth": 0.6,
            "xtick.major.size": 3.0,
            "ytick.major.size": 3.0,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "legend.frameon": False,
            "legend.handlelength": 1.6,
            "legend.borderaxespad": 0.4,
            "axes.unicode_minus": False,
            "axes.prop_cycle": cycler(color=palette),
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "savefig.facecolor": "white",
        }
    )
    plt.rcParams.update(JOURNAL_PRESETS.get(journal, JOURNAL_PRESETS["general"]))
    if language == "zh" and serif_for_zh:
        plt.rcParams["font.family"] = "serif"
        plt.rcParams["font.serif"] = [font_name, "Times New Roman", "Times", "DejaVu Serif"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.figsize"] = size
    plt.rcParams["figure.constrained_layout.use"] = True
    return {
        "font": font_name,
        "size_inches": size,
        "colors": palette,
        "font_sizes": font_sizes,
        "journal": journal,
        "variant": chosen_variant,
        "sciplots_used": sciplots_used,
    }


def publication_subplots(
    nrows: int = 1,
    ncols: int = 1,
    *,
    width: str = "report",
    aspect: float = 0.62,
    width_ratios: Sequence[float] | None = None,
    height_ratios: Sequence[float] | None = None,
    squeeze: bool = True,
):
    """按最终尺寸创建子图，并允许显式声明主次面板比例。"""

    if nrows < 1 or ncols < 1:
        raise ValueError("nrows 和 ncols 必须大于 0")
    if width_ratios is not None and len(width_ratios) != ncols:
        raise ValueError("width_ratios 数量必须与 ncols 一致")
    if height_ratios is not None and len(height_ratios) != nrows:
        raise ValueError("height_ratios 数量必须与 nrows 一致")
    gridspec_kw = {}
    if width_ratios is not None:
        gridspec_kw["width_ratios"] = list(width_ratios)
    if height_ratios is not None:
        gridspec_kw["height_ratios"] = list(height_ratios)
    return plt.subplots(
        nrows,
        ncols,
        figsize=figure_size(width, aspect),
        layout="constrained",
        gridspec_kw=gridspec_kw or None,
        squeeze=squeeze,
    )


def add_panel_labels(
    axes: Iterable,
    labels: Sequence[str] | None = None,
    *,
    x_offset_pt: float = -8.0,
    y_offset_pt: float = 1.0,
    style: str = "nature",
) -> None:
    """在各面板左上外侧添加面板编号（保留但默认不使用）。

    style="nature" 使用小写粗体 a、b、c；style="ieee" 使用 (a)、(b)、(c)。
    按用户定制，默认绘图流程不调用本函数：图内不画面板编号。
    """

    axes_list = list(axes)
    if style not in {"nature", "ieee"}:
        raise ValueError("style 只能是 'nature' 或 'ieee'")
    if labels is not None:
        panel_labels = list(labels)
    elif style == "ieee":
        panel_labels = [f"({chr(97 + i)})" for i in range(len(axes_list))]
    else:
        panel_labels = [chr(97 + i) for i in range(len(axes_list))]
    if len(panel_labels) != len(axes_list):
        raise ValueError("labels 数量必须与 axes 数量一致")
    for axis, label in zip(axes_list, panel_labels):
        axis.annotate(
            label,
            xy=(0, 1),
            xycoords="axes fraction",
            xytext=(x_offset_pt, y_offset_pt),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            annotation_clip=False,
        )


def finalize_figure(fig):
    """理顺多面板版面并让 renderer 就绪，返回同一 Figure。"""
    try:
        fig.set_layout_engine("constrained")
    except AttributeError:
        try:
            fig.set_constrained_layout(True)
        except AttributeError:
            pass
    fig.canvas.draw()
    return fig


def render_preview(
    fig_or_path,
    out_png: str | Path = "_preview.png",
    dpi: int = 150,
) -> str:
    """渲染一张 PNG 预览供 AI 读图复核。

    fig 为 matplotlib Figure 时直接保存；路径为位图时原样返回；
    路径为 PDF 时需要可选的 PyMuPDF。预览只用于读图自检，
    不替代 export_figure() 的正式导出。
    """

    if hasattr(fig_or_path, "savefig"):
        output = Path(out_png).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        fig_or_path.savefig(output, dpi=dpi, bbox_inches="tight")
        return str(output)

    path = Path(fig_or_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    extension = path.suffix.lower().lstrip(".")
    if extension in {"png", "tif", "tiff", "jpg", "jpeg", "bmp"}:
        return str(path)
    if extension == "pdf":
        try:
            import fitz
        except ImportError as error:
            raise RuntimeError(
                "把 PDF 渲染成预览需要 PyMuPDF；读图复核更推荐直接把 matplotlib "
                "Figure 对象传给 render_preview。"
            ) from error
        document = fitz.open(path)
        pixmap = document[0].get_pixmap(dpi=dpi)
        output = Path(out_png).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(str(output))
        document.close()
        return str(output)
    raise RuntimeError(f"不支持从 .{extension} 生成预览；请传 Figure 对象或位图路径。")


class _GlyphHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record) -> None:
        message = record.getMessage()
        if "Glyph" in message and "missing from font" in message:
            self.messages.append(message)


def _labels_overlap(labels, renderer, axis: str) -> bool:
    boxes = [
        label.get_window_extent(renderer)
        for label in labels
        if label.get_visible() and label.get_text().strip()
    ]
    boxes.sort(key=(lambda box: box.x0) if axis == "x" else (lambda box: box.y0))
    if axis == "x":
        return any(left.x1 > right.x0 + 1 for left, right in zip(boxes, boxes[1:]))
    return any(lower.y1 > upper.y0 + 1 for lower, upper in zip(boxes, boxes[1:]))


def audit_layout(fig) -> list[str]:
    """在导出前检查缺字、画布外文字、相邻刻度重叠和过小字号。"""

    import matplotlib.text as mtext

    handler = _GlyphHandler()
    logger = logging.getLogger("matplotlib")
    logger.addHandler(handler)
    caught: list[warnings.WarningMessage] = []
    try:
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            fig.canvas.draw()
            caught = list(record)
    finally:
        logger.removeHandler(handler)

    messages = handler.messages + [
        str(item.message)
        for item in caught
        if "Glyph" in str(item.message) and "missing from font" in str(item.message)
    ]
    issues = [f"缺字：{message}" for message in dict.fromkeys(messages)]

    for text in fig.findobj(mtext.Text):
        size = text.get_fontsize()
        if size and size < 7.5:
            issues.append(f"小于 7.5pt 文本: {text.get_text()[:24]!r}")

    renderer = fig.canvas.get_renderer()
    width, height = fig.bbox.width, fig.bbox.height
    tick_ids = {
        id(label)
        for axis in fig.axes
        for label in (*axis.get_xticklabels(), *axis.get_yticklabels())
    }
    clipped = []
    for text in fig.findobj(mtext.Text):
        if id(text) in tick_ids or not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > width + 1 or box.y1 > height + 1:
            clipped.append(text.get_text().replace("\n", " ")[:24])
    if clipped:
        issues.append("文字可能超出画布：" + "、".join(dict.fromkeys(clipped)))

    for index, axis in enumerate(fig.axes, start=1):
        if _labels_overlap(axis.get_xticklabels(), renderer, "x"):
            issues.append(f"第 {index} 个坐标轴的 x 刻度标签重叠")
        if _labels_overlap(axis.get_yticklabels(), renderer, "y"):
            issues.append(f"第 {index} 个坐标轴的 y 刻度标签重叠")
    return issues


def _display_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
        for character in text
    )


def _is_colorbar_axis(axis) -> bool:
    return axis.get_label() == "<colorbar>" or hasattr(axis, "_colorbar")


def audit_design(fig) -> list[str]:
    """检查可由对象结构确定的高风险设计，避免"文件合格、图却不好看"。"""

    from matplotlib.container import BarContainer

    issues: list[str] = []
    data_axes = [axis for axis in fig.axes if not _is_colorbar_axis(axis)]
    colorbar_axes = [axis for axis in fig.axes if _is_colorbar_axis(axis)]
    colorbar_mappables = {
        id(axis._colorbar.mappable)
        for axis in colorbar_axes
        if hasattr(axis, "_colorbar") and getattr(axis._colorbar, "mappable", None) is not None
    }
    for index, axis in enumerate(data_axes, start=1):
        for location in ("left", "center", "right"):
            title = axis.get_title(loc=location).strip()
            if title:
                issues.append(
                    f"第 {index} 个坐标轴不允许出现标题；标题信息一律放图注/图表契约"
                )
                break

    suptitle = getattr(fig, "_suptitle", None)
    if suptitle is not None and suptitle.get_text().strip():
        issues.append("整图标题（suptitle）不允许出现；标题信息一律放图注/图表契约")

        legend = axis.get_legend()
        if legend is not None and len(legend.get_texts()) > 5:
            issues.append(
                f"第 {index} 个坐标轴图例超过 5 项；应直接标注、改为共享图例或拆分证据"
            )

        for line in axis.lines:
            marker = line.get_marker()
            if marker in {None, "", " ", "None", "none"}:
                continue
            point_count = len(line.get_xdata(orig=False))
            if point_count > 25 and line.get_markevery() is None:
                issues.append(
                    f"第 {index} 个坐标轴对 {point_count} 个点逐点绘制标记；"
                    "应取消标记或设置 markevery"
                )
                break

        for container in axis.containers:
            if not isinstance(container, BarContainer) or not container.patches:
                continue
            if container.orientation == "vertical":
                lower, upper = axis.get_ylim()
            else:
                lower, upper = axis.get_xlim()
            tolerance = max(abs(upper - lower), 1.0) * 1e-9
            if lower > tolerance or upper < -tolerance:
                issues.append(
                    f"第 {index} 个坐标轴的柱状图未从零开始；"
                    "若必须截断，应改用点图/区间图并显式说明"
                )
                break

        for image in axis.images:
            values = image.get_array()
            if (
                getattr(values, "size", 0) <= 4
                and len(axis.texts) >= getattr(values, "size", 0)
                and id(image) in colorbar_mappables
            ):
                issues.append(
                    f"第 {index} 个坐标轴是已标数值的 2×2 小矩阵，"
                    "不应再使用冗余 colorbar"
                )
                break
    for legend in fig.legends:
        if len(legend.get_texts()) > 5:
            issues.append("整图共享图例超过 5 项；应直接标注、拆分证据或突出核心系列")
            break
    return issues


def _is_skill_root(path: Path) -> bool:
    return (path / "SKILL.md").is_file()


def resolve_output_stem(output_stem: str | Path) -> Path:
    """解析导出路径，并禁止把任务产物写回 Skill 目录。"""

    stem = Path(output_stem).expanduser().resolve()
    if stem.suffix.lower() in {".svg", ".png", ".pdf"}:
        stem = stem.with_suffix("")
    if any(
        _is_skill_root(candidate)
        for candidate in (stem.parent, *stem.parent.parents)
    ):
        raise ValueError("图形产物必须写入 PROJECT_ROOT，不能写入 SKILL_ROOT")
    return stem


def _save_grayscale_preview(png_path: Path, dpi: int) -> Path:
    import matplotlib.image as image_io
    import numpy as np

    pixels = image_io.imread(png_path)
    rgb = pixels[..., :3]
    if pixels.shape[-1] == 4:
        alpha = pixels[..., 3:4]
        rgb = rgb * alpha + (1 - alpha)
    grayscale = np.dot(rgb, (0.2126, 0.7152, 0.0722))
    output = png_path.parent / "_qa" / f"{png_path.stem}_grayscale.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image_io.imsave(output, grayscale, cmap="gray", vmin=0, vmax=1, dpi=dpi)
    return output


def export_figure(
    fig,
    output_stem: str | Path,
    *,
    dpi: int = 300,
    svg: bool = False,
    grayscale_preview: bool = False,
    strict_layout: bool = True,
    strict_design: bool = True,
    extra_formats: Sequence[str] = (),
    size_inches: tuple[float, float] | None = None,
) -> dict[str, str]:
    """按固定物理尺寸导出，并执行布局与高风险设计门禁。

    默认只输出一个至少 300 DPI 的 PNG；svg=True 时额外输出可编辑文本的
    SVG，grayscale_preview=True 时额外输出灰度预览，extra_formats 可追加
    "pdf"/"eps"。size_inches 仅在显式传入时覆写最终尺寸，仍禁用
    bbox_inches="tight"，避免图表契约中的物理尺寸被偷换。
    """

    if dpi < 300:
        raise ValueError("论文图 PNG 的 dpi 不能低于 300")
    supported_extra = {"pdf", "eps"}
    extra = [fmt.lower().lstrip(".") for fmt in extra_formats]
    unknown = [fmt for fmt in extra if fmt not in supported_extra]
    if unknown:
        raise ValueError(f"extra_formats 仅支持 {sorted(supported_extra)}；收到 {unknown}")
    if size_inches is not None:
        if len(size_inches) != 2 or any(value <= 0 for value in size_inches):
            raise ValueError("size_inches 必须为 (width, height) 且均为正数")
        fig.set_size_inches(*size_inches)
    layout_issues = audit_layout(fig)
    if strict_layout and layout_issues:
        raise ValueError("版面预检未通过：" + "；".join(layout_issues))
    design_issues = audit_design(fig)
    if strict_design and design_issues:
        raise ValueError("出版设计预检未通过：" + "；".join(design_issues))
    stem = resolve_output_stem(output_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    png_path = stem.with_suffix(".png")
    # 不使用 bbox_inches='tight'，否则会改变图表契约中的最终物理尺寸。
    fig.savefig(png_path, dpi=dpi)
    outputs: dict[str, str] = {"png": str(png_path)}
    if svg:
        svg_path = stem.with_suffix(".svg")
        fig.savefig(svg_path)
        outputs["svg"] = str(svg_path)
    for fmt in extra:
        extra_path = stem.with_suffix(f".{fmt}")
        fig.savefig(extra_path)
        outputs[fmt] = str(extra_path)
    if grayscale_preview:
        outputs["grayscale"] = str(_save_grayscale_preview(png_path, dpi))
    print("已保存:")
    for path in outputs.values():
        print(f"  {path}")
    return outputs


__all__ = [
    "COLOR_SEQUENCE",
    "JOURNAL_PALETTES",
    "JOURNAL_PRESETS",
    "PALETTE",
    "WIDTHS_IN",
    "add_panel_labels",
    "apply_publication_style",
    "audit_design",
    "audit_layout",
    "choose_font",
    "export_figure",
    "finalize_figure",
    "font_sizes_for_width",
    "figure_size",
    "publication_subplots",
    "render_preview",
    "resolve_output_stem",
]
