// ─── DRAWIO PARSING ──────────────────────────────────────────────────────────

function parseDrawioNodes(doc) {
  const nodes = {};
  const edges = [];

  for (const cell of doc.querySelectorAll("mxCell")) {
    const id = cell.getAttribute("id");
    const geo = cell.querySelector("mxGeometry");
    const style = cell.getAttribute("style") || "";
    const value = cell.getAttribute("value") || "";
    const source = cell.getAttribute("source");
    const target = cell.getAttribute("target");
    const parent = cell.getAttribute("parent") || "1";

    if (source || target || cell.getAttribute("edge") === "1") {
      const waypoints = [];
      let sourcePoint = null, targetPoint = null;
      if (geo) {
        for (const pt of geo.querySelectorAll(":scope > mxPoint")) {
          const as = pt.getAttribute("as");
          const px = parseFloat(pt.getAttribute("x"));
          const py = parseFloat(pt.getAttribute("y"));
          if (as === "sourcePoint" && !isNaN(px) && !isNaN(py)) {
            sourcePoint = { x: px, y: py };
          } else if (as === "targetPoint" && !isNaN(px) && !isNaN(py)) {
            targetPoint = { x: px, y: py };
          } else if (as !== "offset" && !isNaN(px) && !isNaN(py)) {
            waypoints.push({ x: px, y: py });
          }
        }
        const arr = geo.querySelector("Array");
        if (arr) {
          for (const pt of arr.querySelectorAll("mxPoint")) {
            const px = parseFloat(pt.getAttribute("x"));
            const py = parseFloat(pt.getAttribute("y"));
            if (!isNaN(px) && !isNaN(py)) waypoints.push({ x: px, y: py });
          }
        }
      }
      const labelX = geo ? parseFloat(geo.getAttribute("x")) : NaN;
      const labelY = geo ? parseFloat(geo.getAttribute("y")) : NaN;
      edges.push({ id, source, target, value, style, waypoints, sourcePoint, targetPoint, parent,
                    labelX: isNaN(labelX) ? 0 : labelX, labelY: isNaN(labelY) ? 0 : labelY });
    } else if (geo && geo.getAttribute("as") === "geometry" && id !== "0" && id !== "1") {
      const x = parseFloat(geo.getAttribute("x") || 0);
      const y = parseFloat(geo.getAttribute("y") || 0);
      const w = parseFloat(geo.getAttribute("width") || 0);
      const h = parseFloat(geo.getAttribute("height") || 0);
      const relative = geo.getAttribute("relative") === "1";
      if (w > 0 && h > 0) {
        nodes[id] = { x, y, w, h, value, style, parent, relative };
      }
    }
  }

  // Resolve parent group offsets (groups position children relative to parent)
  function resolvePos(nodeId, seen = new Set()) {
    const n = nodes[nodeId];
    if (!n || n._resolved || seen.has(nodeId)) return;
    seen.add(nodeId);
    if (n.parent && n.parent !== "0" && n.parent !== "1" && nodes[n.parent]) {
      resolvePos(n.parent, seen);
      const p = nodes[n.parent];
      const pStyle = parseStyle(p.style);
      const pRotation = parseFloat(pStyle.rotation) || 0;
      n.x += p.x;
      n.y += p.y;
      n._parentRotation = (n._parentRotation || 0) + pRotation;
    }
    n._resolved = true;
  }
  for (const id of Object.keys(nodes)) resolvePos(id);

  // Resolve edge coordinates for edges inside groups
  for (const edge of edges) {
    if (!edge.parent || edge.parent === "0" || edge.parent === "1") continue;
    const parentNode = nodes[edge.parent];
    if (!parentNode) continue;

    const px = parentNode.x;
    const py = parentNode.y;

    function transformPoint(pt) {
      if (!pt) return pt;
      return { x: px + pt.x, y: py + pt.y };
    }

    for (let i = 0; i < edge.waypoints.length; i++) {
      edge.waypoints[i] = transformPoint(edge.waypoints[i]);
    }
    if (edge.sourcePoint) edge.sourcePoint = transformPoint(edge.sourcePoint);
    if (edge.targetPoint) edge.targetPoint = transformPoint(edge.targetPoint);
  }

  return { nodes, edges };
}

// ─── STYLE HELPERS ───────────────────────────────────────────────────────────

function parseStyle(styleStr) {
  const result = {};
  const flags = [];
  for (const part of styleStr.split(";")) {
    const eq = part.indexOf("=");
    if (eq > 0) {
      result[part.slice(0, eq)] = part.slice(eq + 1);
    } else if (part.trim()) {
      flags.push(part.trim());
    }
  }
  result._flags = flags;
  return result;
}

/** Desaturate a CSS color string by a factor (0 = grayscale, 1 = unchanged). */
function desaturateColor(color, factor) {
  if (!color || color === "none") return color;
  let r, g, b;
  const hex = color.trim();
  if (hex.startsWith("#")) {
    const h = hex.slice(1);
    if (h.length === 3) {
      r = parseInt(h[0]+h[0], 16); g = parseInt(h[1]+h[1], 16); b = parseInt(h[2]+h[2], 16);
    } else if (h.length === 6) {
      r = parseInt(h.slice(0,2), 16); g = parseInt(h.slice(2,4), 16); b = parseInt(h.slice(4,6), 16);
    } else return color;
  } else {
    const m = color.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (m) { r = +m[1]; g = +m[2]; b = +m[3]; }
    else return color;
  }
  const gray = 0.299 * r + 0.587 * g + 0.114 * b;
  r = Math.round(gray + (r - gray) * factor);
  g = Math.round(gray + (g - gray) * factor);
  b = Math.round(gray + (b - gray) * factor);
  return `rgb(${r},${g},${b})`;
}

/** If overlay is active, desaturate a color. Otherwise return as-is. */
function dimColor(color) {
  return overlayEnabled ? desaturateColor(color, 0.3) : color;
}

/** Classify a node by its drawio style */
function nodeType(ps) {
  const flags = ps._flags || [];
  if (flags.includes("group")) return "group";
  if (flags.includes("ellipse")) return "ellipse";
  if (flags.includes("text")) {
    const hasStroke = ps.strokeColor && ps.strokeColor !== "none";
    const hasFill = ps.fillColor && ps.fillColor !== "none"
      && ps.fillColor.toLowerCase() !== "#ffffff" && ps.fillColor.toLowerCase() !== "#fff"
      && ps.fillColor.toLowerCase() !== "#f5f5f5";
    if (hasStroke || hasFill) return "rect";
    return "text";
  }
  if (flags.includes("image")) return "image";
  if (ps.fillColor === "none" && ps.dashed === "1") return "dashed-group";
  if (ps.shape === "flexArrow") return "arrow-shape";
  return "rect";
}

// ─── TEXT HELPERS ─────────────────────────────────────────────────────────────

/** Strip HTML tags from a value string, preserving line breaks.
 *  Converts <sub> and <sup> to Unicode subscript/superscript characters. */
function htmlToPlainText(html) {
  if (!html) return "";

  const subMap = { '0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉',
                   '+':'₊','-':'₋','=':'₌','(':'₍',')':'₎',
                   'a':'ₐ','e':'ₑ','h':'ₕ','i':'ᵢ','j':'ⱼ','k':'ₖ','l':'ₗ','m':'ₘ','n':'ₙ',
                   'o':'ₒ','p':'ₚ','r':'ᵣ','s':'ₛ','t':'ₜ','u':'ᵤ','v':'ᵥ','x':'ₓ' };
  const supMap = { '0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹',
                   '+':'⁺','-':'⁻','=':'⁼','(':'⁽',')':'⁾',
                   'a':'ᵃ','b':'ᵇ','c':'ᶜ','d':'ᵈ','e':'ᵉ','f':'ᶠ','g':'ᵍ','h':'ʰ','i':'ⁱ',
                   'j':'ʲ','k':'ᵏ','l':'ˡ','m':'ᵐ','n':'ⁿ','o':'ᵒ','p':'ᵖ','r':'ʳ','s':'ˢ',
                   't':'ᵗ','u':'ᵘ','v':'ᵛ','w':'ʷ','x':'ˣ','y':'ʸ','z':'ᶻ' };

  function toUnicode(text, map) {
    return text.replace(/./g, ch => map[ch] || ch);
  }

  function convertSubSup(s, tag, map) {
    return s.replace(new RegExp('<' + tag + '>([\\s\\S]*?)</' + tag + '>', 'gi'), (_, inner) => {
      const plain = inner.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim();
      return toUnicode(plain, map);
    });
  }

  let s = html;
  s = s.replace(/<[^>]+font-size:\s*0px[^>]*>.*?<\/[^>]+>/gi, "");
  s = convertSubSup(s, 'sub', subMap);
  s = convertSubSup(s, 'sup', supMap);
  s = s.replace(/<font[^>]+font-size:\s*([0-9]+)px[^>]*>([\s\S]*?)<\/font>/gi, (match, size, inner) => {
    const sz = parseInt(size);
    const plain = inner.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim();
    if (sz > 0 && sz <= 9 && plain.length <= 5) {
      return toUnicode(plain, subMap);
    }
    return match;
  });

  return s
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<div[^>]*>/gi, "\n")
    .replace(/<\/div>/gi, "\n")
    .replace(/<\/p>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#xa;/g, "\n")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

/** Extract the outermost inline font color from HTML value. */
function extractInlineFontColor(html) {
  if (!html) return null;
  const cleaned = html.replace(/<[^>]+font-size:\s*0px[^>]*>.*?<\/[^>]+>/gi, "");
  const m = cleaned.match(/^<font\s+color="([^"]+)">/i)
         || cleaned.match(/^<font\s+style="[^"]*color:\s*([^;"]+)/i);
  return m ? m[1] : null;
}

/** Extract per-line colors from HTML with inline font color tags. */
function extractPerLineColors(html) {
  if (!html) return {};
  const colors = {};
  const cleaned = html.replace(/<[^>]+font-size:\s*0px[^>]*>.*?<\/[^>]+>/gi, "");
  const segments = cleaned.split(/<br\s*\/?>|<div[^>]*>|<\/div>|<\/p>/gi);
  let lineIdx = 0;
  for (const seg of segments) {
    const stripped = seg.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim();
    if (!stripped) continue;
    const colorMatches = [...seg.matchAll(/(?<!-)(?<!ground-)color:\s*([^;"<]+)/gi),
                          ...seg.matchAll(/\bcolor="([^"]+)"/gi)];
    if (colorMatches.length > 0) {
      colors[lineIdx] = colorMatches[colorMatches.length - 1][1].trim();
    }
    lineIdx++;
  }
  return colors;
}

// ─── SVG HELPERS ─────────────────────────────────────────────────────────────

const _measureCanvas = document.createElement("canvas").getContext("2d");
function measureTextWidth(text, font) {
  _measureCanvas.font = font;
  return _measureCanvas.measureText(text).width;
}

function svgEl(tag, attrs = {}, text = null) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== null) el.textContent = text;
  return el;
}

// ─── SVG RENDERING FROM DRAWIO ───────────────────────────────────────────────

function renderFromDrawio() {
  const parser = new DOMParser();
  const doc = parser.parseFromString(drawioXml, "text/xml");
  const { nodes, edges } = parseDrawioNodes(doc);

  const svg = document.getElementById("pathway");
  svg.innerHTML = "";
  nodeAnalyteMap = [];

  // Compute bounding box across all nodes
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of Object.values(nodes)) {
    minX = Math.min(minX, n.x);
    minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x + n.w);
    maxY = Math.max(maxY, n.y + n.h);
  }
  // Include edge waypoints and floating endpoints in bounds
  for (const e of edges) {
    for (const wp of e.waypoints) {
      minX = Math.min(minX, wp.x); minY = Math.min(minY, wp.y);
      maxX = Math.max(maxX, wp.x); maxY = Math.max(maxY, wp.y);
    }
    for (const pt of [e.sourcePoint, e.targetPoint]) {
      if (pt) {
        minX = Math.min(minX, pt.x); minY = Math.min(minY, pt.y);
        maxX = Math.max(maxX, pt.x); maxY = Math.max(maxY, pt.y);
      }
    }
  }

  if (!isFinite(minX)) { minX = 0; minY = 0; maxX = 960; maxY = 700; }
  const PAD = 40;
  minX -= PAD; minY -= PAD; maxX += PAD; maxY += PAD;
  const W = maxX - minX;
  const H = maxY - minY;

  // Offset all coordinates so the diagram starts at (0,0)
  const ox = -minX, oy = -minY;
  for (const n of Object.values(nodes)) { n.x += ox; n.y += oy; }
  for (const e of edges) {
    for (const wp of e.waypoints) { wp.x += ox; wp.y += oy; }
    if (e.sourcePoint) { e.sourcePoint.x += ox; e.sourcePoint.y += oy; }
    if (e.targetPoint) { e.targetPoint.x += ox; e.targetPoint.y += oy; }
  }

  svg.setAttribute("width", W);
  svg.setAttribute("height", H);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  // Defs for arrowheads (color-keyed for per-edge colors)
  const defs = svgEl("defs");
  const markerColors = new Set(["#666", "#999", "#aaa"]);
  for (const e of edges) {
    const ps = parseStyle(e.style);
    if (ps.strokeColor) markerColors.add(ps.strokeColor);
  }
  for (const rawColor of markerColors) {
    const color = dimColor(rawColor);
    const safeId = "arrow-" + rawColor.replace("#", "");
    const marker = svgEl("marker", {
      id: safeId, markerWidth: "8", markerHeight: "8", refX: "6", refY: "3", orient: "auto"
    });
    marker.appendChild(svgEl("path", { d: "M0,0 L0,6 L8,3 z", fill: color }));
    defs.appendChild(marker);

    const openId = "arrow-open-" + rawColor.replace("#", "");
    const openMarker = svgEl("marker", {
      id: openId, markerWidth: "8", markerHeight: "8", refX: "6", refY: "3", orient: "auto"
    });
    openMarker.appendChild(svgEl("path", {
      d: "M1,1 L7,3 L1,5", fill: "none", stroke: color, "stroke-width": "1"
    }));
    defs.appendChild(openMarker);

    const biId = "arrow-bi-" + rawColor.replace("#", "");
    const biMarker = svgEl("marker", {
      id: biId, markerWidth: "8", markerHeight: "8", refX: "2", refY: "3", orient: "auto-start-reverse"
    });
    biMarker.appendChild(svgEl("path", { d: "M0,0 L0,6 L8,3 z", fill: color }));
    defs.appendChild(biMarker);
  }
  svg.appendChild(defs);

  // Render layers: groups → edges → nodes
  for (const [id, n] of Object.entries(nodes)) {
    const ps = parseStyle(n.style);
    const nt = nodeType(ps);
    if (nt === "group" || nt === "dashed-group") {
      drawGroup(svg, n, ps, nt);
    }
  }

  for (const edge of edges) {
    drawEdge(svg, edge, nodes);
  }

  for (const [id, n] of Object.entries(nodes)) {
    const ps = parseStyle(n.style);
    const nt = nodeType(ps);
    if (nt === "text") {
      drawTextNode(svg, id, n, ps);
    } else if (nt === "ellipse") {
      drawEllipseNode(svg, id, n, ps);
    } else if (nt === "rect" || nt === "arrow-shape") {
      drawRectNode(svg, id, n, ps);
    }
  }

  if (overlayEnabled) applyOverlay(svg);

  // Resize SVG to fit all rendered content
  requestAnimationFrame(() => {
    const bbox = svg.getBBox();
    if (bbox.width > 0 && bbox.height > 0) {
      const pad = 20;
      const vx = bbox.x - pad, vy = bbox.y - pad;
      const vw = bbox.width + pad * 2, vh = bbox.height + pad * 2;
      svg.setAttribute("viewBox", `${vx} ${vy} ${vw} ${vh}`);
      svg.setAttribute("width", vw);
      svg.setAttribute("height", vh);
    }
  });
}

// ─── OVERLAY RENDERING ────────────────────────────────────────────────────────

function applyOverlay(svg) {
  const overlayG = svgEl("g", { class: "overlay-layer" });

  for (const { g, label, node } of nodeAnalyteMap) {
    const { score, hasData } = getOverlayScore(label);
    const isNoData = !hasData || score === null;
    const color = isNoData ? NODATA_COLOR : scoreToColor(score);
    const abnormality = score !== null ? Math.abs(score - 0.5) * 2 : 0;

    const pad = 8;
    const ring = svgEl("rect", {
      x: node.x - pad,
      y: node.y - pad,
      width: node.w + pad * 2,
      height: node.h + pad * 2,
      rx: 8,
      fill: color,
      opacity: isNoData ? "0.1" : (0.22 + 0.25 * abnormality).toFixed(2),
      stroke: color,
      "stroke-width": isNoData ? 1 : (2 + 2.5 * abnormality).toFixed(1),
      "stroke-opacity": isNoData ? "0.25" : (0.5 + 0.5 * abnormality).toFixed(2),
      class: "overlay-ring",
    });
    overlayG.appendChild(ring);

  }

  // Cofactor overlays: scan text nodes for analyte substrings
  const cofactorNames = new Set([
    "Fe", "Fe²⁺", "Fe³⁺", "Fe2+", "Fe3+",
    "Cu", "Cu²⁺", "Cu2+",
    "Zn", "Zn²⁺", "Zn2+", "Zn₂₊",
    "Mg", "Mg²⁺", "Mg2+", "Mg₂₊",
    "Mn", "Mn²⁺", "Mn2+",
    "Ca", "Ca²⁺", "Ca2+",
    "Se",
    "FAD", "FMN", "NAD⁺", "NAD+", "NADH", "NADP", "NADPH",
    "P5P", "TPP", "BH4", "BH₄",
    "CoQ10", "Folate", "Riboflavin", "Thiamine", "Cobalamin",
    "Ascorbate", "Glutathione", "GSH",
  ]);

  const mappedGroups = new Set(nodeAnalyteMap.map(e => e.g));
  const textEls = svg.querySelectorAll("text");

  for (const textEl of textEls) {
    const parentG = textEl.closest("g.node-group");
    if (parentG && mappedGroups.has(parentG)) continue;

    const content = textEl.textContent.trim();
    if (!content) continue;

    const sortedTokens = [...cofactorNames].sort((a, b) => b.length - a.length);
    const coveredRanges = [];
    for (const token of sortedTokens) {
      const idx = content.indexOf(token);
      if (idx === -1) continue;
      if (idx > 0 && /[a-zA-Z]/.test(content[idx - 1])) continue;
      const afterIdx = idx + token.length;
      if (afterIdx < content.length && /[a-zA-Z]/.test(content[afterIdx])) continue;

      const tokenEnd = idx + token.length;
      if (coveredRanges.some(r => idx < r.end && tokenEnd > r.start)) continue;

      const analyteLabel = resolveAnalyteLabel(token);
      if (!analyteLabel) continue;
      const { score, hasData } = getOverlayScore(analyteLabel);
      if (!hasData || score === null) continue;

      coveredRanges.push({ start: idx, end: tokenEnd });

      const color = scoreToColor(score);
      const abnormality = Math.abs(score - 0.5) * 2;
      const fontSize = parseFloat(textEl.getAttribute("font-size")) || 11;

      try {
        const startPos = textEl.getStartPositionOfChar(idx);
        const tokenLen = textEl.getSubStringLength(idx, token.length);
        const pad = 2;

        const rect = svgEl("rect", {
          x: startPos.x - pad,
          y: startPos.y - fontSize * 0.85,
          width: tokenLen + pad * 2,
          height: fontSize * 1.2 + pad,
          rx: 3,
          fill: color,
          opacity: (0.25 + 0.25 * abnormality).toFixed(2),
          style: "cursor:pointer",
        });
        rect.addEventListener("click", () => openPanel(analyteLabel));

        const parentG = textEl.closest("g[transform]");
        if (parentG) {
          const wrapper = svgEl("g", { transform: parentG.getAttribute("transform") });
          wrapper.appendChild(rect);
          overlayG.appendChild(wrapper);
        } else {
          overlayG.appendChild(rect);
        }
      } catch (e) {
        // getStartPositionOfChar can throw if index is out of range
      }
    }
  }

  svg.appendChild(overlayG);
}

// ─── NODE DRAWING ─────────────────────────────────────────────────────────────

function applyNodeTransform(g, node, ps) {
  const transforms = [];
  const totalRotation = nodeRotation(node, ps);
  if (totalRotation) {
    const cx = node.x + node.w / 2;
    const cy = node.y + node.h / 2;
    transforms.push(`rotate(${totalRotation} ${cx} ${cy})`);
  }
  if (transforms.length) g.setAttribute("transform", transforms.join(" "));
}

function shapeOpacity(ps) {
  return ps.opacity ? parseFloat(ps.opacity) / 100 : 1;
}

function textOpacity(ps) {
  if (ps.textOpacity) return parseFloat(ps.textOpacity) / 100;
  return 1;
}

function drawGroup(svg, node, ps, nt) {
  const g = svgEl("g");
  applyNodeTransform(g, node, ps);
  const color = dimColor(ps.strokeColor || "#888");
  const isDashed = nt === "dashed-group" || ps.dashed === "1";

  if (ps.strokeColor && ps.strokeColor !== "none") {
    const attrs = {
      x: node.x, y: node.y, width: node.w, height: node.h, rx: 6,
      fill: dimColor(ps.fillColor || "none"), stroke: color,
      "stroke-width": ps.strokeWidth || 1
    };
    if (isDashed) attrs["stroke-dasharray"] = "8 4";
    const sOp = shapeOpacity(ps);
    if (sOp < 1) attrs["opacity"] = sOp;
    g.appendChild(svgEl("rect", attrs));
  }

  if (node.value) {
    const text = htmlToPlainText(node.value);
    const vAlign = ps.verticalAlign || "bottom";
    let ly = vAlign === "bottom" ? node.y + node.h - 8
           : vAlign === "top" ? node.y + 16
           : node.y + node.h / 2 + 4;
    const textAttrs = {
      x: node.x + node.w / 2, y: ly,
      "text-anchor": "middle", fill: dimColor(ps.fontColor || color),
      "font-size": Math.min(parseFloat(ps.fontSize) || 12, 24), "font-weight": 700,
      "letter-spacing": "0.06em"
    };
    const tOp = textOpacity(ps);
    if (tOp < 1) textAttrs["opacity"] = tOp;
    g.appendChild(svgEl("text", textAttrs, text));
  }
  svg.appendChild(g);
}

function drawTextNode(svg, id, node, ps) {
  const text = htmlToPlainText(node.value);
  if (!text) return;

  const g = svgEl("g", { class: "node-group" });
  const analyteLabel = resolveAnalyteLabel(text);
  const data = analyteLabel ? { label: analyteLabel, ...ANALYTE_DATA[analyteLabel] } : null;
  if (data) {
    g.style.cursor = "pointer";
    g.addEventListener("click", () => openPanel(analyteLabel));
    nodeAnalyteMap.push({ g, label: analyteLabel, node });
  }

  const fontSize = parseFloat(ps.fontSize) || 11;
  const inlineColor = extractInlineFontColor(node.value);
  const fontColor = dimColor(inlineColor || ps.fontColor || "#000");
  const bold = ps.fontStyle === "1" || ps.fontStyle === "3";
  const align = ps.align || "center";
  const vAlign = ps.verticalAlign || "middle";

  const lines = text.split("\n").filter(l => l.trim());
  const lineH = fontSize * 1.2;

  let startY;
  if (vAlign === "top") {
    startY = node.y + fontSize;
  } else if (vAlign === "bottom") {
    startY = node.y + node.h - (lines.length - 1) * lineH;
  } else {
    startY = node.y + node.h / 2 - ((lines.length - 1) * lineH) / 2 + fontSize * 0.35;
  }

  let tx, anchor;
  if (align === "left") {
    tx = node.x + 2;
    anchor = "start";
  } else if (align === "right") {
    tx = node.x + node.w - 2;
    anchor = "end";
  } else {
    tx = node.x + node.w / 2;
    anchor = "middle";
  }

  applyNodeTransform(g, node, ps);

  const tOp = textOpacity(ps);
  const perLineColors = extractPerLineColors(node.value);

  for (let i = 0; i < lines.length; i++) {
    const textAttrs = {
      x: tx, y: startY + i * lineH,
      "text-anchor": anchor,
      fill: dimColor(perLineColors[i]) || fontColor,
      "font-size": fontSize,
      "font-weight": bold ? 700 : 400
    };
    if (tOp < 1) textAttrs["opacity"] = tOp;
    g.appendChild(svgEl("text", textAttrs, lines[i]));
  }

  svg.appendChild(g);
}

function drawEllipseNode(svg, id, node, ps) {
  const g = svgEl("g", { class: "node-group" });
  applyNodeTransform(g, node, ps);
  const text = htmlToPlainText(node.value);
  const analyteLabel = resolveAnalyteLabel(text);
  const data = analyteLabel ? { label: analyteLabel, ...ANALYTE_DATA[analyteLabel] } : null;
  if (data) {
    g.style.cursor = "pointer";
    g.addEventListener("click", () => openPanel(analyteLabel));
    nodeAnalyteMap.push({ g, label: analyteLabel, node });
  }

  const cx = node.x + node.w / 2;
  const cy = node.y + node.h / 2;
  const fill = ps.fillColor || "none";
  const stroke = ps.strokeColor || "#666";
  const dashed = ps.dashed === "1";

  const attrs = {
    cx, cy, rx: node.w / 2, ry: node.h / 2,
    fill: fill === "none" ? "none" : dimColor(fill),
    stroke: stroke === "none" ? "none" : dimColor(stroke),
    "stroke-width": ps.strokeWidth || 1
  };
  if (dashed) attrs["stroke-dasharray"] = "6 4";
  const sOp = shapeOpacity(ps);
  if (sOp < 1) attrs["opacity"] = sOp;
  g.appendChild(svgEl("ellipse", attrs));

  if (text) {
    const fontSize = parseFloat(ps.fontSize) || 14;
    const textAttrs = {
      x: cx, y: cy + fontSize * 0.35,
      "text-anchor": "middle",
      fill: dimColor(ps.fontColor || "#000"),
      "font-size": fontSize,
      "font-weight": ps.fontStyle === "1" ? 700 : 400
    };
    const tOp = textOpacity(ps);
    if (tOp < 1) textAttrs["opacity"] = tOp;
    g.appendChild(svgEl("text", textAttrs, text));
  }

  svg.appendChild(g);
}

function drawRectNode(svg, id, node, ps) {
  const g = svgEl("g", { class: "node-group" });
  applyNodeTransform(g, node, ps);
  const text = htmlToPlainText(node.value);
  const analyteLabel = resolveAnalyteLabel(text);
  const data = analyteLabel ? { label: analyteLabel, ...ANALYTE_DATA[analyteLabel] } : null;
  if (data) {
    g.style.cursor = "pointer";
    g.addEventListener("click", () => openPanel(analyteLabel));
    nodeAnalyteMap.push({ g, label: analyteLabel, node });
  }

  const fill = ps.fillColor || "#f5f5f5";
  const stroke = ps.strokeColor || "#aaa";
  const dashed = ps.dashed === "1";
  const rounded = ps.rounded === "1" ? 10 : 3;

  const attrs = {
    x: node.x, y: node.y, width: node.w, height: node.h,
    rx: rounded,
    fill: fill === "none" ? "none" : dimColor(fill),
    stroke: stroke === "none" ? "none" : dimColor(stroke),
    "stroke-width": ps.strokeWidth || 1,
    class: "node-rect"
  };
  if (dashed) attrs["stroke-dasharray"] = "6 4";
  const sOp = shapeOpacity(ps);
  if (sOp < 1) attrs["opacity"] = sOp;
  g.appendChild(svgEl("rect", attrs));

  if (text) {
    const isPromotedText = (ps._flags || []).includes("text");
    let fontSize = parseFloat(ps.fontSize) || (isPromotedText ? 11 : 14);
    const bold = ps.fontStyle === "1" || ps.fontStyle === "3";
    const fontWeight = bold ? 700 : 400;

    const baseSpacing = parseFloat(ps.spacing) || 2;
    const spacingL = baseSpacing + (parseFloat(ps.spacingLeft) || 0);
    const spacingR = baseSpacing + (parseFloat(ps.spacingRight) || 0);
    const availW = node.w - spacingL - spacingR;

    let lines = text.split("\n").filter(l => l.trim());
    const shouldWrap = ps.whiteSpace === "wrap" || isPromotedText;

    function wrapLines(inputLines, fs) {
      if (!shouldWrap) return inputLines;
      const font = `${bold ? 'bold ' : ''}${fs}px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`;
      const wrapped = [];
      for (const line of inputLines) {
        const words = line.split(/\s+/);
        if (words.length <= 1) { wrapped.push(line); continue; }
        let cur = words[0];
        for (let w = 1; w < words.length; w++) {
          const test = cur + " " + words[w];
          if (measureTextWidth(test, font) > availW) {
            wrapped.push(cur);
            cur = words[w];
          } else {
            cur = test;
          }
        }
        wrapped.push(cur);
      }
      return wrapped;
    }

    lines = wrapLines(lines, fontSize);

    const spacingT = baseSpacing + (parseFloat(ps.spacingTop) || 0);
    const spacingB = baseSpacing + (parseFloat(ps.spacingBottom) || 0);
    const availH = node.h - spacingT - spacingB;
    const maxIter = 20;
    for (let iter = 0; iter < maxIter && fontSize > 4; iter++) {
      const lineH = fontSize * 1.2;
      const totalTextH = lines.length * lineH;
      const font = `${bold ? 'bold ' : ''}${fontSize}px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`;
      const maxLineW = Math.max(...lines.map(l => measureTextWidth(l, font)));
      if (totalTextH <= availH && maxLineW <= availW) break;
      fontSize *= 0.9;
      lines = wrapLines(text.split("\n").filter(l => l.trim()), fontSize);
    }

    const lineH = fontSize * 1.2;
    const startY = node.y + node.h / 2 - ((lines.length - 1) * lineH) / 2 + fontSize * 0.35;

    const tOp = textOpacity(ps);
    const inlineColor = extractInlineFontColor(node.value);
    const perLineColors = extractPerLineColors(node.value);
    const defaultFill = dimColor(inlineColor || ps.fontColor || "#000");
    for (let i = 0; i < lines.length; i++) {
      const textAttrs = {
        x: node.x + node.w / 2, y: startY + i * lineH,
        "text-anchor": "middle",
        fill: dimColor(perLineColors[i]) || defaultFill,
        "font-size": fontSize,
        "font-weight": fontWeight,
        class: "node-label"
      };
      if (tOp < 1) textAttrs["opacity"] = tOp;
      g.appendChild(svgEl("text", textAttrs, lines[i]));
    }
  }

  svg.appendChild(g);
}

function drawBadge(g, node, badge) {
  const bs = BADGE_STYLES[badge.type] || BADGE_STYLES.ok;
  const bw = badge.text.length * 6.5 + 10;
  const bh = 18;
  const bx = node.x + (node.w - bw) / 2;
  const by = node.y - bh / 2 - 1;
  g.appendChild(svgEl("rect", { x: bx, y: by, width: bw, height: bh, rx: 4, fill: bs.fill }));
  g.appendChild(svgEl("text", {
    x: bx + bw / 2, y: by + 12,
    "text-anchor": "middle", fill: bs.text, "font-size": 10, "font-weight": 700
  }, badge.text));
}

// ─── EDGE DRAWING ─────────────────────────────────────────────────────────────

function rotatePoint(px, py, cx, cy, angleDeg) {
  if (!angleDeg) return { x: px, y: py };
  const rad = angleDeg * Math.PI / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const dx = px - cx;
  const dy = py - cy;
  return { x: cx + dx * cos - dy * sin, y: cy + dx * sin + dy * cos };
}

function nodeRotation(node, ps) {
  if (ps.rotation !== undefined) return parseFloat(ps.rotation) || 0;
  return node._parentRotation || 0;
}

function nearestBoundaryPoint(node, pt, border) {
  if (border === undefined) {
    const ns = parseStyle(node.style);
    border = (parseFloat(ns.strokeWidth) || 1) / 2 + 1;
  }
  const hw = node.w / 2 + border;
  const hh = node.h / 2 + border;
  const cx = node.x + node.w / 2;
  const cy = node.y + node.h / 2;
  const rot = nodeRotation(node, parseStyle(node.style));

  let localPt = pt;
  if (rot) localPt = rotatePoint(pt.x, pt.y, cx, cy, -rot);

  const dx = localPt.x - cx;
  const dy = localPt.y - cy;

  if (dx === 0 && dy === 0) {
    const p = { x: cx, y: cy - hh };
    return rot ? rotatePoint(p.x, p.y, cx, cy, rot) : p;
  }

  const scaleX = hw / Math.abs(dx || 0.001);
  const scaleY = hh / Math.abs(dy || 0.001);
  const scale = Math.min(scaleX, scaleY);

  const bx = cx + dx * scale;
  const by = cy + dy * scale;
  return rot ? rotatePoint(bx, by, cx, cy, rot) : { x: bx, y: by };
}

function drawEdge(svg, edge, nodes) {
  const ps = parseStyle(edge.style);
  const src = nodes[edge.source];
  const tgt = nodes[edge.target];

  if (!src && !edge.sourcePoint && !tgt && !edge.targetPoint) return;

  const rawColor = ps.strokeColor || "#666";
  const color = dimColor(rawColor);
  const dashed = ps.dashed === "1";
  const curved = ps.curved === "1";
  const endArrow = ps.endArrow || "classic";
  const startArrow = ps.startArrow || "none";
  const hasStartArrow = (startArrow === "block" || startArrow === "classic") &&
                        (ps.startFill !== "0");
  const hasEndArrow = endArrow !== "none";
  const bidir = hasStartArrow && hasEndArrow;

  let x1, y1, x2, y2;

  function connectionPoint(node, fractX, fractY) {
    const cx = node.x + node.w / 2;
    const cy = node.y + node.h / 2;
    const lx = node.x + node.w * fractX;
    const ly = node.y + node.h * fractY;
    const dx = lx - cx, dy = ly - cy;
    const dist = Math.hypot(dx, dy);
    const push = dist > 0.1 ? 1.5 / dist : 0;
    const px = lx + dx * push;
    const py = ly + dy * push;
    const rot = nodeRotation(node, parseStyle(node.style));
    if (rot) {
      return rotatePoint(px, py, cx, cy, rot);
    }
    return { x: px, y: py };
  }

  if (src) {
    if (ps.exitX !== undefined && ps.exitY !== undefined) {
      const cp = connectionPoint(src, parseFloat(ps.exitX), parseFloat(ps.exitY));
      x1 = cp.x; y1 = cp.y;
    } else {
      const firstWp = edge.waypoints.length > 0 ? edge.waypoints[0] : null;
      const tc = firstWp
               || (tgt ? { x: tgt.x + tgt.w / 2, y: tgt.y + tgt.h / 2 }
                       : (edge.targetPoint || { x: src.x + src.w / 2, y: src.y }));
      ({ x: x1, y: y1 } = nearestBoundaryPoint(src, tc));
    }
  } else if (edge.sourcePoint) {
    x1 = edge.sourcePoint.x; y1 = edge.sourcePoint.y;
  } else {
    return;
  }

  if (tgt) {
    if (ps.entryX !== undefined && ps.entryY !== undefined) {
      const cp = connectionPoint(tgt, parseFloat(ps.entryX), parseFloat(ps.entryY));
      x2 = cp.x; y2 = cp.y;
    } else {
      const lastWp = edge.waypoints.length > 0 ? edge.waypoints[edge.waypoints.length - 1] : null;
      const sc = lastWp
               || (src ? { x: src.x + src.w / 2, y: src.y + src.h / 2 }
                       : (edge.sourcePoint || { x: tgt.x + tgt.w / 2, y: tgt.y }));
      ({ x: x2, y: y2 } = nearestBoundaryPoint(tgt, sc));
    }
  } else if (edge.targetPoint) {
    x2 = edge.targetPoint.x; y2 = edge.targetPoint.y;
  } else {
    return;
  }

  // Build path
  let d;
  if (edge.waypoints.length > 0) {
    const pts = [{ x: x1, y: y1 }, ...edge.waypoints, { x: x2, y: y2 }];
    if (curved && pts.length >= 3) {
      d = buildCurvedPath(pts);
    } else {
      d = `M${pts[0].x},${pts[0].y}`;
      for (let i = 1; i < pts.length; i++) d += ` L${pts[i].x},${pts[i].y}`;
    }
  } else if (ps.edgeStyle === "orthogonalEdgeStyle") {
    const eX = parseFloat(ps.exitX ?? 0.5);
    const eY = parseFloat(ps.exitY ?? 0.5);
    const nX = parseFloat(ps.entryX ?? 0.5);
    const nY = parseFloat(ps.entryY ?? 0.5);
    d = buildOrthogonalPath(x1, y1, x2, y2, eX, eY, nX, nY);
  } else {
    d = `M${x1},${y1} L${x2},${y2}`;
  }

  // flexArrow: draw as a thick filled polygon
  if (ps.shape === "flexArrow") {
    const fillColor = dimColor(ps.fillColor || color);
    const arrowW = parseFloat(ps.width) || 15;
    const headW = arrowW * 1.8;
    const headL = arrowW * 1.5;

    const arrowAtStart = (startArrow === "block" || startArrow === "classic") && endArrow === "none";
    let ax1 = x1, ay1 = y1, ax2 = x2, ay2 = y2;
    if (arrowAtStart) {
      ax1 = x2; ay1 = y2; ax2 = x1; ay2 = y1;
    }

    const dx = ax2 - ax1, dy = ay2 - ay1;
    const dist = Math.hypot(dx, dy);
    if (dist >= 1) {
      const ux = dx / dist, uy = dy / dist;
      const px = -uy, py = ux;

      const bodyEnd = Math.max(0, dist - headL);
      const bx = ax1 + ux * bodyEnd, by = ay1 + uy * bodyEnd;

      const hw = arrowW / 2;
      const hhw = headW / 2;
      const points = [
        `${ax1 + px * hw},${ay1 + py * hw}`,
        `${bx + px * hw},${by + py * hw}`,
        `${bx + px * hhw},${by + py * hhw}`,
        `${ax2},${ay2}`,
        `${bx - px * hhw},${by - py * hhw}`,
        `${bx - px * hw},${by - py * hw}`,
        `${ax1 - px * hw},${ay1 - py * hw}`,
      ].join(" ");

      const polyAttrs = { points, fill: fillColor, stroke: color, "stroke-width": 1 };
      if (ps.opacity) polyAttrs["opacity"] = parseFloat(ps.opacity) / 100;
      svg.appendChild(svgEl("polygon", polyAttrs));
    }
  } else {
    // Markers
    const colorKey = rawColor.replace("#", "");
    let markerEnd = null, markerStart = null;

    if (endArrow === "none") {
      markerEnd = null;
    } else if (endArrow === "open") {
      markerEnd = `url(#arrow-open-${colorKey})`;
    } else {
      markerEnd = `url(#arrow-${colorKey})`;
    }

    if (bidir) {
      markerStart = `url(#arrow-bi-${colorKey})`;
      markerEnd = `url(#arrow-bi-${colorKey})`;
    } else if (hasStartArrow && !hasEndArrow) {
      d = reversePath(d);
      markerEnd = `url(#arrow-${colorKey})`;
    }

    const attrs = {
      d, fill: "none", stroke: color,
      "stroke-width": ps.strokeWidth || 1
    };
    if (markerEnd) attrs["marker-end"] = markerEnd;
    if (markerStart) attrs["marker-start"] = markerStart;
    if (dashed) attrs["stroke-dasharray"] = "6 4";
    if (ps.opacity) attrs["opacity"] = parseFloat(ps.opacity) / 100;
    svg.appendChild(svgEl("path", attrs));
  }

  // Edge label
  if (edge.value) {
    const text = htmlToPlainText(edge.value);
    if (!text) return;
    const lines = text.split("\n").filter(l => l.trim());
    if (lines.length === 0) return;

    const allPts = [{ x: x1, y: y1 }, ...edge.waypoints, { x: x2, y: y2 }];
    const fraction = (edge.labelX + 1) / 2;
    let lx, ly;
    ({ x: lx, y: ly } = pathPointAtFraction(allPts, fraction));
    if (edge.labelY) {
      const segIdx = Math.min(Math.max(Math.floor(fraction * (allPts.length - 1)), 0), allPts.length - 2);
      const dx = allPts[segIdx + 1].x - allPts[segIdx].x;
      const dy = allPts[segIdx + 1].y - allPts[segIdx].y;
      const len = Math.hypot(dx, dy) || 1;
      lx += (-dy / len) * edge.labelY;
      ly += (dx / len) * edge.labelY;
    }

    const fontSize = Math.min(parseFloat(ps.fontSize) || 11, 24);
    const fontColor = dimColor(ps.fontColor || "#666");
    const lineH = fontSize * 1.2;

    if (ps.labelBackgroundColor !== "none") {
      const approxW = Math.max(...lines.map(l => l.length)) * fontSize * 0.6 + 8;
      const totalH = lines.length * lineH + 4;
      svg.appendChild(svgEl("rect", {
        x: lx - approxW / 2, y: ly - totalH / 2,
        width: approxW, height: totalH,
        fill: dimColor(ps.labelBackgroundColor || "#f8f9fa"), rx: 2, opacity: "0.85"
      }));
    }

    const startLy = ly - ((lines.length - 1) * lineH) / 2 + fontSize * 0.35;
    for (let i = 0; i < lines.length; i++) {
      svg.appendChild(svgEl("text", {
        x: lx, y: startLy + i * lineH,
        "text-anchor": "middle",
        fill: fontColor, "font-size": fontSize
      }, lines[i]));
    }
  }
}

// ─── PATH HELPERS ─────────────────────────────────────────────────────────────

function reversePath(d) {
  const re = /([MLQC])\s*([\d.\-e,\s]+)/gi;
  const cmds = [];
  let m;
  while ((m = re.exec(d)) !== null) {
    cmds.push({ type: m[1].toUpperCase(), nums: m[2].trim().split(/[\s,]+/).map(Number) });
  }
  if (cmds.length === 0) return d;

  const segments = [];
  let cur = null;
  for (const cmd of cmds) {
    if (cmd.type === "M") {
      cur = { x: cmd.nums[0], y: cmd.nums[1] };
    } else if (cmd.type === "L") {
      const end = { x: cmd.nums[0], y: cmd.nums[1] };
      segments.push({ type: "L", start: cur, end });
      cur = end;
    } else if (cmd.type === "Q") {
      for (let i = 0; i < cmd.nums.length; i += 4) {
        const end = { x: cmd.nums[i + 2], y: cmd.nums[i + 3] };
        segments.push({ type: "Q", start: cur, cp: { x: cmd.nums[i], y: cmd.nums[i + 1] }, end });
        cur = end;
      }
    } else if (cmd.type === "C") {
      for (let i = 0; i < cmd.nums.length; i += 6) {
        const end = { x: cmd.nums[i + 4], y: cmd.nums[i + 5] };
        segments.push({
          type: "C", start: cur,
          cp1: { x: cmd.nums[i], y: cmd.nums[i + 1] },
          cp2: { x: cmd.nums[i + 2], y: cmd.nums[i + 3] }, end
        });
        cur = end;
      }
    }
  }

  segments.reverse();
  let rd = `M${segments[0].end.x},${segments[0].end.y}`;
  for (const seg of segments) {
    if (seg.type === "C") {
      rd += ` C${seg.cp2.x},${seg.cp2.y} ${seg.cp1.x},${seg.cp1.y} ${seg.start.x},${seg.start.y}`;
    } else if (seg.type === "Q") {
      rd += ` Q${seg.cp.x},${seg.cp.y} ${seg.start.x},${seg.start.y}`;
    } else {
      rd += ` L${seg.start.x},${seg.start.y}`;
    }
  }
  return rd;
}

function pathPointAtFraction(pts, frac) {
  if (pts.length < 2) return pts[0] || { x: 0, y: 0 };
  let totalLen = 0;
  const segLens = [];
  for (let i = 1; i < pts.length; i++) {
    const sl = Math.hypot(pts[i].x - pts[i-1].x, pts[i].y - pts[i-1].y);
    segLens.push(sl);
    totalLen += sl;
  }
  let target = totalLen * Math.max(0, Math.min(1, frac)), accum = 0;
  for (let i = 0; i < segLens.length; i++) {
    if (accum + segLens[i] >= target) {
      const t = segLens[i] > 0 ? (target - accum) / segLens[i] : 0;
      return {
        x: pts[i].x + (pts[i+1].x - pts[i].x) * t,
        y: pts[i].y + (pts[i+1].y - pts[i].y) * t
      };
    }
    accum += segLens[i];
  }
  return { x: pts[pts.length-1].x, y: pts[pts.length-1].y };
}

function pathMidpoint(pts) {
  let totalLen = 0;
  const segLens = [];
  for (let i = 1; i < pts.length; i++) {
    const sl = Math.hypot(pts[i].x - pts[i-1].x, pts[i].y - pts[i-1].y);
    segLens.push(sl);
    totalLen += sl;
  }
  let target = totalLen / 2, accum = 0;
  for (let i = 0; i < segLens.length; i++) {
    if (accum + segLens[i] >= target) {
      const t = segLens[i] > 0 ? (target - accum) / segLens[i] : 0;
      return {
        x: pts[i].x + (pts[i+1].x - pts[i].x) * t,
        y: pts[i].y + (pts[i+1].y - pts[i].y) * t
      };
    }
    accum += segLens[i];
  }
  return { x: (pts[0].x + pts[pts.length-1].x) / 2, y: (pts[0].y + pts[pts.length-1].y) / 2 };
}

function buildCurvedPath(pts) {
  if (pts.length === 2) return `M${pts[0].x},${pts[0].y} L${pts[1].x},${pts[1].y}`;
  let d = `M${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length - 2; i++) {
    const p0 = pts[i];
    const p1 = pts[i + 1];
    const ix = (p0.x + p1.x) / 2;
    const iy = (p0.y + p1.y) / 2;
    d += ` Q${p0.x},${p0.y} ${ix},${iy}`;
  }
  const pn2 = pts[pts.length - 2];
  const pn1 = pts[pts.length - 1];
  d += ` Q${pn2.x},${pn2.y} ${pn1.x},${pn1.y}`;
  return d;
}

function buildOrthogonalPath(x1, y1, x2, y2, exitX, exitY, entryX, entryY) {
  const exitDir = getDirection(exitX, exitY);
  const entryDir = getDirection(entryX, entryY);
  const GAP = 20;

  if (exitDir === "right" && entryDir === "left") {
    const mx = (x1 + x2) / 2;
    return `M${x1},${y1} L${mx},${y1} L${mx},${y2} L${x2},${y2}`;
  }
  if (exitDir === "bottom" && entryDir === "top") {
    const my = (y1 + y2) / 2;
    return `M${x1},${y1} L${x1},${my} L${x2},${my} L${x2},${y2}`;
  }
  if (exitDir === "top" && entryDir === "bottom") {
    const my = (y1 + y2) / 2;
    return `M${x1},${y1} L${x1},${my} L${x2},${my} L${x2},${y2}`;
  }
  if (exitDir === "left" && entryDir === "left") {
    const leftX = Math.min(x1, x2) - GAP;
    return `M${x1},${y1} L${leftX},${y1} L${leftX},${y2} L${x2},${y2}`;
  }
  if (exitDir === "right" && (entryDir === "bottom" || entryDir === "top")) {
    return `M${x1},${y1} L${x2},${y1} L${x2},${y2}`;
  }
  if (exitDir === "bottom" && entryDir === "bottom") {
    const botY = Math.max(y1, y2) + GAP;
    return `M${x1},${y1} L${x1},${botY} L${x2},${botY} L${x2},${y2}`;
  }
  if (exitDir === "right" || exitDir === "left") {
    if (Math.abs(y1 - y2) < 0.5) return `M${x1},${y1} L${x2},${y2}`;
    return `M${x1},${y1} L${x2},${y1} L${x2},${y2}`;
  }
  if (Math.abs(x1 - x2) < 0.5) return `M${x1},${y1} L${x2},${y2}`;
  return `M${x1},${y1} L${x1},${y2} L${x2},${y2}`;
}

function getDirection(px, py) {
  if (px >= 0.9) return "right";
  if (px <= 0.1) return "left";
  if (py >= 0.9) return "bottom";
  if (py <= 0.1) return "top";
  if (px > 0.5) return "right";
  if (px < 0.5) return "left";
  if (py > 0.5) return "bottom";
  return "top";
}
