#!/usr/bin/env python3
"""
LaTeX 方程 → Word OMML 公式转换工具

将 .docx 文档中的 LaTeX 占位符替换为 Word 原生的数学公式（OMML 格式），
使得公式在 Word 中可编辑、可渲染，而非显示为纯文本 LaTeX 代码。

流程: LaTeX 子集 → OMML → 插入 docx

依赖:
    pip install lxml python-docx

用法:
    # 单个公式替换
    python equations.py paper.docx ^
        --replace "EQ1" "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}" ^
        -o paper_final.docx

    # 批量替换（JSON 文件）
    python equations.py paper.docx --mapping equations.json -o paper_final.docx

    # 从 Markdown 生成 docx（含公式）
    python equations.py generate paper.md -o paper.docx --template template.docx

    # 将完整 LaTeX 论文转换为 docx
    python equations.py convert-latex main.tex -o paper.docx --template template.docx
"""

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

SKILL_ROOT = Path(__file__).resolve().parents[3]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import nsmap, qn
    from lxml import etree
except ImportError:
    print("错误: 请先安装依赖: pip install python-docx lxml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# OMML 命名空间
# ---------------------------------------------------------------------------
OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
OMML_PREFIX = "m"

# 注册命名空间前缀，保证序列化干净
ET.register_namespace(OMML_PREFIX, OMML_NS)

LATEX_SYMBOLS = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "varepsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "vartheta": "ϑ",
    "iota": "ι",
    "kappa": "κ",
    "lambda": "λ",
    "mu": "μ",
    "nu": "ν",
    "xi": "ξ",
    "omicron": "ο",
    "pi": "π",
    "varpi": "ϖ",
    "rho": "ρ",
    "varrho": "ϱ",
    "sigma": "σ",
    "tau": "τ",
    "upsilon": "υ",
    "phi": "φ",
    "varphi": "φ",
    "chi": "χ",
    "psi": "ψ",
    "omega": "ω",
    "Gamma": "Γ",
    "Delta": "Δ",
    "Theta": "Θ",
    "Lambda": "Λ",
    "Xi": "Ξ",
    "Pi": "Π",
    "Sigma": "Σ",
    "Upsilon": "Υ",
    "Phi": "Φ",
    "Psi": "Ψ",
    "Omega": "Ω",
    "sum": "∑",
    "prod": "∏",
    "int": "∫",
    "le": "≤",
    "leq": "≤",
    "ge": "≥",
    "geq": "≥",
    "neq": "≠",
    "ne": "≠",
    "approx": "≈",
    "infty": "∞",
    "times": "×",
    "cdot": "·",
    "pm": "±",
    "mp": "∓",
    "to": "→",
    "rightarrow": "→",
    "leftarrow": "←",
    "in": "∈",
    "notin": "∉",
    "subset": "⊂",
    "subseteq": "⊆",
    "cup": "∪",
    "cap": "∩",
    "ldots": "…",
    "cdots": "⋯",
    "dots": "…",
    "partial": "∂",
    "nabla": "∇",
    "hbar": "ℏ",
    "ell": "ℓ",
    "circ": "°",
    "degree": "°",
    "langle": "⟨",
    "rangle": "⟩",
    "Re": "Re",
    "Im": "Im",
    "forall": "∀",
    "exists": "∃",
    "propto": "∝",
    "sim": "∼",
    "simeq": "≃",
    "equiv": "≡",
    "cong": "≅",
    "ll": "≪",
    "gg": "≫",
    "perp": "⊥",
    "parallel": "∥",
    "min": "min",
    "max": "max",
    "argmin": "arg min",
    "argmax": "arg max",
    "lim": "lim",
    "log": "log",
    "ln": "ln",
    "exp": "exp",
    "sin": "sin",
    "cos": "cos",
    "tan": "tan",
    "cot": "cot",
    "sec": "sec",
    "csc": "csc",
    "arcsin": "arcsin",
    "arccos": "arccos",
    "arctan": "arctan",
    "sinh": "sinh",
    "cosh": "cosh",
    "tanh": "tanh",
}


def m_element(local_name, text=None):
    elem = etree.Element(f"{{{OMML_NS}}}{local_name}")
    if text is not None:
        elem.text = text
    return elem


def omml_run(text):
    run = m_element("r")
    text_elem = m_element("t", text)
    if text.startswith((" ", "\t")) or text.endswith((" ", "\t")):
        text_elem.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run.append(text_elem)
    return run


def append_group(parent, children):
    for child in children:
        parent.append(child)


def fraction_element(num_children, den_children):
    frac = m_element("f")
    num = m_element("num")
    den = m_element("den")
    append_group(num, num_children)
    append_group(den, den_children)
    frac.extend([num, den])
    return frac


def radical_element(children, degree_children=None):
    rad = m_element("rad")
    rad_pr = m_element("radPr")
    deg_hide = m_element("degHide")
    deg_hide.set(f"{{{OMML_NS}}}val", "0" if degree_children else "1")
    rad_pr.append(deg_hide)
    deg = m_element("deg")
    if degree_children:
        append_group(deg, degree_children)
    elem = m_element("e")
    append_group(elem, children)
    rad.extend([rad_pr, deg, elem])
    return rad


def matrix_element(rows, left="[", right="]"):
    """构造带定界符的 OMML 矩阵。"""
    matrix = m_element("m")
    for row_cells in rows:
        row = m_element("mr")
        for children in row_cells:
            cell = m_element("e")
            append_group(cell, children)
            row.append(cell)
        matrix.append(row)

    delimiter = m_element("d")
    delimiter_pr = m_element("dPr")
    beg = m_element("begChr")
    beg.set(f"{{{OMML_NS}}}val", left)
    end = m_element("endChr")
    end.set(f"{{{OMML_NS}}}val", right)
    delimiter_pr.extend([beg, end])
    content = m_element("e")
    content.append(matrix)
    delimiter.extend([delimiter_pr, content])
    return delimiter


def accent_element(children, accent):
    acc = m_element("acc")
    acc_pr = m_element("accPr")
    chr_elem = m_element("chr")
    chr_elem.set(f"{{{OMML_NS}}}val", accent)
    acc_pr.append(chr_elem)
    elem = m_element("e")
    append_group(elem, children)
    acc.extend([acc_pr, elem])
    return acc


def script_element(base_children, sub_children=None, sup_children=None):
    if sub_children and sup_children:
        node = m_element("sSubSup")
        base = m_element("e")
        sub = m_element("sub")
        sup = m_element("sup")
        append_group(base, base_children)
        append_group(sub, sub_children)
        append_group(sup, sup_children)
        node.extend([base, sub, sup])
        return node
    if sub_children:
        node = m_element("sSub")
        base = m_element("e")
        sub = m_element("sub")
        append_group(base, base_children)
        append_group(sub, sub_children)
        node.extend([base, sub])
        return node
    if sup_children:
        node = m_element("sSup")
        base = m_element("e")
        sup = m_element("sup")
        append_group(base, base_children)
        append_group(sup, sup_children)
        node.extend([base, sup])
        return node
    return base_children[0] if len(base_children) == 1 else omml_run("")


class LatexParser:
    def __init__(self, source: str):
        self.source = source.strip()
        self.index = 0

    def parse(self):
        nodes = self.parse_until()
        if self.index != len(self.source):
            raise ValueError("LaTeX 出现未匹配的右花括号 '}'")
        return nodes

    def parse_until(self, stop_char=None):
        nodes = []
        text_buffer = []

        def flush_text():
            if text_buffer:
                nodes.append(omml_run("".join(text_buffer)))
                text_buffer.clear()

        while self.index < len(self.source):
            char = self.source[self.index]
            if stop_char and char == stop_char:
                break
            if char == "\\":
                flush_text()
                nodes.extend(self.parse_command())
                continue
            if char in "_^":
                flush_text()
                if nodes:
                    base = [nodes.pop()]
                else:
                    base = [omml_run("")]
                sub = sup = None
                while self.index < len(self.source) and self.source[self.index] in "_^":
                    marker = self.source[self.index]
                    self.index += 1
                    group = self.parse_script_group()
                    if marker == "_":
                        sub = group
                    else:
                        sup = group
                nodes.append(script_element(base, sub, sup))
                continue
            if char == "{":
                self.index += 1
                flush_text()
                nodes.extend(self.parse_until("}"))
                if self.index >= len(self.source) or self.source[self.index] != "}":
                    raise ValueError("LaTeX 分组缺少右花括号 '}'")
                self.index += 1
                continue
            if char == "}":
                break

            text_buffer.append(char)
            self.index += 1

        flush_text()
        return nodes

    def parse_command(self):
        self.index += 1
        start = self.index
        while self.index < len(self.source) and self.source[self.index].isalpha():
            self.index += 1
        command = self.source[start:self.index]

        if not command and self.index < len(self.source):
            symbol = self.source[self.index]
            self.index += 1
            if symbol in ",;:":
                return [omml_run(" ")]
            if symbol == "!":
                return []
            if symbol in "{}_^":
                return [omml_run(symbol)]
            return [omml_run(symbol)]

        if command in {"left", "right", "limits", "displaystyle", "textstyle"}:
            return []
        if command in {"quad", "qquad"}:
            return [omml_run("  " if command == "quad" else "    ")]
        if command == "frac":
            return [fraction_element(self.parse_required_group(), self.parse_required_group())]
        if command == "sqrt":
            self.skip_spaces()
            degree = None
            if self.index < len(self.source) and self.source[self.index] == "[":
                end = self.source.find("]", self.index + 1)
                if end < 0:
                    raise ValueError("根式次数缺少右方括号 ']'")
                degree = LatexParser(self.source[self.index + 1:end]).parse()
                self.index = end + 1
            return [radical_element(self.parse_required_group(), degree)]
        if command == "begin":
            environment = self.group_text()
            if environment not in {"matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "aligned", "cases"}:
                raise ValueError(f"不支持的 LaTeX 环境: {environment}")
            return [self.parse_matrix(environment)]
        accents = {
            "hat": "\u0302",
            "bar": "\u0305",
            "overline": "\u0305",
            "vec": "⃗",
            "dot": "\u0307",
            "ddot": "\u0308",
            "tilde": "\u0303",
        }
        if command in accents:
            return [accent_element(self.parse_required_group(), accents[command])]
        if command == "tag":
            return [omml_run(f"({self.group_text()})")]
        if command == "text":
            return [omml_run(self.group_text())]
        if command == "operatorname":
            return [omml_run(self.group_text())]
        if command in {"mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathbb"}:
            return self.parse_required_group()

        if command in LATEX_SYMBOLS:
            return [omml_run(LATEX_SYMBOLS[command])]
        raise ValueError(f"不支持的 LaTeX 命令: \\{command}")

    def parse_matrix(self, environment):
        end_token = f"\\end{{{environment}}}"
        end = self.source.find(end_token, self.index)
        if end < 0:
            raise ValueError(f"矩阵环境 {environment} 缺少结束标记")
        body = self.source[self.index:end]
        self.index = end + len(end_token)
        rows = []
        for row_text in re.split(r"\\\\", body):
            if not row_text.strip():
                continue
            rows.append([
                LatexParser(cell.strip()).parse()
                for cell in row_text.split("&")
            ])
        if not rows or len({len(row) for row in rows}) != 1:
            raise ValueError("矩阵必须为非空且每行列数一致")
        delimiters = {
            "matrix": ("", ""),
            "pmatrix": ("(", ")"),
            "bmatrix": ("[", "]"),
            "Bmatrix": ("{", "}"),
            "vmatrix": ("|", "|"),
            "Vmatrix": ("‖", "‖"),
            "aligned": ("", ""),
            "cases": ("{", ""),
        }
        return matrix_element(rows, *delimiters[environment])

    def parse_required_group(self):
        self.skip_spaces()
        if self.index < len(self.source) and self.source[self.index] == "{":
            self.index += 1
            children = self.parse_until("}")
            if self.index >= len(self.source) or self.source[self.index] != "}":
                raise ValueError("LaTeX 分组缺少右花括号 '}'")
            self.index += 1
            return children
        if self.index < len(self.source):
            char = self.source[self.index]
            if char == "\\":
                return self.parse_command()
            self.index += 1
            return [omml_run(char)]
        raise ValueError("LaTeX 命令缺少必需参数")

    def parse_script_group(self):
        return self.parse_required_group()

    def group_text(self):
        self.skip_spaces()
        if self.index >= len(self.source) or self.source[self.index] != "{":
            raise ValueError("LaTeX 命令缺少花括号参数")
        self.index += 1
        depth = 1
        start = self.index
        while self.index < len(self.source) and depth:
            if self.source[self.index] == "{":
                depth += 1
            elif self.source[self.index] == "}":
                depth -= 1
            self.index += 1
        if depth:
            raise ValueError("LaTeX 分组缺少右花括号 '}'")
        return self.source[start : self.index - 1]

    def skip_spaces(self):
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1

# ---------------------------------------------------------------------------
# 核心：LaTeX → OMML
# ---------------------------------------------------------------------------

def latex2omml(latex_str: str) -> bytes:
    """
    将 LaTeX 字符串转换为 Word OMML XML（即 <m:oMath> 元素内的 XML 字符串）。
    支持数学建模论文常用 LaTeX 子集：分式、根号、上下标、希腊字母、
    求和/积分符号、比较符号和普通文本。
    """
    omml = etree.Element(f"{{{OMML_NS}}}oMath")
    for child in LatexParser(latex_str).parse():
        omml.append(child)
    return etree.tostring(omml, encoding="unicode").encode("utf-8")


def latex2omml_direct(latex_str: str) -> str:
    """仅返回 OMML 字符串（调试用）。"""
    return latex2omml(latex_str).decode("utf-8")


# ---------------------------------------------------------------------------
# docx 操作：插入 OMML 方程
# ---------------------------------------------------------------------------

def iter_paragraphs(container, seen_cells=None):
    """遍历正文及嵌套表格单元格中的段落。"""
    seen_cells = seen_cells if seen_cells is not None else set()
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                key = id(cell._tc)
                if key in seen_cells:
                    continue
                seen_cells.add(key)
                yield from iter_paragraphs(cell, seen_cells)


def find_paragraph_with_text(doc: Document, text: str) -> object:
    """
    在文档中查找包含指定文本的第一个段落。
    返回 docx Paragraph 对象，或 None。
    """
    for para in iter_paragraphs(doc):
        if text in para.text:
            return para
    return None


def replace_with_equation(para, omml_xml: bytes):
    """
    将段落中所有文本替换为 OMML 公式元素。

    原段落的内容会被清空，然后插入 <m:oMathPara> 包含 <m:oMath>。
    """
    # 清空段落的所有 run
    for r in para._element.findall(qn("w:r")):
        para._element.remove(r)
    for r in para._element.findall(qn("w:rPr")):
        para._element.remove(r)

    # 创建 <m:oMathPara> 包装器
    math_para = OxmlElement("m:oMathPara")
    math_para.append(_build_math_element(omml_xml))
    para._element.append(math_para)


def _build_math_element(omml_xml: bytes):
    """Build a Word math element from the converter output."""
    omml_elem = etree.fromstring(omml_xml)

    math_elem = OxmlElement("m:oMath")
    for child in omml_elem:
        math_elem.append(child)
    return math_elem


def _build_text_run(text: str, source_run=None):
    """Create a Word run, preserving source run properties when possible."""
    run = OxmlElement("w:r")
    if source_run is not None:
        r_pr = source_run.find(qn("w:rPr"))
        if r_pr is not None:
            run.append(copy.deepcopy(r_pr))

    text_elem = OxmlElement("w:t")
    if text.startswith((" ", "\t")) or text.endswith((" ", "\t")):
        text_elem.set(qn("xml:space"), "preserve")
    text_elem.text = text
    run.append(text_elem)
    return run


def replace_inline_placeholder(para, placeholder: str, omml_xml: bytes) -> bool:
    """
    Replace one placeholder inside a paragraph without discarding surrounding text.

    The common docx-js path emits placeholders as a single TextRun. If a Word
    editor splits the placeholder across runs, fall back to rebuilding the
    paragraph text so content is preserved, though original run styling may be
    simplified.
    """
    for run in para._element.findall(qn("w:r")):
        texts = run.findall(qn("w:t"))
        if len(texts) != 1 or not texts[0].text or placeholder not in texts[0].text:
            continue

        before, after = texts[0].text.split(placeholder, 1)
        parent = para._element
        insert_at = parent.index(run)
        parent.remove(run)

        if before:
            parent.insert(insert_at, _build_text_run(before, run))
            insert_at += 1
        parent.insert(insert_at, _build_math_element(omml_xml))
        insert_at += 1
        if after:
            parent.insert(insert_at, _build_text_run(after, run))
        return True

    full_text = para.text
    if placeholder not in full_text:
        return False

    before, after = full_text.split(placeholder, 1)
    for child in list(para._element):
        if child.tag in {qn("w:r"), qn("m:oMath"), qn("m:oMathPara")}:
            para._element.remove(child)

    if before:
        para._element.append(_build_text_run(before))
    para._element.append(_build_math_element(omml_xml))
    if after:
        para._element.append(_build_text_run(after))
    return True


def replace_placeholder(doc: Document, placeholder: str, latex: str):
    """
    查找占位符文本并替换为公式。
    """
    paragraphs = [para for para in iter_paragraphs(doc) if placeholder in para.text]
    if not paragraphs:
        print(f"  ! 未找到占位符 '{placeholder}'，跳过")
        return 0

    omml_xml = latex2omml(latex)
    replaced = 0
    for para in paragraphs:
        if para.text.strip() == placeholder:
            replace_with_equation(para, omml_xml)
            replaced += 1
            continue
        while placeholder in para.text and replace_inline_placeholder(para, placeholder, omml_xml):
            replaced += 1
    print(f"  OK '{placeholder}' -> 已插入 {replaced} 处公式")
    return replaced


def batch_replace(doc_path: str, mapping: dict, output_path: str):
    """
    批量替换占位符为公式。

    mapping = {
        "占位符文本": "LaTeX 公式",
        "EQ_MODEL": "\\min f(x) = \\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2",
        ...
    }
    """
    doc = Document(doc_path)

    success = 0
    for placeholder, latex in mapping.items():
        if replace_placeholder(doc, placeholder, latex):
            success += 1

    doc.save(output_path)
    print(f"\n完成: {success}/{len(mapping)} 个公式已插入 -> {output_path}")
    return success


# ---------------------------------------------------------------------------
# 使用 Pandoc 生成 docx
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _conversion_manifest_path(output: Path) -> Path:
    return output.with_suffix(".conversion.json")


def _replace_conversion_pair(
    source: Path,
    target: Path,
    manifest_payload: dict,
    *,
    overwrite: bool,
) -> Path:
    manifest = _conversion_manifest_path(target)
    if not overwrite and (target.exists() or manifest.exists()):
        raise FileExistsError(f"输出已存在，拒绝覆盖：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staged_target = target.parent / f".{target.name}.new-{token}"
    staged_manifest = target.parent / f".{manifest.name}.new-{token}"
    backups = {
        target: target.parent / f".{target.name}.bak-{token}",
        manifest: target.parent / f".{manifest.name}.bak-{token}",
    }
    moved = set()
    installed = set()
    try:
        shutil.copyfile(source, staged_target)
        staged_manifest.write_text(
            json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for current, backup in backups.items():
            if current.exists():
                os.replace(current, backup)
                moved.add(current)
        os.replace(staged_target, target)
        installed.add(target)
        os.replace(staged_manifest, manifest)
        installed.add(manifest)
    except Exception:
        for current in installed:
            if current.exists():
                current.unlink()
        for current in moved:
            backup = backups[current]
            if backup.exists():
                os.replace(backup, current)
        raise
    finally:
        for path in (staged_target, staged_manifest, *backups.values()):
            if path.exists():
                path.unlink()
    return manifest


def _latex_root(source: Path) -> Path:
    for root in (source.parent, *source.parents):
        manifest_path = root / "latex-project.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            configured = (root / manifest["main_tex"]).resolve()
        except (KeyError, OSError, json.JSONDecodeError) as error:
            raise ValueError(f"LaTeX 项目清单无效：{error}") from error
        if configured != source:
            raise ValueError("转换入口与 latex-project.json 记录不一致")
        return root
    return source.parent


LITERAL_RE = re.compile(
    r"\\begin\s*\{(?P<env>verbatim\*?|lstlisting|minted|comment)\}.*?"
    r"\\end\s*\{(?P=env)\}|"
    r"\\verb\*?(?P<delimiter>[^\w\s]).*?(?P=delimiter)",
    re.S,
)
INPUT_RE = re.compile(
    r"\\(input|include)(?![A-Za-z@])\s*(?:\{([^}]+)\}|([^\s%]+))"
)


def _replace_visible_inputs(text: str, expand) -> str:
    def visible(segment: str) -> str:
        lines = []
        for line in segment.splitlines(keepends=True):
            comment_at = None
            for index, character in enumerate(line):
                if character != "%":
                    continue
                backslashes = 0
                cursor = index - 1
                while cursor >= 0 and line[cursor] == "\\":
                    backslashes += 1
                    cursor -= 1
                if backslashes % 2 == 0:
                    comment_at = index
                    break
            if comment_at is None:
                lines.append(INPUT_RE.sub(expand, line))
            else:
                lines.append(
                    INPUT_RE.sub(expand, line[:comment_at]) + line[comment_at:]
                )
        return "".join(lines)

    result = []
    cursor = 0
    for match in LITERAL_RE.finditer(text):
        result.append(visible(text[cursor:match.start()]))
        result.append(match.group(0))
        cursor = match.end()
    result.append(visible(text[cursor:]))
    return "".join(result)


def _expand_latex_inputs(source: Path) -> tuple[str, Path, list[Path]]:
    root = _latex_root(source)
    seen = set()
    stack = set()
    files = []

    def load(path: Path) -> str:
        current = path.resolve()
        if current != root and root not in current.parents:
            raise ValueError(f"LaTeX 子文件超出项目目录：{path}")
        if current in stack:
            raise ValueError(f"LaTeX 子文件循环包含：{current.relative_to(root)}")
        if not current.is_file():
            raise FileNotFoundError(
                f"LaTeX 子文件不存在：{current.relative_to(root)}"
            )
        if current not in seen:
            seen.add(current)
            files.append(current)
        stack.add(current)
        text = current.read_text(encoding="utf-8")

        def expand(match):
            raw = Path((match.group(2) or match.group(3)).strip())
            if not raw.suffix:
                raw = raw.with_suffix(".tex")
            content = load(root / raw)
            return f"\n\\clearpage\n{content}\n" if match.group(1) == "include" else content

        expanded = _replace_visible_inputs(text, expand)
        stack.remove(current)
        return expanded

    return load(source), root, files


def _source_bundle_sha256(files: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _project_bundle(root: Path, excluded: set[Path]) -> tuple[str, list[Path]]:
    generated_suffixes = {
        ".aux", ".log", ".out", ".toc", ".bbl", ".blg", ".bcf", ".fls",
        ".fdb_latexmk", ".synctex.gz", ".run.xml", ".xdv", ".dvi",
    }
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.resolve() in excluded or path.relative_to(root).parts[0] == "build":
            continue
        suffix = path.suffix.casefold()
        compound = "".join(path.suffixes[-2:]).casefold()
        if suffix in generated_suffixes or compound in generated_suffixes:
            continue
        if path.name.endswith((".build.json", ".conversion.json")):
            continue
        files.append(path)
    return _source_bundle_sha256(files, root), files


def _tool_version(executable: str) -> str | None:
    try:
        process = subprocess.Popen(
            [executable, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output, _ = process.communicate(timeout=10)
    except (OSError, subprocess.SubprocessError):
        if "process" in locals():
            process.kill()
        return None
    return output.splitlines()[0].strip() if process.returncode == 0 and output else None


def _gate_warnings(warnings, allow_warnings, override_reason):
    patterns = list(allow_warnings or [])
    if patterns and (not override_reason or not override_reason.strip()):
        raise ValueError("允许 Pandoc 警告必须提供 override_reason")
    try:
        compiled = [re.compile(pattern, re.I) for pattern in patterns]
    except re.error as error:
        raise ValueError(f"无效的警告允许正则：{error}") from error
    allowed, blocked = [], []
    for warning in warnings:
        (allowed if any(pattern.search(warning) for pattern in compiled) else blocked).append(
            warning
        )
    return allowed, blocked


def _pandoc_to_docx(
    source_path,
    output_path,
    source_format,
    template_path=None,
    *,
    timeout=120,
    allow_warnings=None,
    override_reason=None,
    overwrite=False,
):
    source = Path(source_path).resolve()
    output = Path(output_path).resolve()
    expected_suffix = ".tex" if source_format == "latex" else ".md"
    if not source.is_file() or source.suffix.casefold() != expected_suffix:
        raise FileNotFoundError(f"输入文件不存在或不是 {expected_suffix}：{source}")
    if output.suffix.casefold() != ".docx":
        raise ValueError("输出文件必须使用 .docx 扩展名")
    if output == SKILL_ROOT or SKILL_ROOT in output.parents:
        raise ValueError("拒绝向 SKILL_ROOT 写入 DOCX")
    if timeout <= 0:
        raise ValueError("timeout 必须为正整数")
    manifest_path = _conversion_manifest_path(output)
    if not overwrite and (output.exists() or manifest_path.exists()):
        raise FileExistsError(f"输出已存在，拒绝覆盖：{output}")

    template = Path(template_path).resolve() if template_path else None
    if template is not None and (
        not template.is_file() or template.suffix.casefold() != ".docx"
    ):
        raise FileNotFoundError(f"DOCX 参考模板不存在：{template}")
    executable = shutil.which("pandoc")
    if executable is None:
        raise RuntimeError("未找到 pandoc，无法转换为 DOCX")

    output.parent.mkdir(parents=True, exist_ok=True)
    flattened = None
    source_for_pandoc = source
    if source_format == "latex":
        expanded, resource_root, source_files = _expand_latex_inputs(source)
        project_hash, project_files = _project_bundle(
            resource_root, {output, manifest_path}
        )
        with tempfile.NamedTemporaryFile(
            "w",
            dir=output.parent,
            suffix=".tex",
            delete=False,
            encoding="utf-8",
        ) as handle:
            handle.write(expanded)
            flattened = Path(handle.name)
        source_for_pandoc = flattened
        source_hash = _source_bundle_sha256(source_files, resource_root)
    else:
        resource_root = source.parent
        source_files = [source]
        source_hash = _sha256(source)
        project_hash = source_hash
        project_files = source_files
    with tempfile.NamedTemporaryFile(
        dir=output.parent, suffix=".docx", delete=False
    ) as handle:
        temporary = Path(handle.name)
    command = [
        executable,
        "--from",
        source_format,
        "--to",
        "docx",
        "--standalone",
        "--citeproc",
        str(source_for_pandoc),
        "--output",
        str(temporary),
        f"--resource-path={resource_root}",
    ]
    if template is not None:
        command.extend(["--reference-doc", str(template)])
    reproduce = [
        sys.executable,
        str(Path(__file__).resolve()),
        "convert-latex" if source_format == "latex" else "generate",
        str(source),
        "--output",
        str(output),
    ]
    if template is not None:
        reproduce.extend(["--template", str(template)])
    reproduce.extend(["--timeout", str(timeout)])
    for pattern in allow_warnings or []:
        reproduce.extend(["--allow-warning", pattern])
    if override_reason:
        reproduce.extend(["--override-reason", override_reason.strip()])
    if overwrite:
        reproduce.append("--overwrite")
    warnings = []
    allowed_warnings = []
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=resource_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[-2000:]
            raise RuntimeError(f"Pandoc 转换失败：{detail or completed.returncode}")
        warnings = [
            line.strip() for line in completed.stderr.splitlines() if line.strip()
        ]
        allowed_warnings, blocked_warnings = _gate_warnings(
            warnings, allow_warnings, override_reason
        )
        if blocked_warnings:
            raise RuntimeError(
                "Pandoc 存在未获批准的警告，拒绝发布 DOCX："
                + "；".join(blocked_warnings)
            )
        Document(temporary)
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_format": source_format,
            "source": str(source),
            "source_files": [
                path.relative_to(resource_root).as_posix() for path in source_files
            ],
            "source_sha256": source_hash,
            "project_files": [
                path.relative_to(resource_root).as_posix() for path in project_files
            ],
            "project_sha256": project_hash,
            "output": str(output),
            "output_sha256": _sha256(temporary),
            "template": str(template) if template else None,
            "template_sha256": _sha256(template) if template else None,
            "pandoc": {
                "path": executable,
                "version": _tool_version(executable),
            },
            "command": command,
            "returncode": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "warnings": warnings,
            "allowed_warnings": allowed_warnings,
            "warning_override": {
                "patterns": list(allow_warnings or []),
                "reason": override_reason.strip() if override_reason else None,
            },
            "reproduce": subprocess.list2cmdline(reproduce),
        }
        manifest_path = _replace_conversion_pair(
            temporary, output, manifest, overwrite=overwrite
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Pandoc 转换超过 {timeout} 秒") from error
    finally:
        if temporary.exists():
            temporary.unlink()
        if flattened is not None and flattened.exists():
            flattened.unlink()
    return {
        "output_path": str(output),
        "manifest": str(manifest_path),
        "warnings": warnings,
        "allowed_warnings": allowed_warnings,
    }


def markdown_to_docx(
    md_path: str,
    output_path: str,
    template_path: str = None,
    **options,
):
    """将含 LaTeX 公式的 Markdown 转换为 DOCX。"""
    return _pandoc_to_docx(
        md_path, output_path, "markdown", template_path, **options
    )


def latex_to_docx(
    tex_path: str,
    output_path: str,
    template_path: str = None,
    **options,
):
    """将完整 LaTeX 文档转换为 DOCX，公式由 Pandoc 写为原生 OMML。"""
    return _pandoc_to_docx(
        tex_path, output_path, "latex", template_path, **options
    )


def verify_conversion(output_path, manifest_path=None):
    """重新计算输入、模板和 DOCX 哈希，验证转换交付物仍与清单一致。"""
    output = Path(output_path).resolve()
    manifest_file = (
        Path(manifest_path).resolve()
        if manifest_path
        else _conversion_manifest_path(output)
    )
    issues = []
    if not output.is_file() or output.suffix.casefold() != ".docx":
        issues.append(f"DOCX 输出不存在：{output}")
    if not manifest_file.is_file():
        issues.append(f"转换清单不存在：{manifest_file}")
        return {
            "output_path": str(output),
            "manifest": str(manifest_file),
            "issues": issues,
            "passed": False,
        }
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        issues.append(f"转换清单无效：{error}")
        manifest = {}
    if not isinstance(manifest, dict):
        issues.append("转换清单根节点必须是 JSON 对象")
        manifest = {}
    required_fields = {
        "schema_version",
        "created_at",
        "source_format",
        "source",
        "source_files",
        "source_sha256",
        "project_files",
        "project_sha256",
        "output",
        "output_sha256",
        "template",
        "template_sha256",
        "pandoc",
        "command",
        "returncode",
        "duration_seconds",
        "warnings",
        "allowed_warnings",
        "warning_override",
        "reproduce",
    }
    missing_fields = sorted(required_fields - manifest.keys())
    if missing_fields:
        issues.append("转换清单缺少必填字段：" + "、".join(missing_fields))
    string_fields = {
        "created_at",
        "source_format",
        "source",
        "output",
        "reproduce",
    }
    for field in sorted(string_fields & manifest.keys()):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            issues.append(f"转换清单字段 {field} 必须是非空字符串")
    list_fields = {
        "source_files",
        "project_files",
        "command",
        "warnings",
        "allowed_warnings",
    }
    for field in sorted(list_fields & manifest.keys()):
        value = manifest[field]
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            issues.append(f"转换清单字段 {field} 必须是字符串数组")
        elif field in {"source_files", "project_files", "command"} and not value:
            issues.append(f"转换清单字段 {field} 不得为空")
    hash_fields = {
        "source_sha256",
        "project_sha256",
        "output_sha256",
    }
    if manifest.get("template") is not None:
        hash_fields.add("template_sha256")
    for field in sorted(hash_fields & manifest.keys()):
        if not re.fullmatch(r"[0-9a-f]{64}", str(manifest[field])):
            issues.append(f"转换清单字段 {field} 不是有效的 SHA-256")
    template_value = manifest.get("template")
    template_hash = manifest.get("template_sha256")
    if template_value is not None and (
        not isinstance(template_value, str) or not template_value.strip()
    ):
        issues.append("转换清单字段 template 必须是 null 或非空字符串")
    if (template_value is None) != (template_hash is None):
        issues.append("转换清单的 template 与 template_sha256 必须成对记录")
    pandoc = manifest.get("pandoc")
    if "pandoc" in manifest:
        if not isinstance(pandoc, dict):
            issues.append("转换清单字段 pandoc 必须是对象")
        elif (
            not isinstance(pandoc.get("path"), str)
            or not pandoc["path"].strip()
            or not (
                pandoc.get("version") is None
                or isinstance(pandoc.get("version"), str)
            )
        ):
            issues.append("转换清单字段 pandoc.path/version 类型无效")
    warning_override = manifest.get("warning_override")
    if "warning_override" in manifest:
        if not isinstance(warning_override, dict):
            issues.append("转换清单字段 warning_override 必须是对象")
        else:
            patterns = warning_override.get("patterns")
            reason = warning_override.get("reason")
            if not isinstance(patterns, list) or not all(
                isinstance(item, str) for item in patterns
            ):
                issues.append(
                    "转换清单字段 warning_override.patterns 必须是字符串数组"
                )
            if reason is not None and (
                not isinstance(reason, str) or not reason.strip()
            ):
                issues.append(
                    "转换清单字段 warning_override.reason 必须是 null 或非空字符串"
                )
    if type(manifest.get("schema_version")) is not int or manifest.get(
        "schema_version"
    ) != 1:
        issues.append("转换清单 schema_version 不受支持")
    if type(manifest.get("returncode")) is not int:
        issues.append("转换清单字段 returncode 必须是整数")
    elif manifest["returncode"] != 0:
        issues.append("转换清单记录的 Pandoc 返回码不是 0")
    duration = manifest.get("duration_seconds")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration < 0
    ):
        issues.append("转换清单字段 duration_seconds 必须是非负数")
    created_at = manifest.get("created_at")
    if isinstance(created_at, str) and created_at.strip():
        try:
            datetime.fromisoformat(created_at)
        except ValueError:
            issues.append("转换清单字段 created_at 不是有效的 ISO 8601 时间")
    output_value = manifest.get("output")
    if isinstance(output_value, str) and output_value.strip() and Path(
        output_value
    ).resolve() != output:
        issues.append("转换清单记录的 DOCX 路径与当前文件不一致")
    if output.is_file():
        if manifest.get("output_sha256") != _sha256(output):
            issues.append("DOCX 哈希与转换清单不一致")
        try:
            Document(output)
        except Exception as error:
            issues.append(f"DOCX 结构无法读取：{error}")

    source_value = manifest.get("source")
    source_format = manifest.get("source_format")
    source = (
        Path(source_value).resolve()
        if isinstance(source_value, str) and source_value
        else None
    )
    if source is None:
        pass
    elif not source.is_file():
        issues.append(f"转换源文件不存在：{source_value}")
    elif source_format == "latex":
        try:
            _, root, source_files = _expand_latex_inputs(source)
            source_hash = _source_bundle_sha256(source_files, root)
            project_hash, project_files = _project_bundle(
                root, {output, manifest_file}
            )
            if manifest.get("source_sha256") != source_hash:
                issues.append("LaTeX 源文件哈希与转换清单不一致")
            if manifest.get("project_sha256") != project_hash:
                issues.append("LaTeX 项目哈希与转换清单不一致")
            current_sources = [
                path.relative_to(root).as_posix() for path in source_files
            ]
            current_project = [
                path.relative_to(root).as_posix() for path in project_files
            ]
            if manifest.get("source_files") != current_sources:
                issues.append("LaTeX 子文件列表与转换清单不一致")
            if manifest.get("project_files") != current_project:
                issues.append("LaTeX 项目文件列表与转换清单不一致")
        except (OSError, RuntimeError, ValueError) as error:
            issues.append(f"LaTeX 输入复验失败：{error}")
    elif source_format == "markdown":
        if source is not None and source.is_file():
            source_hash = _sha256(source)
            if manifest.get("source_sha256") != source_hash:
                issues.append("Markdown 源文件哈希与转换清单不一致")
            if manifest.get("project_sha256") != source_hash:
                issues.append("Markdown 项目哈希与转换清单不一致")
    else:
        issues.append(f"未知的转换源格式：{source_format}")

    if isinstance(template_value, str) and template_value:
        template = Path(template_value).resolve()
        if not template.is_file():
            issues.append(f"DOCX 参考模板不存在：{template}")
        elif template_hash != _sha256(template):
            issues.append("DOCX 参考模板哈希与转换清单不一致")
    return {
        "output_path": str(output),
        "manifest": str(manifest_file),
        "issues": list(dict.fromkeys(issues)),
        "passed": not issues,
    }


# ---------------------------------------------------------------------------
# 命令行
# ---------------------------------------------------------------------------

def load_mapping(file_path: str) -> dict:
    """从 JSON 文件加载占位符→LaTeX 映射。"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {item["placeholder"]: item["latex"] for item in data}
    raise ValueError("JSON 格式错误，应为 dict 或 [{placeholder, latex}, ...]")


def build_parser():
    parser = argparse.ArgumentParser(
        description="LaTeX 方程转 Word OMML 公式工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", help="运行模式")

    # ---- 模式 1: replace（替换 docx 中的占位符） ----
    rp = sub.add_parser("replace", help="替换 .docx 中的占位符为公式")
    rp.add_argument("input", help="输入 .docx 文件路径")
    rp.add_argument("--mapping", "-m", help="JSON 映射文件 ({\"占位符\": \"LaTeX\", ...})")
    rp.add_argument("--replace", "-r", nargs=2, action="append",
                    metavar=("PLACEHOLDER", "LATEX"),
                    help="单个替换对，可重复使用")
    rp.add_argument("--output", "-o", default=None,
                    help="输出 .docx 路径（默认覆盖输入文件）")
    rp.add_argument("--show-omml", action="store_true",
                    help="仅显示 LaTeX 转 OMML 转换结果，不操作 docx")

    # ---- 模式 2: generate（从 Markdown 生成） ----
    gn = sub.add_parser("generate", help="从 Markdown 生成含公式的 .docx")
    gn.add_argument("input", help="输入 .md 文件路径（使用 $$...$$ 或 $...$ 写公式）")
    gn.add_argument("--output", "-o", required=True, help="输出 .docx 路径")
    gn.add_argument("--template", "-t", help="pandoc 参考模板 .docx")
    gn.add_argument("--timeout", type=int, default=120, help="转换超时秒数")
    gn.add_argument("--allow-warning", action="append", default=[],
                    help="允许的 Pandoc 警告正则，可重复使用")
    gn.add_argument("--override-reason", help="允许警告的具体理由")
    gn.add_argument("--overwrite", action="store_true", help="覆盖已有转换产物")

    # ---- 模式 3: convert-latex（从完整 LaTeX 文档生成） ----
    cv = sub.add_parser("convert-latex", help="将完整 LaTeX 文档转换为 .docx")
    cv.add_argument("input", help="LaTeX 主入口 .tex 文件")
    cv.add_argument("--output", "-o", required=True, help="输出 .docx 路径")
    cv.add_argument("--template", "-t", help="pandoc 参考模板 .docx")
    cv.add_argument("--timeout", type=int, default=120, help="转换超时秒数")
    cv.add_argument("--allow-warning", action="append", default=[],
                    help="允许的 Pandoc 警告正则，可重复使用")
    cv.add_argument("--override-reason", help="允许警告的具体理由")
    cv.add_argument("--overwrite", action="store_true", help="覆盖已有转换产物")

    vf = sub.add_parser("verify-conversion", help="复验 DOCX 与转换清单的全部哈希")
    vf.add_argument("input", help="待复验的 .docx 文件")
    vf.add_argument("--manifest", help="转换清单路径，默认使用同名 .conversion.json")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "replace":
        # 收集替换映射
        mapping = {}
        if args.mapping:
            mapping.update(load_mapping(args.mapping))
        if args.replace:
            for placeholder, latex in args.replace:
                mapping[placeholder] = latex

        if not mapping:
            print("错误: 请提供 --mapping 或 --replace", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

        if args.show_omml:
            print("LaTeX -> OMML 预览:")
            print("=" * 60)
            for placeholder, latex in mapping.items():
                print(f"\n占位符: {placeholder}")
                print(f"LaTeX:   {latex}")
                try:
                    omml = latex2omml_direct(latex)
                    print(f"OMML: {omml}")
                except Exception as e:
                    print(f"错误: {e}")
            return

        output = args.output or args.input
        batch_replace(args.input, mapping, output)

    elif args.mode == "generate":
        try:
            result = markdown_to_docx(
                args.input, args.output,
                template_path=args.template,
                timeout=args.timeout,
                allow_warnings=args.allow_warning,
                override_reason=args.override_reason,
                overwrite=args.overwrite,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"错误：{error}", file=sys.stderr)
            sys.exit(1)
        print(f"已生成：{result['output_path']}")
        for warning in result["warnings"]:
            print(f"Pandoc 警告：{warning}", file=sys.stderr)

    elif args.mode == "convert-latex":
        try:
            result = latex_to_docx(
                args.input, args.output,
                template_path=args.template,
                timeout=args.timeout,
                allow_warnings=args.allow_warning,
                override_reason=args.override_reason,
                overwrite=args.overwrite,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"错误：{error}", file=sys.stderr)
            sys.exit(1)
        print(f"已生成：{result['output_path']}")
        for warning in result["warnings"]:
            print(f"Pandoc 警告：{warning}", file=sys.stderr)

    elif args.mode == "verify-conversion":
        result = verify_conversion(args.input, args.manifest)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["passed"]:
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
