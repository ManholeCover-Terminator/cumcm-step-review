#!/usr/bin/env python3
"""De-rasterize an image-extracted graph (JSON) into an editable .drawio.

Turns a whiteboard photo, legacy PNG, or Visio screenshot into an editable
diagram: Claude's own vision reads the image and extracts a JSON description
of the nodes/edges (the workflow is documented in
references/derasterize.md); this script turns that JSON into `.drawio` XML,
honoring the coordinates, labels, shapes, and colors Claude read off the
image.

  python3 raster2drawio.py graph.json -o out.drawio

Input JSON:
  {"nodes": [{"id": "n1", "label": "API Gateway", "x": 120, "y": 60,
              "w": 160, "h": 60, "shape": "rect",
              "fill": "#dae8fc", "stroke": "#6c8ebf"},
             {"id": "n2", "label": "Auth DB", "x": 360, "y": 60,
              "shape": "cylinder"}],
   "edges": [{"source": "n1", "target": "n2", "label": "HTTPS",
              "dashed": false, "arrow": true}]}

Only "id" is required per node; label defaults to id, w/h default to
120/60, shape defaults to "rect" (choices: rect, rounded, ellipse,
rhombus/diamond, cylinder, parallelogram, cloud, hexagon), fill/stroke
default to the skill's palette blue. Edge "arrow" defaults to true
(endArrow=none when false); "dashed" defaults to false.

If ANY node is missing x or y, positions are not guessed: the graph is
handed to autolayout.py (shelled out, requires Graphviz `dot`) to place it,
and a note is written to stderr.

Usage: python3 raster2drawio.py <graph.json|-> [-o out.drawio]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

DEFAULT_W, DEFAULT_H = 120, 60
DEFAULT_FILL, DEFAULT_STROKE = "#dae8fc", "#6c8ebf"
SHAPES = {
    "rect": "whiteSpace=wrap;html=1;",
    "rounded": "rounded=1;whiteSpace=wrap;html=1;",
    "ellipse": "ellipse;whiteSpace=wrap;html=1;",
    "rhombus": "rhombus;whiteSpace=wrap;html=1;",
    "diamond": "rhombus;whiteSpace=wrap;html=1;",
    "cylinder": "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=15;",
    "parallelogram": "shape=parallelogram;whiteSpace=wrap;html=1;",
    "cloud": "ellipse;shape=cloud;whiteSpace=wrap;html=1;",
    "hexagon": "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;",
}
EDGE_BASE = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;"


def attr(value):
    # Newlines in labels become &#xa; so draw.io renders a line break (a raw
    # newline inside an XML attribute is normalized to a space by parsers).
    return escape(str(value), {'"': "&quot;", "\n": "&#xa;"})


def node_style(node):
    base = SHAPES.get(node.get("shape", "rect"), SHAPES["rect"])
    fill = node.get("fill", DEFAULT_FILL)
    stroke = node.get("stroke", DEFAULT_STROKE)
    return f"{base}fillColor={fill};strokeColor={stroke};"


def edge_style(edge):
    style = EDGE_BASE
    if edge.get("dashed"):
        style += "dashed=1;"
    if edge.get("arrow") is False:
        style += "endArrow=none;"
    return style


def to_drawio(nodes, edges):
    """Direct build: every node already has x/y. Mirrors autolayout.py's
    to_drawio() string-building, without the dot layout pass."""
    cells = []
    for node in nodes:
        w, h = node.get("w", DEFAULT_W), node.get("h", DEFAULT_H)
        cells.append(
            f'        <mxCell id="{attr(node["id"])}" value="{attr(node.get("label", node["id"]))}" '
            f'style="{attr(node_style(node))}" vertex="1" parent="1">\n'
            f'          <mxGeometry x="{node["x"]}" y="{node["y"]}" width="{w}" height="{h}" as="geometry"/>\n'
            f"        </mxCell>"
        )
    for i, edge in enumerate(edges):
        cells.append(
            f'        <mxCell id="e{i}" value="{attr(edge.get("label", ""))}" '
            f'style="{attr(edge_style(edge))}" edge="1" parent="1" '
            f'source="{attr(edge["source"])}" target="{attr(edge["target"])}">\n'
            f'          <mxGeometry relative="1" as="geometry"/>\n'
            f"        </mxCell>"
        )
    return (
        "<mxfile>\n"
        '  <diagram id="raster2drawio" name="Page-1">\n'
        '    <mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        'pageWidth="850" pageHeight="1100" math="0" shadow="0">\n'
        "      <root>\n"
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        + "\n".join(cells)
        + "\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n"
    )


def build_autolayout_graph(nodes, edges):
    """Same graph, in autolayout.py's input shape (positions dropped —
    dot will compute fresh ones for every node)."""
    return {
        "direction": "TB",
        "nodes": [
            {"id": n["id"], "label": n.get("label", n["id"]), "style": node_style(n),
             "width": n.get("w", DEFAULT_W), "height": n.get("h", DEFAULT_H)}
            for n in nodes
        ],
        "edges": [
            {"source": e["source"], "target": e["target"], "label": e.get("label", ""),
             "style": edge_style(e)}
            for e in edges
        ],
    }


def run_autolayout(graph):
    """Shell out to the sibling autolayout.py; return the .drawio XML text."""
    here = os.path.dirname(os.path.abspath(__file__))
    autolayout = os.path.join(here, "autolayout.py")
    fd, graph_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(graph, f)
        r = subprocess.run([sys.executable, autolayout, graph_path],
                           capture_output=True, text=True)
    finally:
        os.unlink(graph_path)
    if r.returncode != 0:
        sys.exit(f"error: autolayout.py failed: {r.stderr.strip()}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser(
        description="Convert an image-extracted graph JSON into an editable .drawio.")
    ap.add_argument("input", help="graph JSON file, or - for stdin")
    ap.add_argument("-o", "--output", help="output .drawio path (default: stdout)")
    args = ap.parse_args()

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        try:
            with open(args.input, encoding="utf-8") as f:
                raw = f.read()
        except OSError as exc:
            sys.exit(f"error: cannot read {args.input}: {exc}")
    try:
        graph = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: invalid JSON: {exc}")

    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if not nodes:
        sys.exit("error: no nodes in input")
    for n in nodes:
        if "id" not in n:
            sys.exit("error: every node needs an 'id'")
    for e in edges:
        if "source" not in e or "target" not in e:
            sys.exit("error: every edge needs 'source' and 'target'")

    if any(n.get("x") is None or n.get("y") is None for n in nodes):
        xml = run_autolayout(build_autolayout_graph(nodes, edges))
        sys.stderr.write(
            "note: some nodes had no x/y — positions were auto-placed via autolayout.py\n")
    else:
        xml = to_drawio(nodes, edges)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(xml)
        sys.stderr.write(f"wrote {args.output} ({len(nodes)} nodes, {len(edges)} edges)\n")
    else:
        sys.stdout.write(xml)


if __name__ == "__main__":
    main()
