#!/usr/bin/env python3
"""Extract a compact formatting profile from a DOCX template."""

import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W_NS, "a": A_NS}


def xpath_string(element, expression):
    if element is None:
        return ""
    return element.xpath(f"string({expression})", namespaces=NS)


def half_points_to_points(value):
    if not value:
        return ""
    return f"{int(value) / 2:g}pt"


def line_to_multiple(value, rule):
    if not value:
        return ""
    if rule == "auto":
        return f"{int(value) / 240:g}"
    return value


def text_of(paragraph):
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=NS)).strip()


def paragraph_profile(paragraph):
    p_pr = paragraph.find("w:pPr", NS)
    runs = []
    for run in paragraph.findall("w:r", NS):
        text = "".join(run.xpath(".//w:t/text()", namespaces=NS)).strip()
        if not text:
            continue
        r_pr = run.find("w:rPr", NS)
        size = xpath_string(r_pr, "w:sz/@w:val")
        runs.append(
            {
                "text": text[:40],
                "fontEastAsia": xpath_string(r_pr, "w:rFonts/@w:eastAsia")
                or xpath_string(r_pr, "w:rFonts/@w:eastAsiaTheme"),
                "fontAscii": xpath_string(r_pr, "w:rFonts/@w:ascii")
                or xpath_string(r_pr, "w:rFonts/@w:asciiTheme"),
                "size": half_points_to_points(size),
                "bold": r_pr.find("w:b", NS) is not None if r_pr is not None else False,
            }
        )

    line = xpath_string(p_pr, "w:spacing/@w:line")
    line_rule = xpath_string(p_pr, "w:spacing/@w:lineRule")
    return {
        "text": text_of(paragraph),
        "alignment": xpath_string(p_pr, "w:jc/@w:val"),
        "firstLineDxa": xpath_string(p_pr, "w:ind/@w:firstLine"),
        "firstLineChars": xpath_string(p_pr, "w:ind/@w:firstLineChars"),
        "line": line,
        "lineRule": line_rule,
        "lineMultiple": line_to_multiple(line, line_rule),
        "runs": runs,
    }


def extract_theme_fonts(zip_file):
    theme_names = [
        name
        for name in zip_file.namelist()
        if name.startswith("word/theme/") and name.endswith(".xml")
    ]
    if not theme_names:
        return {}

    root = etree.fromstring(zip_file.read(theme_names[0]))
    result = {}
    for label in ("majorFont", "minorFont"):
        node = root.find(f".//a:{label}", NS)
        if node is None:
            continue
        latin = xpath_string(node, "a:latin/@typeface")
        hans = ""
        for font in node.findall("a:font", NS):
            if font.get("script") == "Hans":
                hans = font.get("typeface", "")
                break
        result[label] = {"latin": latin, "hans": hans}
    return result


def extract_table_profiles(root):
    tables = []
    for table in root.xpath("//w:tbl", namespaces=NS):
        tbl_pr = table.find("w:tblPr", NS)
        borders = {}
        border_node = table.find("w:tblPr/w:tblBorders", NS)
        if border_node is not None:
            for child in border_node:
                borders[child.tag.rsplit("}", 1)[1]] = {
                    "val": child.get(f"{{{W_NS}}}val", ""),
                    "size": child.get(f"{{{W_NS}}}sz", ""),
                }

        rows = []
        for row in table.xpath("./w:tr", namespaces=NS):
            cells = []
            for cell in row.xpath("./w:tc", namespaces=NS):
                cells.append("".join(cell.xpath(".//w:t/text()", namespaces=NS)).strip())
            rows.append(cells)

        tables.append(
            {
                "alignment": xpath_string(tbl_pr, "w:jc/@w:val"),
                "style": xpath_string(tbl_pr, "w:tblStyle/@w:val"),
                "borders": borders,
                "rows": rows,
            }
        )
    return tables


def infer_roles(paragraphs):
    samples = {}
    for profile in paragraphs:
        text = profile["text"]
        if not text:
            continue
        first_run = profile["runs"][0] if profile["runs"] else {}
        size = first_run.get("size", "")
        bold = first_run.get("bold", False)
        align = profile["alignment"]
        first_line_chars = profile["firstLineChars"]

        if text == "论文题目":
            samples["paperTitle"] = profile
        elif text == "摘 要":
            samples["abstractTitle"] = profile
        elif text.startswith("关键词"):
            samples["keywords"] = profile
        elif first_line_chars == "200" and size == "12pt":
            samples.setdefault("bodyParagraph", profile)
        elif align == "center" and size == "16pt" and bold:
            samples.setdefault("level1Heading", profile)
        elif size == "12pt" and not bold and align == "":
            samples.setdefault("level2Heading", profile)
        elif (
            size == "12pt"
            and align == "both"
            and any(keyword in text for keyword in ("建立", "求解", "优点", "缺点", "改进"))
        ):
            samples.setdefault("level3ModelHeading", profile)
    return samples


def extract_profile(template_path):
    with zipfile.ZipFile(template_path) as docx:
        document = etree.fromstring(docx.read("word/document.xml"))
        paragraphs = [
            paragraph_profile(p)
            for p in document.xpath("//w:body/w:p", namespaces=NS)
            if text_of(p)
        ]

        sect = document.find(".//w:sectPr", NS)
        page = {
            "widthDxa": xpath_string(sect, "w:pgSz/@w:w"),
            "heightDxa": xpath_string(sect, "w:pgSz/@w:h"),
            "marginTopDxa": xpath_string(sect, "w:pgMar/@w:top"),
            "marginRightDxa": xpath_string(sect, "w:pgMar/@w:right"),
            "marginBottomDxa": xpath_string(sect, "w:pgMar/@w:bottom"),
            "marginLeftDxa": xpath_string(sect, "w:pgMar/@w:left"),
            "headerDxa": xpath_string(sect, "w:pgMar/@w:header"),
            "footerDxa": xpath_string(sect, "w:pgMar/@w:footer"),
            "docGridLinePitch": xpath_string(sect, "w:docGrid/@w:linePitch"),
        }

        size_counter = Counter(
            run["size"]
            for paragraph in paragraphs
            for run in paragraph["runs"]
            if run["size"]
        )

        return {
            "template": str(template_path),
            "page": page,
            "themeFonts": extract_theme_fonts(docx),
            "commonRunSizes": dict(size_counter.most_common()),
            "roleSamples": infer_roles(paragraphs),
            "tables": extract_table_profiles(document),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Extract page, paragraph, run, and table formatting from a DOCX template."
    )
    parser.add_argument("template", help="Path to the .docx template")
    parser.add_argument("--output", "-o", help="Optional JSON output path")
    args = parser.parse_args()

    profile = extract_profile(Path(args.template))
    rendered = json.dumps(profile, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
