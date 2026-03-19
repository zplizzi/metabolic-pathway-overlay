import html as html_mod
import json
import re
from pathlib import Path

from quart import Quart, send_file, request, jsonify, abort

from analyte_mapping import build_analyte_data, build_all_analytes

app = Quart(__name__)


def pathway_path(name: str) -> Path:
    """Resolve a pathway name to its .drawio file, rejecting path traversal."""
    safe = Path(name).name  # strip any directory components
    p = app.config["pathways_dir"] / f"{safe}.drawio"
    if not p.exists():
        return None
    return p


@app.route("/")
async def index():
    return await send_file(Path(__file__).parent / "index.html")


@app.route("/api/pathways")
async def list_pathways():
    """List available pathway names."""
    names = sorted(p.stem for p in app.config["pathways_dir"].glob("*.drawio"))
    return jsonify(names)


@app.route("/api/pathways/<name>")
async def get_pathway(name: str):
    p = pathway_path(name)
    if not p:
        abort(404)
    return await send_file(p)


@app.route("/api/pathways/<name>", methods=["PUT"])
async def save_pathway(name: str):
    p = pathway_path(name)
    if not p:
        # Allow creating new pathways
        safe = Path(name).name
        p = app.config["pathways_dir"] / f"{safe}.drawio"
    data = await request.get_data(as_text=True)
    p.write_text(data)
    return jsonify({"ok": True})


@app.route("/api/analyte-data")
async def analyte_data():
    """Return pre-processed analyte data mapped to pathway node labels."""
    data = build_analyte_data(app.config["test_data_dir"])
    return jsonify(data)


@app.route("/api/share")
async def share():
    """Generate a self-contained HTML file with all data embedded."""
    page = (Path(__file__).parent / "index.html").read_text()

    # Collect all pathway XML
    pathways = {}
    for p in sorted(app.config["pathways_dir"].glob("*.drawio")):
        pathways[p.stem] = p.read_text()

    analyte = build_analyte_data(app.config["test_data_dir"])

    # Replace the async data loading with embedded data.
    page = re.sub(
        r'async function loadAnalyteData\(\) \{.*?\n\}',
        'async function loadAnalyteData() {\n'
        '  const data = EMBEDDED_ANALYTE_DATA;\n'
        '  ANALYTE_ALIASES = data._aliases || {};\n'
        '  delete data._aliases;\n'
        '  ANALYTE_DATA = data;\n'
        '}',
        page, flags=re.DOTALL
    )

    page = re.sub(
        r'async function initPathways\(\) \{.*?\n\}',
        'async function initPathways() {\n'
        '  const names = Object.keys(EMBEDDED_PATHWAYS).sort();\n'
        '  const select = document.getElementById("pathway-select");\n'
        '  select.innerHTML = "";\n'
        '  for (const name of names) {\n'
        '    const opt = document.createElement("option");\n'
        '    opt.value = name;\n'
        '    opt.textContent = name.replace(/_/g, " ");\n'
        '    select.appendChild(opt);\n'
        '  }\n'
        '  const initial = location.hash.slice(1) || "full_figure_1" || names[0];\n'
        '  if (initial && names.includes(initial)) select.value = initial;\n'
        '  await switchPathway(select.value);\n'
        '}',
        page, flags=re.DOTALL
    )

    page = re.sub(
        r'async function switchPathway\(name\) \{.*?\n\}',
        'async function switchPathway(name) {\n'
        '  const isNewPathway = currentPathway && currentPathway !== name;\n'
        '  currentPathway = name;\n'
        '  location.hash = name;\n'
        '  drawioXml = EMBEDDED_PATHWAYS[name];\n'
        '  renderFromDrawio();\n'
        '  if (isNewPathway) sessionStorage.removeItem("pv_view");\n'
        '  resetView();\n'
        '}',
        page, flags=re.DOTALL
    )

    # Remove the editor button and editor container
    page = page.replace(
        '<button class="edit-btn" id="edit-btn" onclick="toggleEditor()">Edit Diagram</button>',
        ''
    )
    page = page.replace(
        '<!-- Editor (draw.io iframe) -->\n  <div id="editor-container"></div>',
        ''
    )

    # Inject embedded data right after <script>
    embedded_js = (
        f'\nconst EMBEDDED_PATHWAYS = {json.dumps(pathways)};\n'
        f'const EMBEDDED_ANALYTE_DATA = {json.dumps(analyte)};\n'
    )
    page = page.replace('<script>\n', '<script>\n' + embedded_js, 1)

    page = page.replace('<title>Pathway Viewer</title>',
                        '<title>Pathway Viewer (Shared)</title>')

    return page, 200, {
        "Content-Type": "text/html",
        "Content-Disposition": "attachment; filename=pathway_viewer.html"
    }


@app.route("/api/all-analytes")
async def all_analytes():
    """Return all analytes from all sources, grouped by source."""
    data = build_all_analytes(app.config["test_data_dir"])
    return jsonify(data)


@app.route("/drawio-viewer")
async def drawio_viewer():
    """Render a .drawio file using the diagrams.net viewer for comparison."""
    name = request.args.get("pathway", "b3_nad")
    p = pathway_path(name)
    if not p:
        abort(404)
    xml = p.read_text()
    mxgraph_json = json.dumps({"highlight": "#0000ff", "nav": False, "resize": True, "xml": xml})
    attr_safe = html_mod.escape(mxgraph_json, quote=True)
    page = f"""<!DOCTYPE html>
<html><head>
<style>* {{ margin:0; padding:0; }} body {{ background: white; }}</style>
</head><body>
<div class="mxgraph" style="max-width:100%;" data-mxgraph="{attr_safe}">
</div>
<script src="https://viewer.diagrams.net/js/viewer-static.min.js"></script>
</body></html>"""
    return page, 200, {"Content-Type": "text/html"}


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Serve the pathway editor/viewer")
    parser.add_argument("--port", default=5555, type=int, help="Port to serve on")
    parser.add_argument("--pathways_dir", default="data/pathways", type=str, help="path to pathways folder")
    parser.add_argument("--test_data_dir", default="data/test_data", type=str, help="path to test data folder")
    args = parser.parse_args()

    app.config["pathways_dir"] = Path(args.pathways_dir)
    app.config["test_data_dir"] = Path(args.test_data_dir)

    app.run(host="127.0.0.1", port=args.port, use_reloader=True)
