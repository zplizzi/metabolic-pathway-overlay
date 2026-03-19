# Pathway Viewer

Interactive diagram viewer for metabolic pathways with lab result overlays. Renders `.drawio` files as SVG with clickable metabolite nodes showing test history, sparklines, and reference ranges.

## Architecture

- **`pathways/*.drawio`** — Source of truth for diagram layout (node positions, connections, routing). Edit in draw.io to change diagram structure.
- **Viewer mode** — Parses `.drawio` XML and renders SVG. Metabolite overlays (badges, click panels) are attached by matching drawio node IDs to `METABOLITES[id]` keys in `index.html`.
- **Edit mode** — Embeds the draw.io editor via iframe + postMessage API. Saves PUT back to the server. Exit re-renders from updated XML.

## Files

```
pathways/            — .drawio diagram files (one per pathway)
  b3_nad.drawio      — B3/NAD+ pathway (small, ~90 lines, hand-built)
  full_figure_1.drawio — Full metabolic figure (1.6MB, 3263 cells)
index.html           — viewer + editor UI, metabolite data, all rendering logic
server.py            — Quart app: serves pages, lists/reads/writes pathway files
compare.py           — Screenshot comparison tool (playwright)
screenshots/         — Generated comparison screenshots (gitignored)
```

## Running

Requires `quart`, `hypercorn` (in the parent venv at `tcr_play/.venv`).

```
cd b3_pathway
uv run python server.py [--port 5555]
# → http://127.0.0.1:5555
```

The URL hash selects the pathway: `http://127.0.0.1:5555/#b3_nad`

## API

```
GET  /api/pathways          — list available pathway names (JSON array)
GET  /api/pathways/<name>   — get .drawio XML for a pathway
PUT  /api/pathways/<name>   — save .drawio XML
GET  /drawio-viewer?pathway=<name> — render via diagrams.net viewer (for comparison)
```

## Comparison Tool

Screenshots both the HTML renderer and the diagrams.net viewer side-by-side for visual comparison. Requires `playwright` (install with `pip install playwright && playwright install chromium`).

```
python compare.py [pathway_name]   # default: b3_nad
# Outputs: screenshots/<name>_html.png, screenshots/<name>_drawio.png
```

The tool temporarily removes overflow/transform CSS and resizes the viewport to capture the full SVG at native resolution.

## How the Renderer Works

### Parsing (`parseDrawioNodes`)

1. Every `<mxCell>` with geometry becomes a node or edge
2. Edges are identified by `source`/`target` attributes or `edge="1"`
3. Edges parse waypoints from `<Array><mxPoint>` children, and `sourcePoint`/`targetPoint` from `<mxPoint as="sourcePoint|targetPoint">`
4. Parent-child group offsets are resolved recursively — children positioned relative to their parent group's coordinates

### Node Types (`nodeType`)

Classified by style flags:
- **`text`** — Most common in complex diagrams. Rendered as plain SVG text with HTML stripped (`htmlToPlainText`). Supports alignment, rotation, font size/color/bold.
- **`ellipse`** — SVG ellipse with optional label
- **`rect`** — Rectangle with fill/stroke/rounded corners
- **`group`** / **`dashed-group`** — Container rectangles, rendered first (below edges)
- **`image`** — Skipped (not rendered)

### Edge Rendering (`drawEdge`)

- **Connection points**: Uses explicit `exitX`/`exitY`/`entryX`/`entryY` from style when present. Otherwise auto-routes to the nearest boundary point on the node rectangle (`nearestBoundaryPoint`).
- **Floating endpoints**: Many edges (~50% in complex diagrams) have no named source/target node. These use `sourcePoint`/`targetPoint` geometry coordinates instead.
- **Curved edges** (`curved=1`): With waypoints → Catmull-Rom spline via `buildCurvedPath`. Without → simple cubic bezier.
- **Orthogonal edges** (`edgeStyle=orthogonalEdgeStyle`): L-shaped or Z-shaped paths based on exit/entry direction.
- **Straight edges**: Direct line (default fallback).
- **Arrows**: Per-edge color markers generated in `<defs>`. Supports `classic`, `open`, `block`, `none`, and bidirectional.
- **Labels**: Positioned at path midpoint (arc-length-based for polylines). White background rect behind text for readability.

### Coordinate System

- Bounding box computed across all nodes, waypoints, and floating edge endpoints
- Negative coordinates handled by offsetting everything so `min` becomes `(PAD, PAD)`
- SVG dimensions set to the full diagram extent

### Pan/Zoom

- CSS transform on `.diagram-wrap` (translate + scale)
- `wheel` event on the diagram pane: `ctrlKey` = pinch-zoom (macOS trackpad), otherwise = two-finger pan
- `resetView()` called on pathway switch

## Known Limitations / Future Work

- **Edge routing quality**: The auto-routing for edges without explicit exit/entry ports is basic (nearest-boundary-point). Draw.io's routing avoids crossings and routes around obstacles — we don't attempt this.
- **Curved edges without waypoints**: Simple bezier, doesn't match draw.io's curve calculation exactly. Visible in dense diagrams as lines crossing through nodes.
- **HTML in labels**: Stripped to plain text (`htmlToPlainText`). Subscripts, superscripts, colored spans within a single label are lost. Could use `<foreignObject>` for full HTML rendering but would complicate the SVG.
- **Font size extremes**: Some drawio files contain edges with `fontSize=500` (probably a draw.io bug). These create oversized label backgrounds. Could clamp font sizes.
- **`shape=flexArrow`**: Rendered as a basic rectangle, not the actual arrow shape.
- **`shape=mxgraph.floorplan.wall`**: Not specially handled.
- **Image nodes**: Skipped entirely.
- **Metabolite data**: Hardcoded in `index.html` as the `METABOLITES` JS object. Only applies to `b3_nad` pathway currently. Other pathways render the diagram but without overlays.
