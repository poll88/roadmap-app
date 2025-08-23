import json
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components

_VIS_CSS = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css"
_VIS_JS  = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js"
_FONT    = "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&display=swap"
_HTML2IMG = "https://cdnjs.cloudflare.com/ajax/libs/html-to-image/1.11.11/html-to-image.min.js"

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

def render_timeline(items, groups, selected_id: str = "", export_png: bool = False):
    rows = max(1, len(groups))
    height_px = max(260, 80 * rows + 120)

    win_start, win_end = _window_longest(items)
    ws, we = win_start.isoformat(), win_end.isoformat()

    # background per row across window
    bg = [{
        "id": f"bg-{g['id']}", "group": g["id"],
        "start": ws, "end": we, "type": "background", "className": "row-bg"
    } for g in groups]

    items_json  = json.dumps(items + bg, default=str)
    groups_json = json.dumps(groups, default=str)
    export_flag = "true" if export_png else "false"

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
    body, #wrap, #timeline, .vis-timeline, .vis-item, .vis-item-content, .vis-label, .vis-time-axis {{ font-family: var(--font); }}
    #wrap {{
      background:#fff; border-radius:14px; border:1px solid #e7e9f2;
      padding:8px;   /* included in PNG for a small margin */
    }}
    #timeline {{ height:{height_px}px; background:#fff; border-radius:12px; }}
    .row-bg {{ background: rgba(37,99,235,.05) }}
    .vis-time-axis .text {{ font-size:12px; font-weight:500 }}
    .vis-labelset .vis-label .vis-inner {{ font-weight:600 }}
    .vis-item .vis-item-content {{ line-height:1.15 }}
    .ttl {{ font-weight:600 }}
    .sub {{ font-size:12px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }}
  </style>
</head>
<body>
  <div id="wrap">
    <div id="timeline"></div>
  </div>

  <script src="{_VIS_JS}"></script>
  <script src="{_HTML2IMG}"></script>
  <script>
    function esc(s) {{
      return String(s ?? "")
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }}

    const ITEMS  = {items_json};
    const GROUPS = {groups_json};
    const DO_EXPORT = {export_flag};  // set by Streamlit when the sidebar button is pressed

    const container = document.getElementById('timeline');
    const options = {{
      orientation: 'top',
      margin: {{ item: 8, axis: 12 }},
      start: '{ws}',
      end:   '{we}',
      selectable: false,   // disable click/tap selection
      template: function(item) {{
        if (item.type === 'background') return '';
        const t = item.content ? `<div class="ttl">${{esc(item.content)}}</div>` : '';
        const s = item.subtitle ? `<div class="sub">${{esc(item.subtitle)}}</div>` : '';
        return t + s;
      }},
    }};

    const tl = new vis.Timeline(container, ITEMS, GROUPS, options);

    async function exportPng() {{
      const node = document.getElementById('wrap');
      try {{
        const pixelRatio = 300 / 96; // ~3.125x for 300 PPI
        const dataUrl = await window.htmlToImage.toPng(node, {{
          pixelRatio: pixelRatio,
          backgroundColor: '#ffffff',
          cacheBust: true
        }});
        const a = document.createElement('a');
        const ts = new Date().toISOString().slice(0,19).replace(/[:T]/g,'-');
        a.download = `timeline_{ws}_to_{we}_${{ts}}_300ppi.png`;
        a.href = dataUrl;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }} catch (e) {{
        console.error('PNG export failed', e);
        alert('PNG export failed. If this persists, try a desktop browser.');
      }}
    }}

    // If the sidebar button set export flag, export once on first paint.
    if (DO_EXPORT) {{
      // Wait one tick so timeline paints fully
      requestAnimationFrame(() => exportPng());
    }}
  </script>
</body>
</html>
    """
    components.html(html, height=height_px + 32, scrolling=False)