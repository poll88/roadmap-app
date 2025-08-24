# lib/timeline.py — clean render (no debug UI) + reliable SVG download overlay
# - Multi-CDN loader for vis.js/CSS (robust on iPad)
# - No click selection
# - Exact-style SVG export with transparent background
# - Shows a small "Download SVG" overlay after export (works on iPad Safari)

import json
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components

# Multiple CDNs for reliability
_VIS_CSS_URLS = [
  "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css",
  "https://cdn.jsdelivr.net/npm/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css",
  "https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.3/vis-timeline-graph2d.min.css",
]
_VIS_JS_URLS = [
  "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js",
  "https://cdn.jsdelivr.net/npm/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.3/vis-timeline-graph2d.min.js",
]
# ESM for SVG export only (base render doesn’t depend on it)
_DOM_TO_SVG_ESM = "https://cdn.jsdelivr.net/npm/dom-to-svg@0.12.2/lib/index.js"

BUFFER_PCT = 0.15
MIN_BUFFER_DAYS = 14

def _to_date(v):
    if isinstance(v, date): return v
    if isinstance(v, str) and v:
        return datetime.fromisoformat(v[:10]).date()
    return date.today()

def _window_longest(items):
    best = None; best_span = -1
    for it in items:
        if it.get("type") == "background": continue
        s = _to_date(it.get("start"))
        e = _to_date(it.get("end") or it.get("start"))
        if e < s: s, e = e, s
        span = max(1, (e - s).days)
        if span > best_span: best_span, best = span, (s, e)
    if not best:
        t = date.today()
        buf = max(MIN_BUFFER_DAYS, 30)
        return t - timedelta(days=buf), t + timedelta(days=buf)
    s, e = best
    buf = max(MIN_BUFFER_DAYS, int(round(best_span * BUFFER_PCT)))
    return s - timedelta(days=buf), e + timedelta(days=buf)

def render_timeline(items, groups, selected_id: str = "", export: dict | None = None):
    rows = max(1, len(groups))
    height_px = max(260, 80 * rows + 120)

    win_start, win_end = _window_longest(items)
    ws, we = win_start.isoformat(), win_end.isoformat()

    # Per-row light backgrounds (only if groups exist)
    bg = []
    if groups:
        bg = [{
            "id": f"bg-{g['id']}", "group": g["id"],
            "start": ws, "end": we, "type": "background", "className": "row-bg"
        } for g in groups]

    items_json  = json.dumps(items + bg, default=str)
    groups_json = json.dumps(groups, default=str)
    export_json = json.dumps(export or {}, default=str)

    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <!-- Montserrat for a modern look -->
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {{ --font: 'Montserrat', ui-sans-serif, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; }}
    html, body {{ background: transparent; margin:0; padding:0; }}
    body, #timeline, .vis-timeline, .vis-item, .vis-item-content, .vis-label, .vis-time-axis {{ font-family: var(--font); }}
    #wrap {{ position: relative; }}
    #timeline {{
      height:{height_px}px;
      background: transparent;
      border-radius:12px; border:1px solid #e7e9f2;
    }}
    .row-bg {{ background: rgba(37,99,235,.05) }}
    .vis-time-axis .text {{ font-size:12px; font-weight:500 }}
    .vis-labelset .vis-label .vis-inner {{ font-weight:600 }}
    .vis-item .vis-item-content {{ line-height:1.15 }}
    .ttl {{ font-weight:600 }}
    .sub {{ font-size:12px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }}

    /* Small overlay that appears AFTER export is ready (esp. for iPad Safari) */
    #dlbox {{
      display:none; position:absolute; right:10px; top:10px;
      background:#ffffff; border:1px solid #e5e7eb; border-radius:10px;
      box-shadow:0 6px 18px rgba(16,24,40,.08); padding:10px 12px; z-index:20;
      font-size:12px;
    }}
    #dlbox .row {{ display:flex; align-items:center; gap:8px; }}
    #dlbox a {{
      display:inline-flex; align-items:center; justify-content:center;
      padding:8px 10px; border-radius:8px; border:1px solid #cbd5e1;
      text-decoration:none; font-weight:600; color:#0f172a;
    }}
    #dlbox button {{
      margin-left:8px; padding:6px 8px; border-radius:8px; border:1px solid #e5e7eb;
      background:#f8fafc; color:#334155; cursor:pointer;
    }}
  </style>
</head>
<body>
  <div id="wrap">
    <div id="timeline"></div>
    <div id="dlbox">
      <div class="row">
        <a id="svg_link" download target="_blank">Download SVG</a>
        <button id="close_dl" title="Close">✕</button>
      </div>
    </div>
  </div>

  <script>
    // Data shared by both scripts
    window.__TL_DATA__ = {{
      ITEMS: {items_json},
      GROUPS: {groups_json},
      EXPORT: {export_json},
      WS: "{ws}",
      WE: "{we}",
      CSS_URLS: {json.dumps(_VIS_CSS_URLS)},
      JS_URLS: {json.dumps(_VIS_JS_URLS)}
    }};

    function loadCssSeq(urls) {{
      return new Promise((resolve) => {{
        let i = 0, done = false;
        const next = () => {{
          if (i >= urls.length) return resolve("none");
          const l = document.createElement('link');
          l.rel = 'stylesheet'; l.href = urls[i]; l.crossOrigin = 'anonymous';
          l.onload = () => {{ if (!done) {{ done = true; resolve(urls[i]); }} }};
          l.onerror = () => {{ l.remove(); i++; next(); }};
          document.head.appendChild(l);
        }};
        next();
      }});
    }}
    function loadScriptSeq(urls) {{
      return new Promise((resolve, reject) => {{
        let i = 0;
        const next = () => {{
          if (i >= urls.length) return reject(new Error("vis.js failed"));
          const s = document.createElement('script');
          s.src = urls[i]; s.async = true; s.crossOrigin = 'anonymous';
          s.onload = () => resolve(urls[i]);
          s.onerror = () => {{ s.remove(); i++; next(); }};
          document.head.appendChild(s);
        }};
        next();
      }});
    }}
    function stripGroupsIfMissing(items, groups) {{
      const hasGroups = Array.isArray(groups) && groups.length > 0;
      const anyGrouped = (items || []).some(it => it && it.group);
      if (!hasGroups && anyGrouped) {{
        return (items || []).map(it => {{ if (!it) return it; const c={{...it}}; delete c.group; return c; }});
      }}
      return items || [];
    }}

    // Render after CSS+JS are in
    (async function boot() {{
      const D = window.__TL_DATA__;
      await loadCssSeq(D.CSS_URLS).catch(()=>{});
      await loadScriptSeq(D.JS_URLS);

      const el = document.getElementById('timeline');
      const items  = stripGroupsIfMissing(D.ITEMS, D.GROUPS);
      const groups = Array.isArray(D.GROUPS) ? D.GROUPS : [];

      const options = {{
        orientation: 'top',
        margin: {{ item: 8, axis: 12 }},
        start: D.WS,
        end:   D.WE,
        selectable: false,
        template: function(item) {{
          if (item.type