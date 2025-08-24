# lib/timeline.py — failsafe vis loader (multi-CDN), visible status+errors,
# transparent background, group-safe render, SVG export kept separate.

import json
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components

# Preferred CDN locations (we'll try all until one works)
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
# ESM (export only; base render does not depend on this)
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
  <style>
    :root {{ --font: ui-sans-serif, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; }}
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

    /* Small status box so you can see what's happening */
    #status {{
      position:absolute; right:8px; top:8px; max-width:50%;
      background:#f8fafc; border:1px dashed #cbd5e1; color:#0f172a;
      font-size:11px; line-height:1.25; padding:6px 8px; border-radius:8px; white-space:pre-wrap;
    }}
    #err {{
      display:none; position:absolute; inset:0; padding:14px; border-radius:12px;
      background: rgba(255,248,248,.96); color:#991B1B; border:1px solid #fecaca; font-size:13px; line-height:1.35;
    }}
    #err strong {{ display:block; margin-bottom:6px; }}
  </style>
</head>
<body>
  <div id="wrap">
    <div id="timeline"></div>
    <div id="status">Status: booting…</div>
    <div id="err"><strong>Timeline failed to load</strong><span id="errmsg"></span></div>
  </div>

  <script>
    // Data for both scripts
    window.__TL_DATA__ = {{
      ITEMS: {items_json},
      GROUPS: {groups_json},
      EXPORT: {export_json},
      WS: "{ws}",
      WE: "{we}",
      CSS_URLS: {json.dumps(_VIS_CSS_URLS)},
      JS_URLS: {json.dumps(_VIS_JS_URLS)}
    }};

    function logStatus(msg) {{
      try {{
        const s = document.getElementById('status');
        s.textContent += "\\n" + msg;
      }} catch(_){{}}
    }}
    function showErr(msg) {{
      const box = document.getElementById('err');
      const span = document.getElementById('errmsg');
      span.textContent = String(msg || 'Unknown error');
      box.style.display = 'block';
      logStatus("ERROR: " + span.textContent);
    }}

    function loadCssSeq(urls) {{
      return new Promise((resolve) => {{
        let i = 0, done = false;
        const tryNext = () => {{
          if (i >= urls.length) {{
            // Last resort: continue without (we styled essentials ourselves)
            return resolve("none");
          }}
          const l = document.createElement('link');
          l.rel = 'stylesheet'; l.href = urls[i]; l.crossOrigin = 'anonymous';
          l.onload = () => {{ if (!done) {{ done = true; resolve(urls[i]); }} }};
          l.onerror = () => {{ l.remove(); i++; tryNext(); }};
          document.head.appendChild(l);
        }};
        tryNext();
      }});
    }}

    function loadScriptSeq(urls) {{
      return new Promise((resolve, reject) => {{
        let i = 0;
        const tryNext = () => {{
          if (i >= urls.length) return reject(new Error("All vis.js URLs failed"));
          const s = document.createElement('script');
          s.src = urls[i]; s.async = true; s.crossOrigin = 'anonymous';
          s.onload = () => resolve(urls[i]);
          s.onerror = () => {{ s.remove(); i++; tryNext(); }};
          document.head.appendChild(s);
        }};
        tryNext();
      }});
    }}

    function stripGroupsIfMissing(items, groups) {{
      try {{
        const hasGroups = Array.isArray(groups) && groups.length > 0;
        const anyGrouped = (items || []).some(it => it && it.group);
        if (!hasGroups && anyGrouped) {{
          return (items || []).map(it => {{
            if (!it) return it;
            const c = Object.assign({{}}, it);
            delete c.group;
            return c;
          }});
        }}
        return items || [];
      }} catch(_) {{
        return items || [];
      }}
    }}

    function renderTimeline() {{
      const D = window.__TL_DATA__;
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
          if (item.type === 'background') return '';
          const t = item.content ? `<div class="ttl">${{String(item.content).replace(/&/g,"&amp;").replace(/</g,"&lt;")}}</div>` : '';
          const s = item.subtitle ? `<div class="sub">${{String(item.subtitle).replace(/&/g,"&amp;").replace(/</g,"&lt;")}}</div>` : '';
          return t + s;
        }},
      }};

      try {{
        if (groups.length) {{
          window.__TL__ = new vis.Timeline(el, new vis.DataSet(items), new vis.DataSet(groups), options);
        }} else {{
          window.__TL__ = new vis.Timeline(el, new vis.DataSet(items), options);
        }}
        logStatus("Rendered OK. items=" + (items?.length||0) + " groups=" + (groups?.length||0));
      }} catch (e) {{
        console.error(e); showErr(e.message || e);
      }}
    }}

    (async function boot() {{
      const D = window.__TL_DATA__;
      logStatus("Loading CSS…");
      const cssFrom = await loadCssSeq(D.CSS_URLS).catch(()=>"none");
      logStatus("CSS from: " + cssFrom);

      logStatus("Loading vis.js…");
      let jsFrom = "unknown";
      try {{
        jsFrom = await loadScriptSeq(D.JS_URLS);
        logStatus("vis.js from: " + jsFrom);
      }} catch (e) {{
        showErr("vis.js failed to load from all CDNs");
        return;
      }}

      // Wait 1 frame so the browser applies styles
      requestAnimationFrame(renderTimeline);
    }})();
  </script>

  <!-- SVG export isolated in a module (won't affect base render if it fails) -->
  <script type="module">
    import {{ elementToSVG, inlineResources }} from "{_DOM_TO_SVG_ESM}";
    const D = window.__TL_DATA__;
    const EXPORT = D && D.EXPORT;
    if (EXPORT && Object.keys(EXPORT).length) {{
      const ITEMS  = D.ITEMS || [];
      const GROUPS = D.GROUPS || [];

      const toDate = v => new Date(typeof v === 'string' ? v : v);
      let smin = null, emax = null;
      for (const it of ITEMS) {{
        if (!it || it.type === 'background') continue;
        const s = toDate(it.start), e = toDate(it.end || it.start);
        const a = s < e ? s : e, b = s < e ? e : s;
        if (!smin || a < smin) smin = a;
        if (!emax || b > emax) emax = b;
      }}
      if (!smin || !emax) return;

      const monthAdd = (d, delta) => {{ const dt=new Date(d); const m=dt.getUTCMonth()+delta; dt.setUTCMonth(m,1); return dt; }};
      const pad = Number(EXPORT.padMonths || 0);
      const start = monthAdd(new Date(Date.UTC(smin.getUTCFullYear(), smin.getUTCMonth(), 1)), -pad);
      const end   = monthAdd(new Date(Date.UTC(emax.getUTCFullYear(), emax.getUTCMonth(), 1)), pad + 1);

      const pxPerInch = 96;
      const cssWidth  = Math.max(800, Math.round((Number(EXPORT.widthInches || 24)) * pxPerInch));
      const rows      = Math.max(1, GROUPS.length);
      const cssHeight = Math.max(260, 80 * rows + 120);

      const wrap = document.createElement('div');
      wrap.style.position = 'fixed'; wrap.style.left = '-100000px'; wrap.style.top = '0';
      wrap.style.width = cssWidth + 'px'; wrap.style.background = 'transparent';
      document.body.appendChild(wrap);

      const node = document.createElement('div');
      node.style.width = '100%'; node.style.height = cssHeight + 'px'; node.style.background = 'transparent';
      node.className = 'vis-timeline';
      wrap.appendChild(node);

      const timeAxis = {{}};
      const gran = String(EXPORT.granularity || 'auto').toLowerCase();
      if (gran === 'month')  {{ timeAxis.scale = 'month'; timeAxis.step = 1; }}
      if (gran === 'quarter'){{ timeAxis.scale = 'month'; timeAxis.step = 3; }}

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

      const exTl = new vis.Timeline(node, ITEMS, (GROUPS && GROUPS.length ? GROUPS : undefined), options);
      await new Promise(r => requestAnimationFrame(() => setTimeout(r, 120)));

      // Inline vis CSS so the SVG keeps the look
      try {{
        const cssText = await fetch({json.dumps(_VIS_CSS_URLS[0])}).then(r => r.ok ? r.text() : "");
        if (cssText) {{
          const st = document.createElement('style');
          st.textContent = cssText;
          node.prepend(st);
        }}
      }} catch (_) {{}}

      const svgDoc = elementToSVG(node);
      await inlineResources(svgDoc.documentElement);
      const svgText = new XMLSerializer().serializeToString(svgDoc);

      const ts = new Date().toISOString().slice(0,19).replace(/[:T]/g,'-');
      const filename = `timeline_${{start.toISOString().slice(0,10)}}_to_${{end.toISOString().slice(0,10)}}_${{ts}}.svg`;
      const blob = new Blob([svgText], {{ type: 'image/svg+xml' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); setTimeout(()=>{{ URL.revokeObjectURL(url); a.remove(); }}, 0);

      exTl.destroy(); wrap.remove();
    }}
  </script>
</body>
</html>
    """
    components.html(html, height=height_px + 36, scrolling=False)