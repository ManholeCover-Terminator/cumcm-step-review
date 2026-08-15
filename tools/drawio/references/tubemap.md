# Tube-Map Mode — a graph as a metro map

`scripts/tubemap.py` restyles a graph as a **London-Underground-style metro map**:
thick coloured lines, octilinear routing (horizontal / vertical / 45° only), white
interchange circles, small station stops, and offset labels — the instantly-readable
transit-map aesthetic.

Read this when the user asks for a "metro map", "subway map", "tube map", or wants a
system / pipeline / journey drawn as coloured transit lines instead of a boxes-and-
arrows diagram.

```bash
python3 <this-skill-dir>/scripts/tubemap.py metro.json -o metro.drawio
# then the normal workflow: validate.py → preview PNG → self-check → export
```

## When it fits

A tube map reads best when the graph is a set of **overlapping paths** that share a few
**interchange** nodes — pipelines, user journeys, request flows, a product's subsystems,
a roadmap of parallel workstreams. It is *not* the right choice for a dense mesh or a
strict hierarchy (use `autolayout.py` / a diagram-type preset for those).

## Input schema

You (the model) compose the metro JSON — from a system description, or by reading an
existing diagram's structure and grouping its edges into a handful of named "lines".

```json
{
  "stations": {
    "nl":     {"label": "Natural language", "gx": 0, "gy": 2},
    "layout": {"label": "Auto-layout",      "gx": 4, "gy": 2, "interchange": true},
    "drawio": {"label": ".drawio",          "gx": 6, "gy": 2, "interchange": true}
  },
  "lines": [
    {"name": "Author", "color": "#0098d4", "stations": ["nl", "layout", "drawio"]},
    {"name": "Import", "stations": ["code", "extract", "layout"]}
  ]
}
```

| Field | Required | Notes |
|---|---|---|
| `stations.<id>.label` | no (defaults to id) | Station name; XML-escaped automatically |
| `stations.<id>.gx` / `gy` | **yes** | Integer **grid** coordinates (not pixels); `--grid` sets the pitch (default 110px) |
| `stations.<id>.interchange` | no | `true` → white-fill black-ring circle (a transfer station); else a small stop |
| `lines[].name` | no | For your own reference |
| `lines[].color` | no | `#rrggbb`; a line without one gets the next colour from the built-in tube palette |
| `lines[].stations` | **yes** | Ordered station ids the line passes through; a station id may appear on several lines (that's an interchange) |

## The one layout rule: keep segments octilinear

For the crispest map, place each line's consecutive stations so they are **aligned
horizontally, vertically, or on a 45° diagonal** (same `gx`, same `gy`, or equal
`|Δgx| == |Δgy|`). When two stations aren't aligned, the script inserts **one** bend —
it runs the 45° diagonal for the shorter delta, then a straight axis segment into the
target — so the line still reads as a metro line rather than an arbitrary curve. Mark the
nodes where lines cross as `interchange: true`.

## Limitation

`tubemap.py` honours the grid coordinates you give it — it does **not** solve the
(NP-hard) octilinear metro-layout problem for you. Placing the stations on a sensible
grid is the authoring step; the script does the drawing, routing, markers, and colours.
Parallel lines sharing the exact same segment are drawn on top of each other (offset them
by a grid row if you need both visible).
