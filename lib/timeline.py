# lib/timeline.py — DOM→SVG export (exact style), transparent background, no click selection

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

    # light per-row background spans across window (kept visible)
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
      background: transparent;    /* transparent background for export */
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
  <script type="module">
    import {{ elementToSVG, inlineResources }} from "{_DOM_TO_SVG_ESM}";

    function esc(s) {{
      return String(s ?? "")
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }}

    const ITEMS  = {items_json};
    const GROUPS = {groups_json};
    const EXPORT = {export_json};

    const container = document.getElementById('timeline');

    const options = {{
      orientation: 'top',
      margin: {{ item: 8, axis: 12 }},
      start: '{ws}',
      end:   '{we}',
      selectable: false,
      template: function(item) {{
        if (item.type === 'background') return '';
        const t = item.content ? `<div class="ttl">${{esc(item.content)}}</div>` : '';
        const s = item.subtitle ? `<div class="sub">${{esc(item.subtitle)}}</div>` : '';
        return t + s;
      }},
    }};

    const tl = new vis.Timeline(container, ITEMS, GROUPS, options);

    async function exportSVG(granularity, padMonths, widthInches) {{
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
      if (!smin || !emax) {{
        alert('No items to export.');
        return;
      }}

      function monthAdd(d, delta) {{
        const dt = new Date(d);
        const m = dt.getUTCMonth() + delta;
        dt.setUTCMonth(m, 1);
        return dt;
      }}
      const start = monthAdd(new Date(Date.UTC(smin.getUTCFullYear(), smin.getUTCMonth(), 1)), -padMonths);
      const end   = monthAdd(new Date(Date.UTC(emax.getUTCFullYear(), emax.getUTCMonth(), 1)), padMonths + 1);

      // Offscreen container with transparent bg
      const pxPerInch = 96; // CSS pixels
      const cssWidth = Math.max(800, Math.round(widthInches * pxPerInch));
      const rows = Math.max(1, GROUPS.length);
      const cssHeight = Math.max(260, 80 * rows + 120);

      const wrap = document.createElement('div');
      wrap.id = 'export-wrap';
      wrap.style.position = 'fixed';
      wrap.style.left = '-100000px';
      wrap.style.top = '0';
      wrap.style.width = cssWidth + 'px';
      wrap.style.background = 'transparent';
      wrap.style.padding = '0';
      document.body.appendChild(wrap);

      const node = document.createElement('div');
      node.id = 'export-timeline';
      node.style.width = '100%';
      node.style.height = cssHeight + 'px';
      node.style.background = 'transparent';
      node.className = 'vis-timeline';
      wrap.appendChild(node);

      const timeAxis = {{}};
      if (granularity === 'month') {{
        timeAxis.scale = 'month';
        timeAxis.step = 1;
      }} else if (granularity === 'quarter') {{
        timeAxis.scale = 'month';
        timeAxis.step = 3;
      }}

      const exOpts = Object.assign({{}}, options, {{
        start: start.toISOString().slice(0,10),
        end:   end.toISOString().slice(0,10),
        timeAxis
      }});
      const exTl = new vis.Timeline(node, ITEMS, GROUPS, exOpts);

      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 120)));

      // Build a self-contained SVG (inlines fonts, styles, images)
      const svgDoc = elementToSVG(node);
      await inlineResources(svgDoc.documentElement);
      const svgText = new XMLSerializer().serializeToString(svgDoc);

      // Download as SVG (transparent background)
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

    // One-shot export triggered from Streamlit (sidebar button)
    (async () => {{
      if (EXPORT && Object.keys(EXPORT).length) {{
        const gran = (EXPORT.granularity || 'auto').toLowerCase();
        const pad  = Number(EXPORT.padMonths || 0);
        const win  = Number(EXPORT.widthInches || 24);
        await new Promise(r => requestAnimationFrame(() => setTimeout(r, 50)));
        await exportSVG(gran, pad, win);
      }}
    }})();
  </script>
</body>
</html>
    """
    components.html(html, height=height_px + 20, scrolling=False)