import json
import re
import math
import networkx as nx

# ========================
# CONFIGURATION
# ========================
GRAPH_FILE   = "graph_frozen.graphml"
OUT_HTML     = "graph_d3.html"

NODE_SIZE_MULT  = 0.8
NODE_SIZE_ADD   = 1.0
NODE_SIZE_POWER = 1.05
LABEL_SCALE     = 0.35
MIN_FONT_SIZE   = 8

ATTR_SIZE   = ["SizeGephi", "size", "Size", "viz:size", "viz_size"]
ATTR_LABEL  = ["label", "Label", "name", "Name"]
ATTR_TYPE   = ["type", "Type", "node_type", "category"]
ATTR_BIBTEX = ["bibtex", "Bibtex", "BIBTEX"]

COLOR_SUBTOPIC = "#3CB371"
COLOR_AUTHOR   = "#FF7AA2"
COLOR_OTHER    = "#9E9E9E"

# ========================
# HELPERS
# ========================
def pick_attr(attrs, candidates):
    for c in candidates:
        if attrs.get(c): return attrs[c]
    lower_keys = {k.lower(): k for k in attrs}
    for c in candidates:
        if c.lower() in lower_keys: return attrs[lower_keys[c.lower()]]
    return None

def _as_float(v):
    try:
        if v is None: return None
        s = str(v).strip().replace(",", ".")
        return float(s) if s else None
    except: return None

def extract_xy(attrs):
    pairs = [("x", "y"), ("X", "Y"), ("viz:position.x", "viz:position.y"), ("pos_x", "pos_y")]
    for kx, ky in pairs:
        if attrs.get(kx) and attrs.get(ky):
            return _as_float(attrs[kx]), _as_float(attrs[ky])
    return None

# ========================
# CITATION PARSER
# ========================
def clean_tex(text):
    if not text: return ""
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_field(entry_str, keys):
    if isinstance(keys, str): keys = [keys]
    for key in keys:
        pattern = rf'{key}\s*=\s*[\{{"](.*?)(?<!\\)[\}}"]'
        match = re.search(pattern, entry_str, re.IGNORECASE | re.DOTALL)
        if match:
            return clean_tex(match.group(1))
    return ""

def format_apa_html(raw_bibtex):
    if not raw_bibtex or str(raw_bibtex).lower() == "none":
        return "", "", []
    entries = str(raw_bibtex).split(" || ")
    html_output = ""
    search_texts = []
    years = []
    for entry in entries:
        if not entry.strip(): continue
        author  = get_field(entry, "author")
        year    = get_field(entry, ["year", "date"])
        title   = get_field(entry, "title")
        journal = get_field(entry, ["journal", "booktitle", "series"])
        volume  = get_field(entry, "volume")
        issue   = get_field(entry, "number")
        pages   = get_field(entry, "pages")
        doi     = get_field(entry, "doi")

        # plain text for APA copy
        plain = f"{author} ({year}). {title}. {journal}"
        if volume: plain += f", {volume}"
        if issue:  plain += f"({issue})"
        if pages:  plain += f", {pages}"
        if doi:
            clean_doi = doi.replace("https://doi.org/", "")
            plain += f". https://doi.org/{clean_doi}"

        citation = f"<span class='apa-author'>{author}</span>"
        if year: citation += f" ({year})"
        citation += ". "
        if title: citation += f"<span class='apa-title'>{title}</span>. "
        if journal:
            citation += f"<i class='apa-journal'>{journal}</i>"
            if volume: citation += f", <i>{volume}</i>"
            if issue:  citation += f"({issue})"
            if pages:  citation += f", {pages}"
            citation += ". "
        if doi:
            clean_doi = doi.replace("https://doi.org/", "")
            link = f"https://doi.org/{clean_doi}"
            citation += f" <a href='{link}' target='_blank' class='apa-doi'>{link}</a>"

        # copy button per entry
        plain_escaped = plain.replace("'", "\\'").replace("\n", " ")
        citation = f"<div class='apa-entry'>{citation}<button class='copy-btn' onclick=\"copyAPA('{plain_escaped}')\">Copy APA</button></div>"
        html_output += citation
        search_texts.append(f"{author} {year} {title} {journal}")
        try:
            y = int(year[:4]) if year else 0
            if y > 0: years.append(y)
        except: pass

    return html_output, " | ".join(search_texts), years

# ========================
# READ GRAPH & BUILD JSON
# ========================
G = nx.read_graphml(GRAPH_FILE)

nodes = []
all_years = []

for n, attrs in G.nodes(data=True):
    nid = str(n)
    label = str(pick_attr(attrs, ATTR_LABEL) or nid)
    ntype = str(pick_attr(attrs, ATTR_TYPE) or "")

    raw_size = _as_float(pick_attr(attrs, ATTR_SIZE)) or 10.0
    radius = (max(0, raw_size)**NODE_SIZE_POWER) * NODE_SIZE_MULT + NODE_SIZE_ADD
    font_size = max(MIN_FONT_SIZE, int(math.log1p(radius) * LABEL_SCALE * 10))

    xy = extract_xy(attrs)
    x = xy[0] if xy else 0.0
    y = -xy[1] if xy else 0.0

    if "subtopic" in ntype.lower(): color = COLOR_SUBTOPIC
    elif "author" in ntype.lower(): color = COLOR_AUTHOR
    else: color = COLOR_OTHER

    raw_bib = pick_attr(attrs, ATTR_BIBTEX)
    apa_html, search_text, years = format_apa_html(raw_bib)
    all_years.extend(years)
    min_year = min(years) if years else None
    max_year = max(years) if years else None

    nodes.append({
        "id": nid,
        "label": label,
        "type": ntype,
        "x": x,
        "y": y,
        "radius": radius,
        "fontSize": font_size,
        "color": color,
        "apa": apa_html,
        "searchText": search_text,
        "minYear": min_year,
        "maxYear": max_year,
    })

edges = []
for u, v in G.edges():
    edges.append({"source": str(u), "target": str(v)})

graph_data = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)

global_min_year = min(all_years) if all_years else 1990
global_max_year = max(all_years) if all_years else 2025
n_nodes = len(nodes)
n_edges = len(edges)

# ========================
# GENERATE HTML
# ========================
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Graph</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #111; overflow: hidden; font-family: 'Segoe UI', sans-serif; }}
  svg {{ width: 100vw; height: 100vh; cursor: grab; }}
  svg:active {{ cursor: grabbing; }}

  .edge {{ stroke: #444; stroke-width: 1px; transition: opacity 0.2s; }}
  .edge.dimmed {{ opacity: 0.05; }}

  .node-label {{ fill: white; text-anchor: middle; dominant-baseline: middle; pointer-events: none; user-select: none; }}
  .node.dimmed circle {{ opacity: 0.08; }}
  .node.dimmed text   {{ opacity: 0.08; }}
  .node-highlight circle {{ stroke: #FF7AA2 !important; stroke-width: 3px !important; }}

  /* ── Tooltip ── */
  #tooltip {{
    position: fixed; pointer-events: none; z-index: 3000;
    background: rgba(18,18,18,0.95); border: 1px solid rgba(255,255,255,0.15);
    border-radius: 6px; padding: 8px 12px; color: #eee; font-size: 12px;
    max-width: 220px; line-height: 1.4; display: none;
    box-shadow: 0 2px 8px rgba(0,0,0,0.5);
  }}

  /* ── Left controls panel ── */
  #controls {{
    position: fixed; top: 16px; left: 16px; z-index: 2000;
    display: flex; flex-direction: column; gap: 10px; width: 300px;
  }}

  /* Search */
  #searchbox {{ display: flex; flex-direction: column; gap: 6px; }}
  #searchbox input {{
    width: 100%; padding: 9px 14px; border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.2); background: rgba(20,20,20,0.95);
    color: #eee; font-size: 14px; outline: none;
  }}
  #searchbox input:focus {{ border-color: #FF7AA2; }}
  #search-results {{
    background: rgba(18,18,18,0.97); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px; max-height: 260px; overflow-y: auto; display: none;
  }}
  .search-result-item {{
    padding: 8px 14px; cursor: pointer; font-size: 13px; color: #ddd;
    border-bottom: 1px solid rgba(255,255,255,0.05); line-height: 1.4;
  }}
  .search-result-item:hover {{ background: rgba(255,122,162,0.15); color: #fff; }}
  .sr-type  {{ font-size: 10px; color: #888; text-transform: uppercase; margin-bottom: 2px; }}
  .sr-label {{ font-weight: 600; }}
  .sr-sub   {{ font-size: 11px; color: #aaa; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .no-results {{ padding: 10px 14px; color: #888; font-size: 13px; }}

  /* Filter card */
  .ctrl-card {{
    background: rgba(18,18,18,0.95); border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px;
  }}
  .ctrl-card label {{ font-size: 12px; color: #aaa; display: flex; align-items: center; gap: 8px; cursor: pointer; }}
  .ctrl-card label input[type=checkbox] {{ accent-color: #FF7AA2; width: 14px; height: 14px; }}
  .ctrl-title {{ font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }}

  /* Year slider */
  .year-row {{ display: flex; align-items: center; gap: 8px; }}
  .year-row input[type=range] {{ flex: 1; accent-color: #FF7AA2; }}
  .year-val {{ font-size: 12px; color: #eee; min-width: 34px; text-align: center; }}

  /* Buttons row */
  .btn-row {{ display: flex; gap: 8px; }}
  .ctrl-btn {{
    flex: 1; padding: 7px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15);
    background: rgba(40,40,40,0.9); color: #eee; font-size: 12px; cursor: pointer;
    transition: background 0.15s;
  }}
  .ctrl-btn:hover {{ background: rgba(255,122,162,0.2); border-color: #FF7AA2; }}
  .ctrl-btn.active {{ background: rgba(255,122,162,0.25); border-color: #FF7AA2; color: #FF7AA2; }}

  /* Stats */
  .stats-row {{ display: flex; gap: 6px; }}
  .stat-box {{
    flex: 1; background: rgba(30,30,30,0.8); border-radius: 6px;
    padding: 8px; text-align: center;
  }}
  .stat-val {{ font-size: 18px; font-weight: 700; color: #fff; }}
  .stat-lbl {{ font-size: 10px; color: #888; margin-top: 2px; }}

  /* ── Side panel ── */
  #sidepanel {{
    position: fixed; top: 12px; right: 12px; width: 35%; max-width: 500px;
    height: calc(100vh - 24px); background: rgba(18,18,18,0.95);
    border: 1px solid rgba(255,255,255,0.15); border-radius: 8px;
    padding: 20px; overflow-y: auto; z-index: 1000; color: #eee;
    box-shadow: 0 4px 15px rgba(0,0,0,0.5); display: flex; flex-direction: column; gap: 8px;
  }}
  #sidepanel h3 {{ margin: 0; color: #fff; border-bottom: 1px solid #444; padding-bottom: 10px; }}
  .hint {{ font-style: italic; color: #888; font-size: 13px; }}
  .apa-entry {{
    padding-left: 24px; text-indent: -24px;
    font-size: 13px; line-height: 1.5; color: #ddd;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding-bottom: 10px; margin-bottom: 6px; position: relative;
  }}
  .apa-journal {{ font-style: italic; color: #aaa; }}
  .apa-doi {{ color: #FF7AA2; text-decoration: none; word-break: break-all; }}
  .apa-doi:hover {{ text-decoration: underline; }}
  .copy-btn {{
    display: inline-block; margin-top: 6px; margin-left: 0;
    padding: 3px 10px; font-size: 11px; border-radius: 4px;
    border: 1px solid rgba(255,122,162,0.4); background: transparent;
    color: #FF7AA2; cursor: pointer; text-indent: 0;
  }}
  .copy-btn:hover {{ background: rgba(255,122,162,0.15); }}
  .copy-toast {{
    position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: #3CB371; color: #fff; padding: 8px 20px; border-radius: 20px;
    font-size: 13px; z-index: 9999; opacity: 0; transition: opacity 0.3s;
    pointer-events: none;
  }}
</style>
</head>
<body>

<div id="tooltip"></div>
<div class="copy-toast" id="copy-toast">✓ APA copied to clipboard</div>

<!-- Left controls -->
<div id="controls">

  <!-- Search -->
  <div id="searchbox">
    <input type="text" id="searchinput" placeholder="🔍  Search nodes or papers..." autocomplete="off" />
    <div id="search-results"></div>
  </div>

  <!-- Filters + stats -->
  <div class="ctrl-card">
    <div class="ctrl-title">Statistics</div>
    <div class="stats-row">
      <div class="stat-box"><div class="stat-val" id="stat-nodes">{n_nodes}</div><div class="stat-lbl">Nodes</div></div>
      <div class="stat-box"><div class="stat-val" id="stat-edges">{n_edges}</div><div class="stat-lbl">Edges</div></div>
      <div class="stat-box"><div class="stat-val" id="stat-visible">{n_nodes}</div><div class="stat-lbl">Visible</div></div>
    </div>

    <div class="ctrl-title">Filter by type</div>
    <label><input type="checkbox" id="chk-subtopic" checked> <span style="color:#3CB371">●</span> Subtopics</label>
    <label><input type="checkbox" id="chk-author"   checked> <span style="color:#FF7AA2">●</span> Authors</label>
    <label><input type="checkbox" id="chk-other"    checked> <span style="color:#9E9E9E">●</span> Other</label>

    <div class="ctrl-title">Filter by publication year</div>
    <div class="year-row">
      <span class="year-val" id="year-from-lbl">{global_min_year}</span>
      <input type="range" id="year-from" min="{global_min_year}" max="{global_max_year}" value="{global_min_year}" step="1">
      <input type="range" id="year-to"   min="{global_min_year}" max="{global_max_year}" value="{global_max_year}" step="1">
      <span class="year-val" id="year-to-lbl">{global_max_year}</span>
    </div>

    <div class="btn-row">
      <button class="ctrl-btn" id="btn-reset">⟳ Reset view</button>
      <button class="ctrl-btn" id="btn-neighbors">👁 Neighbors</button>
    </div>
  </div>
</div>

<svg id="svg">
  <g id="zoom-group">
    <g id="edges-layer"></g>
    <g id="nodes-layer"></g>
  </g>
</svg>

<div id="sidepanel">
  <h3>Selected Node</h3>
  <div class="hint">Click a node to view details.</div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
const graphData = {graph_data};
const GLOBAL_MIN_YEAR = {global_min_year};
const GLOBAL_MAX_YEAR = {global_max_year};

const svg  = d3.select("#svg");
const g    = d3.select("#zoom-group");
const tip  = document.getElementById("tooltip");

// ── Zoom & Pan ──────────────────────────────────────────────
const zoom = d3.zoom()
  .scaleExtent([0.05, 8])
  .on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

// Initial transform saved for reset
let initTransform;

// ── State ───────────────────────────────────────────────────
const nodePos = {{}};
graphData.nodes.forEach(n => {{ nodePos[n.id] = {{ x: n.x, y: n.y }}; }});

let neighborMode  = false;
let selectedNodeId = null;
let filterSubtopic = true, filterAuthor = true, filterOther = true;
let yearFrom = GLOBAL_MIN_YEAR, yearTo = GLOBAL_MAX_YEAR;

// adjacency for neighbor mode
const adjSet = {{}};
graphData.edges.forEach(e => {{
  if (!adjSet[e.source]) adjSet[e.source] = new Set();
  if (!adjSet[e.target]) adjSet[e.target] = new Set();
  adjSet[e.source].add(e.target);
  adjSet[e.target].add(e.source);
}});

// ── Draw edges ──────────────────────────────────────────────
const edgeLines = d3.select("#edges-layer")
  .selectAll("line")
  .data(graphData.edges)
  .join("line")
  .attr("class", "edge")
  .attr("x1", d => nodePos[d.source]?.x ?? 0)
  .attr("y1", d => nodePos[d.source]?.y ?? 0)
  .attr("x2", d => nodePos[d.target]?.x ?? 0)
  .attr("y2", d => nodePos[d.target]?.y ?? 0);

// ── Draw nodes ──────────────────────────────────────────────
const nodeG = d3.select("#nodes-layer")
  .selectAll("g.node")
  .data(graphData.nodes)
  .join("g")
  .attr("class", "node")
  .attr("transform", d => `translate(${{nodePos[d.id].x}}, ${{nodePos[d.id].y}})`)
  .style("cursor", "pointer")
  .on("click", (event, d) => {{
    event.stopPropagation();
    selectedNodeId = d.id;
    showPanel(d);
    highlightNode(d.id);
    if (neighborMode) applyNeighborDim(d.id);
  }})
  .on("mouseover", (event, d) => {{
    tip.style.display = "block";
    tip.innerHTML = `<b>${{d.label}}</b><br><span style="color:#888;font-size:11px">${{d.type}}</span>` +
      (d.minYear ? `<br><span style="color:#aaa;font-size:11px">📅 ${{d.minYear}}–${{d.maxYear ?? d.minYear}}</span>` : "");
  }})
  .on("mousemove", event => {{
    tip.style.left = (event.clientX + 14) + "px";
    tip.style.top  = (event.clientY - 10) + "px";
  }})
  .on("mouseout", () => {{ tip.style.display = "none"; }});

nodeG.append("circle")
  .attr("r", d => d.radius)
  .attr("fill", d => d.color)
  .attr("stroke", "#222")
  .attr("stroke-width", 0.5);

nodeG.append("text")
  .attr("class", "node-label")
  .attr("font-size", d => d.fontSize)
  .text(d => d.label);

// ── Drag ────────────────────────────────────────────────────
const drag = d3.drag()
  .on("start", function(event) {{ event.sourceEvent.stopPropagation(); d3.select(this).raise(); }})
  .on("drag", function(event, d) {{
    nodePos[d.id].x += event.dx;
    nodePos[d.id].y += event.dy;
    d3.select(this).attr("transform", `translate(${{nodePos[d.id].x}}, ${{nodePos[d.id].y}})`);
    edgeLines.filter(e => e.source === d.id).attr("x1", nodePos[d.id].x).attr("y1", nodePos[d.id].y);
    edgeLines.filter(e => e.target === d.id).attr("x2", nodePos[d.id].x).attr("y2", nodePos[d.id].y);
  }});
nodeG.call(drag);

// ── Side panel ──────────────────────────────────────────────
function showPanel(d) {{
  const panel = document.getElementById("sidepanel");
  let html = `<h3>${{d.label}}</h3>`;
  if (d.type) html += `<div style="font-size:12px;color:#888;margin-bottom:8px">Type: ${{d.type}}</div>`;
  html += d.apa && d.apa.length > 0 ? d.apa : `<div class="hint">No citation data available.</div>`;
  panel.innerHTML = html;
}}

svg.on("click", () => {{
  document.getElementById("sidepanel").innerHTML =
    `<h3>Selected Node</h3><div class="hint">Click a node to view details.</div>`;
  clearHighlight();
  if (neighborMode) clearDim();
  selectedNodeId = null;
}});

// ── Highlight ────────────────────────────────────────────────
function highlightNode(id) {{
  clearHighlight();
  d3.selectAll("g.node").filter(d => d.id === id).classed("node-highlight", true);
}}
function clearHighlight() {{ d3.selectAll("g.node").classed("node-highlight", false); }}

// ── Neighbor mode ────────────────────────────────────────────
function applyNeighborDim(id) {{
  const neighbors = adjSet[id] || new Set();
  nodeG.classed("dimmed", d => d.id !== id && !neighbors.has(d.id));
  edgeLines.classed("dimmed", e => e.source !== id && e.target !== id);
}}
function clearDim() {{
  nodeG.classed("dimmed", false);
  edgeLines.classed("dimmed", false);
}}

const btnNeighbors = document.getElementById("btn-neighbors");
btnNeighbors.addEventListener("click", () => {{
  neighborMode = !neighborMode;
  btnNeighbors.classList.toggle("active", neighborMode);
  if (!neighborMode) {{ clearDim(); }}
  else if (selectedNodeId) {{ applyNeighborDim(selectedNodeId); }}
}});

// ── Copy APA ─────────────────────────────────────────────────
function copyAPA(text) {{
  navigator.clipboard.writeText(text).then(() => {{
    const toast = document.getElementById("copy-toast");
    toast.style.opacity = "1";
    setTimeout(() => {{ toast.style.opacity = "0"; }}, 2000);
  }});
}}

// ── Filter logic ─────────────────────────────────────────────
function applyFilters() {{
  let visible = 0;
  nodeG.each(function(d) {{
    const typeOk =
      (filterSubtopic && d.type.toLowerCase().includes("subtopic")) ||
      (filterAuthor   && d.type.toLowerCase().includes("author"))   ||
      (filterOther    && !d.type.toLowerCase().includes("subtopic") && !d.type.toLowerCase().includes("author"));

    // year filter: show node if it has no year data OR has papers in range
    const yearOk = !d.minYear || (d.maxYear >= yearFrom && d.minYear <= yearTo);

    const show = typeOk && yearOk;
    d3.select(this).style("display", show ? null : "none");
    if (show) visible++;
  }});

  // hide edges where either endpoint is hidden
  const hiddenIds = new Set();
  nodeG.each(function(d) {{
    if (d3.select(this).style("display") === "none") hiddenIds.add(d.id);
  }});
  edgeLines.style("display", e => (hiddenIds.has(e.source) || hiddenIds.has(e.target)) ? "none" : null);

  document.getElementById("stat-visible").textContent = visible;
}}

// Type checkboxes
document.getElementById("chk-subtopic").addEventListener("change", e => {{ filterSubtopic = e.target.checked; applyFilters(); }});
document.getElementById("chk-author").addEventListener("change",   e => {{ filterAuthor   = e.target.checked; applyFilters(); }});
document.getElementById("chk-other").addEventListener("change",    e => {{ filterOther    = e.target.checked; applyFilters(); }});

// Year sliders
const sliderFrom = document.getElementById("year-from");
const sliderTo   = document.getElementById("year-to");
const lblFrom    = document.getElementById("year-from-lbl");
const lblTo      = document.getElementById("year-to-lbl");

sliderFrom.addEventListener("input", () => {{
  yearFrom = parseInt(sliderFrom.value);
  if (yearFrom > yearTo) {{ yearTo = yearFrom; sliderTo.value = yearFrom; lblTo.textContent = yearFrom; }}
  lblFrom.textContent = yearFrom;
  applyFilters();
}});
sliderTo.addEventListener("input", () => {{
  yearTo = parseInt(sliderTo.value);
  if (yearTo < yearFrom) {{ yearFrom = yearTo; sliderFrom.value = yearTo; lblFrom.textContent = yearTo; }}
  lblTo.textContent = yearTo;
  applyFilters();
}});

// ── Reset view ───────────────────────────────────────────────
document.getElementById("btn-reset").addEventListener("click", () => {{
  svg.transition().duration(600).call(zoom.transform, initTransform);
}});

// ── Fly to node ──────────────────────────────────────────────
function flyTo(nodeData) {{
  const W = window.innerWidth, H = window.innerHeight;
  const scale = 2.5;
  const tx = W/2 - scale * nodePos[nodeData.id].x;
  const ty = H/2 - scale * nodePos[nodeData.id].y;
  svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  showPanel(nodeData);
  highlightNode(nodeData.id);
}}

// ── Search ───────────────────────────────────────────────────
const searchInput   = document.getElementById("searchinput");
const searchResults = document.getElementById("search-results");

searchInput.addEventListener("input", () => {{
  const q = searchInput.value.trim().toLowerCase();
  if (!q) {{ searchResults.style.display = "none"; return; }}
  const results = [];
  graphData.nodes.forEach(n => {{
    if (n.label.toLowerCase().includes(q)) {{
      results.push({{ node: n, matchType: "node", snippet: "" }});
    }} else if (n.searchText && n.searchText.toLowerCase().includes(q)) {{
      const parts = n.searchText.split(" | ");
      const matched = parts.find(p => p.toLowerCase().includes(q)) || "";
      results.push({{ node: n, matchType: "paper", snippet: matched.substring(0, 80) }});
    }}
  }});
  if (results.length === 0) {{
    searchResults.innerHTML = `<div class="no-results">No results found.</div>`;
  }} else {{
    searchResults.innerHTML = results.slice(0, 30).map((r, i) => `
      <div class="search-result-item" data-idx="${{i}}">
        <div class="sr-type">${{r.matchType === "node" ? "📍 Node" : "📄 Paper"}}</div>
        <div class="sr-label">${{r.node.label}}</div>
        ${{r.snippet ? `<div class="sr-sub">${{r.snippet}}</div>` : ""}}
      </div>`).join("");
    searchResults.querySelectorAll(".search-result-item").forEach((el, i) => {{
      el.addEventListener("click", () => {{
        flyTo(results[i].node);
        searchResults.style.display = "none";
        searchInput.value = results[i].node.label;
      }});
    }});
  }}
  searchResults.style.display = "block";
}});

document.addEventListener("click", e => {{
  if (!document.getElementById("searchbox").contains(e.target))
    searchResults.style.display = "none";
}});

// ── Initial zoom to fit ─────────────────────────────────────
const xs = graphData.nodes.map(n => n.x);
const ys = graphData.nodes.map(n => n.y);
const minX = Math.min(...xs), maxX = Math.max(...xs);
const minY = Math.min(...ys), maxY = Math.max(...ys);
const W = window.innerWidth, H = window.innerHeight;
const scale = 0.85 / Math.max((maxX - minX) / W, (maxY - minY) / H);
const tx = W/2 - scale*(minX + maxX)/2;
const ty = H/2 - scale*(minY + maxY)/2;
initTransform = d3.zoomIdentity.translate(tx, ty).scale(scale);
svg.call(zoom.transform, initTransform);
</script>
</body>
</html>
"""

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print(f"DONE: Saved {OUT_HTML}")