#!/usr/bin/env python3
"""Collapse a big .drawio into a boardroom-friendly executive summary.

Detects clusters in a large diagram with a deterministic pure-Python label
propagation pass (no networkx), replaces each cluster with ONE labeled group
node, keeps aggregated inter-cluster edges, and emits a 2-page .drawio: page 1
is the executive view (auto-laid-out via autolayout.py), page 2 is the
original full diagram, copied verbatim. Each executive node is wrapped in a
draw.io UserObject `data:page/id,...` drill-down link to page 2, so clicking
"Auth (5)" jumps straight into the full detail.

Community detection is unsupervised — it finds however many clusters the
graph naturally has; `--clusters` is only a soft hint and may be ignored.
Clusters are named after the longest common leading token shared by their
members' labels (falling back to the highest-degree member's label), with the
member count appended, e.g. "Auth (5)". Rename them by hand afterward for a
more semantic label — label propagation does not know what your system does.

Requires Graphviz `dot` on PATH (shells out to autolayout.py to place the
executive nodes).

  python3 compress.py big-system.drawio -o exec-view.drawio

Usage: python3 compress.py <diagram.drawio> [-o out.drawio] [--clusters N]
"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(path):
    """Return (nodes, edges) for a .drawio: nodes {id: (label, style)} for leaf
    vertices, edges {(source_id, target_id)}. Cells are flattened across pages;
    UserObject/object wrappers are unwrapped (id on the wrapper, cell inside).
    Copied from drawiodiff.parse() — see SHARED CONVENTIONS."""
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
    parents = {c.get("parent") for c in cells}                # ids that have children
    nodes, edges = {}, set()
    for c in cells:
        cid = c.get("id")
        if c.get("edge") == "1":
            s, t = c.get("source"), c.get("target")
            if s and t:
                edges.add((s, t))
        elif c.get("vertex") == "1" and cid not in parents:   # leaf vertices only
            if "edgeLabel" in (c.get("style") or ""):
                continue
            g = c.find("mxGeometry")
            if g is not None and g.get("relative") == "1":    # edge-label child
                continue
            nodes[cid] = (labels.get(cid, ""), c.get("style") or "")
    return nodes, edges


def label_propagation(node_ids, edges, max_passes=20):
    """Deterministic pure-Python label propagation for community detection.

    Edges are treated as undirected for clustering. Each pass computes every
    node's new label synchronously from the PREVIOUS pass's labels (most
    frequent label among neighbours, ties -> smallest label), then applies
    them all at once — this keeps a thin bridge between two dense clusters
    from cascading a merge within a single pass. Stops early once no label
    changes, else after `max_passes`. Returns {node_id: community_label}.
    """
    nodes = sorted(set(node_ids))
    neighbours = {n: set() for n in nodes}
    for s, t in edges:
        if s in neighbours and t in neighbours and s != t:
            neighbours[s].add(t)
            neighbours[t].add(s)
    labels = {n: n for n in nodes}
    for _ in range(max_passes):
        new_labels = {}
        for n in nodes:
            if not neighbours[n]:
                new_labels[n] = labels[n]
                continue
            counts = {}
            for nb in neighbours[n]:
                lbl = labels[nb]
                counts[lbl] = counts.get(lbl, 0) + 1
            best = max(counts.values())
            new_labels[n] = min(lbl for lbl, c in counts.items() if c == best)
        if new_labels == labels:
            break
        labels = new_labels
    return labels


def compute_degree(node_ids, edges):
    """Undirected degree per node (used as the naming tiebreak)."""
    degree = {n: 0 for n in node_ids}
    for s, t in edges:
        if s in degree:
            degree[s] += 1
        if t in degree:
            degree[t] += 1
    return degree


def aggregate_edges(edges, community_of):
    """Roll original edges up to inter-community edges: for every edge whose
    endpoints fall in two different communities, count crossings by
    (source_community, target_community) and dedupe into one entry per pair.
    Same-community (internal) edges are dropped. Returns
    {(src_community, tgt_community): crossing_count}."""
    counts = {}
    for s, t in edges:
        cs, ct = community_of.get(s), community_of.get(t)
        if cs is None or ct is None or cs == ct:
            continue
        counts[(cs, ct)] = counts.get((cs, ct), 0) + 1
    return counts


def cluster_name(member_ids, node_labels, degree):
    """Heuristic community name: the longest common leading token shared by
    every member's label (split on whitespace), else the highest-degree
    member's label. The member count is appended, e.g. "Auth (5)"."""
    token_lists = [str(node_labels.get(m, m)).split() for m in member_ids]
    common = []
    if token_lists and all(token_lists):
        for tokens in zip(*token_lists):
            if len(set(tokens)) == 1:
                common.append(tokens[0])
            else:
                break
    if common:
        base = " ".join(common)
    else:
        top = max(member_ids, key=lambda m: (degree.get(m, 0), m))
        base = node_labels.get(top) or top
    return f"{base} ({len(member_ids)})"


def layout_exec_page(graph):
    """Shell out to autolayout.py to place the executive nodes; return the
    rendered <diagram>...</diagram> page, renamed to a friendlier id/title."""
    with tempfile.TemporaryDirectory() as d:
        gpath = os.path.join(d, "exec.json")
        with open(gpath, "w", encoding="utf-8") as f:
            json.dump(graph, f)
        opath = os.path.join(d, "exec.drawio")
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "autolayout.py"), gpath, "-o", opath],
            capture_output=True, text=True,
        )
        if r.returncode != 0 or not os.path.exists(opath):
            sys.exit(f"error: autolayout failed: {r.stderr.strip()}")
        with open(opath, encoding="utf-8") as f:
            xml = f.read()
    m = re.search(r"(<diagram\b.*?</diagram>)", xml, re.S)
    if not m:
        sys.exit("error: autolayout produced no page")
    page = m.group(1).replace('id="autolayout"', 'id="exec-view"', 1)
    page = page.replace('name="Page-1"', 'name="Executive View"', 1)
    return page + "\n"


def copy_original_page(path, page2_id):
    """Copy the source's first page verbatim (cells untouched) into a new
    <diagram> with id=page2_id, so exec-node drill-down links resolve to it."""
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        sys.exit(f"error: cannot parse {path}: {exc}")
    pages = tree.getroot().findall("diagram") or [tree.getroot()]
    page = copy.deepcopy(pages[0])
    if page.find("mxGraphModel/root") is None:
        sys.exit(f"error: {path}: page is compressed (no <root>), cannot copy verbatim")
    page.set("id", page2_id)
    page.set("name", "Full Diagram")
    return ET.tostring(page, encoding="unicode") + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="Collapse a big .drawio into an executive-summary view with drill-down.")
    ap.add_argument("input", help="source .drawio")
    ap.add_argument("-o", "--output", help="output .drawio path (default: stdout)")
    ap.add_argument("--clusters", type=int,
                    help="soft hint for cluster count; label propagation picks the "
                         "count automatically and may ignore this")
    args = ap.parse_args()

    if args.clusters:
        sys.stderr.write("note: --clusters is a soft hint; label propagation "
                         "determines the actual cluster count automatically\n")

    nodes, edges = parse(args.input)
    if not nodes:
        sys.exit(f"error: no leaf vertices found in {args.input}")

    community_of = label_propagation(nodes.keys(), edges)
    communities = {}
    for nid in sorted(nodes):
        communities.setdefault(community_of[nid], []).append(nid)

    degree = compute_degree(nodes.keys(), edges)
    node_labels = {nid: label for nid, (label, _style) in nodes.items()}
    names = {c: cluster_name(members, node_labels, degree) for c, members in communities.items()}

    crossings = aggregate_edges(edges, community_of)

    page2_id = "full-diagram"
    exec_nodes = [{"id": f"c_{c}", "label": names[c], "link": f"data:page/id,{page2_id}"}
                  for c in communities]
    exec_edges = [{"source": f"c_{s}", "target": f"c_{t}", "label": str(n) if n > 1 else ""}
                  for (s, t), n in sorted(crossings.items())]
    exec_graph = {"direction": "TB", "nodes": exec_nodes, "edges": exec_edges}

    page1 = layout_exec_page(exec_graph)
    page2 = copy_original_page(args.input, page2_id)
    xml = "<mxfile>\n" + page1 + page2 + "</mxfile>\n"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(xml)
        sys.stderr.write(f"wrote {args.output} ({len(nodes)} nodes -> "
                         f"{len(communities)} clusters)\n")
    else:
        sys.stdout.write(xml)
        sys.stderr.write(f"{len(nodes)} nodes -> {len(communities)} clusters\n")


if __name__ == "__main__":
    main()
