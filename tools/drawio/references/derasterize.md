# De-rasterizing an image into an editable diagram

Goal: turn a whiteboard photo, a legacy PNG export, or a Visio screenshot
into an EDITABLE `.drawio` file. Claude's own vision does the extraction;
`scripts/raster2drawio.py` only turns the extracted JSON into XML.

## Workflow

1. **Look at the image.** Read it with your normal vision — no OCR tool
   needed. For every box/shape in the picture, note:
   - `id` — any short stable slug (`n1`, `api-gw`, …)
   - `label` — the text verbatim, exactly as written (fix obvious typos only
     if the source is clearly a typo, not a stylistic choice)
   - `x`, `y` — estimate the pixel position of the shape's top-left corner
     from the image (a rough grid read is fine; exact pixel-matching isn't
     the goal)
   - `w`, `h` — estimate width/height in pixels (defaults to 120x60 if you
     can't tell)
   - `shape` — classify: `rect`, `rounded`, `ellipse`, `rhombus`/`diamond`,
     `cylinder`, `parallelogram`, `cloud`, `hexagon`
   - `fill`, `stroke` — sample the approximate fill/border color as a hex
     value (skip if the source is plain black-and-white)

   For every arrow/line, note `source`, `target`, the label text if any
   (e.g. "Yes"/"No" on a decision arrow), whether it's `dashed`, and whether
   it has a visible `arrow` head (false for a plain connecting line).

2. **Write the JSON** to a file:
   ```json
   {"nodes": [{"id": "n1", "label": "API Gateway", "x": 120, "y": 60,
               "w": 160, "h": 60, "shape": "rect",
               "fill": "#dae8fc", "stroke": "#6c8ebf"}],
    "edges": [{"source": "n1", "target": "n2", "label": "HTTPS",
               "dashed": false, "arrow": true}]}
   ```

3. **Convert it**:
   ```bash
   python3 scripts/raster2drawio.py graph.json -o out.drawio
   ```
   If any node is missing `x`/`y`, don't guess coordinates by hand — leave
   them out and the script auto-places the whole graph via `autolayout.py`
   (Graphviz `dot` required), noting this on stderr.

4. **Continue the standard workflow**: `validate.py` for structural issues,
   export a preview PNG, then a vision self-check — compare the rendered
   PNG side-by-side against the ORIGINAL image and look for missed shapes,
   wrong labels, or misrouted edges. Fix and re-run as needed.

## Honest limitation

Hand sketches with ambiguous, crossing, or arrowhead-less connections are
genuinely ambiguous — expect one review round where you correct a
misattributed edge after seeing the first render next to the original.
