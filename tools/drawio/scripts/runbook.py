#!/usr/bin/env python3
"""Turn a flowchart / decision-tree .drawio into a click-through HTML runbook.

Parses the nodes and edges out of a .drawio and infers a node "type" from its
shape style (ellipse -> start/end, rhombus -> decision, parallelogram -> io,
else process). The ellipse with no incoming edges is taken as the start node.
The output is a single self-contained HTML page: the current node's text
front and center, one button per outgoing edge (labeled with the edge's
choice text, or "Continue" when a node has a single unlabeled successor), a
breadcrumb trail of visited nodes, Back/Restart controls, and an "end" state
on terminal nodes (no outgoing edges). No draw.io CLI is needed -- the XML is
read and the HTML is built directly, so the whole script is testable without
any external tool.

  python3 runbook.py triage.drawio -o triage.html

Usage: python3 runbook.py <file.drawio> [-o out.html]
"""
import argparse
import html
import json
import os
import sys
import xml.etree.ElementTree as ET


def parse(path):
    """Return (nodes, edges, start_id).

    nodes: {id: {"label": str, "type": "start"|"end"|"decision"|"io"|"process"}}
    edges: [{"source": id, "target": id, "label": str}, ...] in document order.
    Cells are flattened across pages; UserObject/object wrappers are unwrapped
    (id on the wrapper, cell inside) -- mirrors drawiodiff.py parse().
    """
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        sys.exit(f"error: cannot parse {path}: {exc}")
    pages = tree.getroot().findall("diagram") or [tree.getroot()]
    cells, labels = [], {}
    for page in pages:
        model = page.find("mxGraphModel")
        root = model.find("root") if model is not None else None
        if root is None:
            if (page.text or "").strip():
                sys.stderr.write(f"warning: {path}: a page is compressed, skipped\n")
            continue
        for child in root:
            if child.tag == "mxCell":
                cells.append(child)
                labels[child.get("id")] = child.get("value") or ""
            elif child.tag in ("UserObject", "object"):
                inner = child.find("mxCell")
                if inner is not None:
                    inner.set("id", child.get("id", ""))
                    cells.append(inner)
                    labels[child.get("id")] = child.get("label") or child.get("value") or ""

    parents = {c.get("parent") for c in cells}             # ids that have children
    order, styles, edges = [], {}, []
    for c in cells:
        cid = c.get("id")
        if c.get("edge") == "1":
            s, t = c.get("source"), c.get("target")
            if s and t:
                edges.append({"source": s, "target": t, "label": labels.get(cid, "")})
        elif c.get("vertex") == "1" and cid not in parents:  # leaf vertices only
            style = c.get("style") or ""
            if "edgeLabel" in style:
                continue
            g = c.find("mxGeometry")
            if g is not None and g.get("relative") == "1":  # edge-label child
                continue
            order.append(cid)
            styles[cid] = style

    indeg = {i: 0 for i in order}
    outdeg = {i: 0 for i in order}
    for e in edges:
        if e["source"] in outdeg:
            outdeg[e["source"]] += 1
        if e["target"] in indeg:
            indeg[e["target"]] += 1

    nodes = {}
    for nid in order:
        style = styles[nid]
        if "ellipse" in style:
            ntype = "end" if outdeg[nid] == 0 and indeg[nid] > 0 else "start"
        elif "rhombus" in style:
            ntype = "decision"
        elif "parallelogram" in style:
            ntype = "io"
        else:
            ntype = "process"
        nodes[nid] = {"label": labels.get(nid, ""), "type": ntype}

    edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]

    # Start node: the ellipse with no incoming edges; else the unique in-degree-0
    # node; else the first node in document order. Warn to stderr if ambiguous.
    ellipse_zero_in = [nid for nid in order if "ellipse" in styles[nid] and indeg[nid] == 0]
    if len(ellipse_zero_in) == 1:
        start_id = ellipse_zero_in[0]
    elif len(ellipse_zero_in) > 1:
        sys.stderr.write("warning: multiple ellipse nodes with in-degree 0; picking the first\n")
        start_id = ellipse_zero_in[0]
    else:
        zero_in = [nid for nid in order if indeg[nid] == 0]
        if len(zero_in) == 1:
            start_id = zero_in[0]
        elif len(zero_in) > 1:
            sys.stderr.write("warning: no unique in-degree-0 node; picking the first\n")
            start_id = zero_in[0]
        elif order:
            sys.stderr.write("warning: no start node found by heuristics; using the first node\n")
            start_id = order[0]
        else:
            start_id = None
    return nodes, edges, start_id


def build_html(title, nodes, edges, start_id):
    """One self-contained click-through page. nodes: {id:{label,type}}; edges:
    [{source,target,label}, ...]; start_id: node id to begin the walk at."""
    adjacency = {}
    for e in edges:
        adjacency.setdefault(e["source"], []).append({"target": e["target"], "label": e["label"]})
    payload = json.dumps({"nodes": nodes, "edges": adjacency, "start": start_id}).replace("</", "<\\/")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;
background:#f6f7f9;color:#1a1a1a;min-height:100vh;display:flex;flex-direction:column;align-items:center}}
@media(prefers-color-scheme:dark){{body{{background:#15171a;color:#e8e8e8}}}}
header{{width:100%;max-width:640px;padding:16px 20px 4px}}
h1{{margin:0;font-size:16px;font-weight:600}}
#crumbs{{width:100%;max-width:640px;padding:6px 20px;display:flex;flex-wrap:wrap;gap:4px;
font-size:12px;color:#667}}
@media(prefers-color-scheme:dark){{#crumbs{{color:#9aa}}}}
#crumbs span:not(:last-child)::after{{content:" \\2192 ";margin:0 2px}}
main{{width:100%;max-width:640px;padding:12px 20px 28px;flex:1}}
#card{{background:#fff;border:1px solid #0002;border-left:4px solid #0d99ff;border-radius:12px;
padding:24px;box-shadow:0 1px 3px #0001}}
@media(prefers-color-scheme:dark){{#card{{background:#1e2226;border-color:#fff2;border-left-color:#0d99ff}}}}
#card.decision{{border-left-color:#d79b00}}
#card.end{{border-left-color:#82b366}}
#card.io{{border-left-color:#9673a6}}
#type{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#889;margin:0 0 8px}}
#label{{font-size:19px;font-weight:600;white-space:pre-wrap;margin:0 0 20px}}
.choices{{display:flex;flex-direction:column;gap:8px}}
.choices button{{font:inherit;text-align:left;padding:10px 14px;border:1px solid #0002;
border-radius:8px;background:#fff;cursor:pointer;color:inherit}}
@media(prefers-color-scheme:dark){{.choices button{{background:#262b31;border-color:#fff2}}}}
.choices button:hover{{border-color:#0d99ff;color:#0d99ff}}
.ctl{{display:flex;gap:10px;margin-top:20px}}
.ctl button{{font:inherit;padding:6px 14px;border:1px solid #0002;border-radius:8px;
background:#fff;cursor:pointer;color:inherit}}
@media(prefers-color-scheme:dark){{.ctl button{{background:#262b31;border-color:#fff2}}}}
.ctl button:hover{{border-color:#0d99ff}}
.ctl button:disabled{{opacity:.4;cursor:default}}
#endmsg{{display:none;color:#82b366;font-weight:600;margin:0}}
</style></head><body>
<header><h1>{html.escape(title)}</h1></header>
<div id="crumbs"></div>
<main>
<div id="card">
<p id="type"></p>
<p id="label"></p>
<div class="choices" id="choices"></div>
<p id="endmsg">End of path -- nothing more to check.</p>
</div>
<div class="ctl">
  <button id="back">&larr; Back</button>
  <button id="restart">&#8635; Restart</button>
</div>
</main>
<script>
const DATA={payload};
let path=[DATA.start];
const $=id=>document.getElementById(id);
function render(){{
  const cur=path[path.length-1];
  const node=DATA.nodes[cur]||{{label:String(cur),type:"process"}};
  $("card").className=node.type;
  $("type").textContent=node.type;
  $("label").textContent=node.label;
  const choices=DATA.edges[cur]||[];
  const box=$("choices");box.innerHTML="";
  $("endmsg").style.display=choices.length?"none":"block";
  choices.forEach(c=>{{
    const b=document.createElement("button");
    const target=DATA.nodes[c.target]||{{}};
    b.textContent=c.label||(choices.length===1?"Continue":(target.label||c.target));
    b.onclick=()=>{{path.push(c.target);render();}};
    box.appendChild(b);
  }});
  $("back").disabled=path.length<2;
  const crumbs=$("crumbs");crumbs.innerHTML="";
  path.forEach((id,i)=>{{
    const s=document.createElement("span");
    s.textContent=(DATA.nodes[id]||{{}}).label||id;
    if(i<path.length-1){{
      s.style.cursor="pointer";
      s.onclick=()=>{{path=path.slice(0,i+1);render();}};
    }}
    crumbs.appendChild(s);
  }});
}}
$("back").onclick=()=>{{if(path.length>1){{path.pop();render();}}}};
$("restart").onclick=()=>{{path=[DATA.start];render();}};
render();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Turn a flowchart .drawio into a click-through HTML runbook.")
    ap.add_argument("file")
    ap.add_argument("-o", "--output", help="output .html (default: alongside input)")
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        sys.exit(f"error: {args.file} not found")
    nodes, edges, start_id = parse(args.file)
    if not nodes:
        sys.exit(f"error: no nodes found in {args.file}")
    if start_id is None:
        sys.exit(f"error: no start node found in {args.file}")

    title = os.path.splitext(os.path.basename(args.file))[0]
    out = args.output or os.path.splitext(args.file)[0] + ".html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_html(title, nodes, edges, start_id))
    sys.stderr.write(f"wrote {out} ({len(nodes)} nodes, {len(edges)} edges)\n")


if __name__ == "__main__":
    main()
