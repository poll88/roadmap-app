# lib/timeline.py — bulletproof render: waits for vis.js, inlines CSS, graceful group fallback,
# visible error banner, SVG export isolated; transparent background; no click selection.

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

    # Background per row (only if groups exist)
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
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{_FONT}" rel="stylesheet">
  <!-- keep the link, but we will also inline the CSS for reliability -->
  <link rel="stylesheet" href="{_VIS_CSS}" crossorigin="anonymous"/>
  <style>
    :root {{ --font: 'Montserrat', system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, sans-serif; }}
    html, body {{ background: transparent; }}
    body, #timeline, .vis-timeline, .vis-item, .vis-item-content,
    .vis-label, .vis-time-axis {{ font-family: var(--font); }}
    #wrapper {{ position: relative; }}
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
    /* error banner */
    #err {{
      display:none; position:absolute; inset:0; padding:14px; border-radius:12px;
      background: rgba(255, 248, 248, .96); color:#991B1B; border:1px solid #fecaca;
      font-size:13px; line-height:1.35;
    }}
    #err strong {{ display:block; margin-bottom:6px; }}
  </style>
</head>
<body>
  <div id="wrapper">
    <div id="timeline"></div>
    <div id="err"><strong>Timeline failed to load</strong><span id="errmsg"></span></div>
  </div>

  <script src="{_VIS_JS}"></script>

  <!-- Base renderer (non-module). Waits for vis.js and inlines vis CSS before rendering. -->
  <script>
    // Data payload shared by both scripts
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

    function showErr(msg) {{
      try {{
        const box = document.getElementById('err');
        const span = document.getElementById('errmsg');
        span.textContent = String(msg || 'Unknown error');
        box.style.display = 'block';
      }} catch(_) {{}}
    }}

    // Inline the vis CSS to avoid stylesheet load races on iPad/CDN
    let __cssInjected = false;
    function ensureVisCss() {{
      if (__cssInjected) return Promise.resolve();
      return fetch("{_VIS_CSS}", {{ mode: 'cors' }})
        .then(r => r.ok ? r.text() : '')
        .then(css => {{
          if (css) {{
            const s = document.createElement('style');
            s.setAttribute('data-inlined-vis-css', '1');
            s.textContent = css;
            document.head.appendChild(s);
            __cssInjected = true;
          }}
        }})
        .catch(() => {{ /* non-fatal; link tag will be used */ }});
    }}

    // If groups array is empty but items carry a "group" field, fall back to single-lane render.
    function stripGroupsIfMissing(items, groups) {{
      try {{
        const hasGroups = Array.isArray(groups) && groups.length > 0;
        const anyGrouped = (items || []).some(it => it && it.group);
        if (!hasGroups && anyGrouped) {{
          return (items || []).map(it => {{
            if (!it) return it;
            const cpy = Object.assign({{}}, it);
            delete cpy.group;
            return cpy;
          }});
        }}
        return items || [];
      }} catch(_) {{
        return items || [];
      }}
    }}

    function renderTimeline() {{
      const el = document.getElementById('timeline');
      const D = window.__TIMELINE_DATA__;
      const baseItems  = Array.isArray(D.ITEMS) ? D.ITEMS : [];
      const baseGroups = Array.isArray(D.GROUPS) ? D.GROUPS : [];

      const safeItems  = stripGroupsIfMissing(baseItems, baseGroups);
      const safeGroups = baseGroups; // keep as-is; may be empty

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

      try {{
        const items  = new vis.DataSet(safeItems);
        // If we have no groups, pass only items (3-arg ctor) so vis renders single lane
        if (safeGroups && safeGroups.length) {{
          const groups = new vis.DataSet(safeGroups);
          if (window.__TL__ && window.__TL__.destroy) window.__TL__.destroy();
          window.__TL__ = new vis.Timeline(el, items, groups, options);
        }} else {{
          if (window.__TL__ && window.__TL__.destroy) window.__TL__.destroy();
          window.__TL__ = new vis.Timeline(el, items, options);
        }}
      }} catch (e) {{
        console.error(e);
        showErr(e.message || e);
      }}
    }}

    (function boot(n) {{
      // Wait for vis.js to be present, then inline the CSS, then render
      if (window.vis && window.vis.Timeline) {{
        return ensureVisCss().finally(() => {{
          requestAnimationFrame(() => renderTimeline());
        }});
      }}
      if (n > 80) {{  // ~4s
        return showErr('vis.js did not load.');
      }}
      setTimeout(() => boot(n + 1), 50);
    }})(0);
  </script>

  <!-- SVG export stays isolated in a module; if it fails, base render is unaffected -->
  <script type="module">
    import {{ elementToSVG, inlineResources }} from "{_DOM_TO_SVG_ESM}";

    async function exportSVG(EXPORT) {{
      if (!EXPORT || Object.keys(EXPORT).length === 0) return;

      const D = window.__TIMELINE_DATA__;
      const ITEMS  = D.ITEMS || [];
      const GROUPS = D.GROUPS || [];

      const toDate = v => new Date(typeof v === 'string' ? v : v);
      let smin = null, emax = null;
      for (const it of ITEMS) {{
        if (it.type === 'background') continue;
        const s = toDate(it.start), e = toDate(it.end || it.start);
        const a = s < e ? s : e, b = s < e ? e : s;
        if (!smin || a < smin) smin = a;
        if (!emax || b > emax) emax = b;
      }}
      if (!smin || !emax) return;

      const monthAdd = (d, delta) => {{
        const dt = new Date(d);
        const m = dt.getUTCMonth() + delta;
        dt.setUTCMonth(m, 1);
        return dt;
      }};
      const pad = Number(EXPORT.padMonths || 0);
      const start = monthAdd(new Date(Date.UTC(smin.getUTCFullYear(), smin.getUTCMonth(), 1)), -pad);
      const end   = monthAdd(new Date(Date.UTC(emax.getUTCFullYear(), emax.getUTCMonth(), 1)), pad + 1);

      // Offscreen render node
      const pxPerInch = 96;
      const cssWidth  = Math.max(800, Math.round((Number(EXPORT.widthInches || 24)) * pxPerInch));
      const rows      = Math.max(1, GROUPS.length);
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

      const exTl = new vis.Timeline(node, ITEMS, GROUPS && GROUPS.length ? GROUPS : undefined, options);
      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 120)));

      // Inline the externally loaded CSS into the SVG as well
      try {{
        const css = await fetch("{_VIS_CSS}", {{ mode: 'cors' }}).then(r => r.ok ? r.text() : '');
        if (css) {{
          const style = document.createElement('style');
          style.textContent = css;
          node.prepend(style);
        }}
      }} catch(_) {{}}

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
      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 50)));
      exportSVG(EXPORT);
    }} catch (err) {{
      console.warn('SVG export module failed:', err);  // non-fatal
    }}
  </script>
</body>
</html>
    """
    components.html(html, height=height_px + 28, scrolling=False)