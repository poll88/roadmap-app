# lib/timeline.py — stable render (non-module), SVG export (module), transparent bg

import json
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components

_VIS_CSS = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css"
_VIS_JS  = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js"
_FONT    = "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&display=swap"
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
        if span > best_span:
            best_span = span; best = (s, e)
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

    # light per-row backgrounds spanning the window
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
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{_FONT}" rel="stylesheet">
  <link rel="stylesheet" href="{_VIS_CSS}"/>
  <style>
    :root {{ --font: 'Montserrat', system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, sans-serif; }}
    html, body {{ background: transparent; }}
    body, #timeline, .vis-timeline, .vis-item, .vis-item-content, .vis-label, .vis-time-axis {{ font-family: var(--font); }}
    #timeline {{
      height:{height_px}px;
      background: transparent;     /* transparent background for export */
      border-radius:12px;
      border:1px solid #e7e9f2;
    }}
    .row-bg {{ background: rgba(37,99,235,.05) }}
    .vis-time-axis .text {{ font-size:12px; font-weight:500 }}
    .vis-labelset .vis-label .vis-inner {{ font-weight:600 }}
    .vis-item .vis-item-content {{ line-height:1.15 }}
    .ttl {{ font-weight:600 }}
    .sub {{ font-size:12px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }}
    /* selection disabled */
  </style>
</head>
<body>
  <div id="timeline"></div>

  <script src="{_VIS_JS}"></script>

  <!-- 1) NON-MODULE SCRIPT: always renders the timeline (robust on iPad) -->
  <script>
    // Expose data to window so the module (if it loads) can reuse it
    window.__TIMELINE_DATA__ = {{
      ITEMS: {items_json},
      GROUPS: {groups_json},
      EXPORT: {export_json},
      WS: "{ws}",
      WE: "{we}"
    }};

    function esc(s) {{
      return String(s ?? "")
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }}

    (function renderBaseTimeline() {{
      try {{
        const el = document.getElementById('timeline');
        const D = window.__TIMELINE_DATA__;
        const options = {{
          orientation: 'top',
          margin: {{ item: 8, axis: 12 }},
          start: D.WS,
          end:   D.WE,
          selectable: false,
          template: function(item) {{
            if (item.type === 'background') return '';
            const t = item.content ? `<div class="ttl">${{esc(item.content)}}</div>` : '';
            const s = item.subtitle ? `<div class="sub">${{esc(item.subtitle)}}</div>` : '';
            return t + s;
          }},
        }};
        // Create timeline; keep a reference for debugging
        window.__TL__ = new vis.Timeline(el, D.ITEMS, D.GROUPS, options);
      }} catch (e) {{
        console.error('Timeline render failed:', e);
      }}
    }})();
  </script>

  <!-- 2) MODULE SCRIPT: only handles SVG export; if it fails to load, timeline still shows -->
  <script type="module">
    import {{ elementToSVG, inlineResources }} from "{_DOM_TO_SVG_ESM}";

    async function exportSVG(EXPORT) {{
      if (!EXPORT || Object.keys(EXPORT).length === 0) return;

      const D = window.__TIMELINE_DATA__;
      const ITEMS  = D.ITEMS;
      const GROUPS = D.GROUPS;

      // Compute span across items
      function toDate(v) {{
        if (!v) return new Date();
        if (typeof v === 'string') return new Date(v);
        return new Date(v);
      }}
      let smin = null, emax = null;
      for (const it of ITEMS) {{
        if (it.type === 'background') continue;
        const s = toDate(it.start), e = toDate(it.end || it.start);
        const a = s < e ? s : e, b = s < e ? e : s;
        if (!smin || a < smin) smin = a;
        if (!emax || b > emax) emax = b;
      }}
      if (!smin || !emax) return;

      function monthAdd(d, delta) {{
        const dt = new Date(d);
        const m = dt.getUTCMonth() + delta;
        dt.setUTCMonth(m, 1);
        return dt;
      }}
      const padMonths = Number(EXPORT.padMonths || 0);
      const start = monthAdd(new Date(Date.UTC(smin.getUTCFullYear(), smin.getUTCMonth(), 1)), -padMonths);
      const end   = monthAdd(new Date(Date.UTC(emax.getUTCFullYear(), emax.getUTCMonth(), 1)), padMonths + 1);

      // Offscreen container
      const pxPerInch = 96;
      const widthInches = Number(EXPORT.widthInches || 24);
      const cssWidth = Math.max(800, Math.round(widthInches * pxPerInch));
      const rows = Math.max(1, GROUPS.length);
      const cssHeight = Math.max(260, 80 * rows + 120);

      const wrap = document.createElement('div');
      wrap.style.position = 'fixed';
      wrap.style.left = '-100000px';
      wrap.style.top = '0';
      wrap.style.width = cssWidth + 'px';
      wrap.style.background = 'transparent';
      document.body.appendChild(wrap);

      const node = document.createElement('div');
      node.style.width = '100%';
      node.style.height = cssHeight + 'px';
      node.style.background = 'transparent';
      node.className = 'vis-timeline';
      wrap.appendChild(node);

      const timeAxis = {{}};
      const gran = String(EXPORT.granularity || 'auto').toLowerCase();
      if (gran === 'month')  {{ timeAxis.scale = 'month';  timeAxis.step = 1; }}
      if (gran === 'quarter'){{ timeAxis.scale = 'month';  timeAxis.step = 3; }}

      const options = {{
        orientation: 'top',
        margin: {{ item: 8, axis: 12 }},
        start: start.toISOString().slice(0,10),
        end:   end.toISOString().slice(0,10),
        timeAxis,
        selectable: false,
        template: function(item) {{
          if (item.type === 'background') return '';
          const t = item.content ? `<div class="ttl">${{item.content}}</div>` : '';
          const s = item.subtitle ? `<div class="sub">${{item.subtitle}}</div>` : '';
          return t + s;
        }},
      }};
      const exTl = new vis.Timeline(node, ITEMS, GROUPS, options);

      // Wait for layout
      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 120)));

      // Inline resources -> SVG text
      const svgDoc = elementToSVG(node);
      await inlineResources(svgDoc.documentElement);
      const svgText = new XMLSerializer().serializeToString(svgDoc);

      const ts = new Date().toISOString().slice(0,19).replace(/[:T]/g,'-');
      const filename = `timeline_${{start.toISOString().slice(0,10)}}_to_${{end.toISOString().slice(0,10)}}_${{ts}}.svg`;
      const blob = new Blob([svgText], {{ type: 'image/svg+xml' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename;
      document.body.appendChild(a); a.click();
      setTimeout(() => {{ URL.revokeObjectURL(url); a.remove(); }}, 0);

      exTl.destroy();
      wrap.remove();
    }}

    try {{
      const EXPORT = window.__TIMELINE_DATA__ && window.__TIMELINE_DATA__.EXPORT;
      // Run once (sidebar sets the payload, app clears it next render)
      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 50)));
      exportSVG(EXPORT);
    }} catch (err) {{
      // If this fails, it won't break the base timeline render
      console.warn('SVG export module failed:', err);
    }}
  </script>
</body>
</html>
    """
    components.html(html, height=height_px + 20, scrolling=False)