"""defusedxml 兼容层：优先使用安全解析器，缺失时回退标准库并警告一次。

docx 工具链解析的 XML 均为本地已解包的 OOXML 部件（非不可信远程输入）。
defusedxml 可用时仍优先使用，以保持防 XXE 的默认安全姿态；缺失时回退到
标准库 xml.dom.minidom，并导出与 defusedxml.minidom 相同的模块形状，
让既有代码无需改动即可运行。
"""

import sys
import types
import warnings

try:
    import defusedxml.minidom as _safe_minidom

    HAVE_DEFUSEDXML = True
except ImportError:  # pragma: no cover - 取决于运行环境
    import xml.dom.minidom as _safe_minidom

    HAVE_DEFUSEDXML = False
    if not getattr(sys, "_cumcm_defusedxml_warned", False):
        sys._cumcm_defusedxml_warned = True
        warnings.warn(
            "未安装 defusedxml，已回退到标准库 xml.dom.minidom 解析 OOXML 部件；"
            "仅用于本地文档解析。建议安装 defusedxml 恢复防 XXE 保护。",
            RuntimeWarning,
            stacklevel=2,
        )

minidom = _safe_minidom

# 兼容既有代码的 defusedxml.minidom.parseString(...) 写法。
defusedxml = types.ModuleType("defusedxml")
defusedxml.minidom = minidom

__all__ = ["HAVE_DEFUSEDXML", "defusedxml", "minidom"]
