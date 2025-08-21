# lib/timeline.py — dynamic window: longest event ± buffer

import json
from datetime import date, datetime, timedelta
import streamlit.components.v1 as components

# CDN assets
_VIS_CSS = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css"
_VIS_JS  = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js"
_FONT    = "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&display=swap"

# Tuning knobs
_BUFFER_PERCENT = 0.15   # 15% of the longest event’s span
_MIN_BUFFER_DAYS = 14    # but at least this many days

def _to_date(v):
    if isinstance(v, date): return v
    if isinstance(v, str) and v:
        return datetime.fromisoformat(v[:10]).date()
    return date.today()

def _dynamic_window(items):
    """Find the single longest event and return (start, end) expanded by buffer."""
    best = None
    best_span = -1
    for it in items:
        if it.get("type") == "background":  # ignore bg rows
            continue
        s = _to_date(it.get("start"))
        e = _to_date(it.get("end") or it.get("start"))
        if e < s:
            s, e = e, s
        span_days = max(1, (e - s).days)
        if span_days > best_span:
            best_span = span_days
            best = (s, e)

    if not best:
        # No items: show a small symmetric window around today
        t = date.today()
        buf = max(_MIN_BUFFER_DAYS, 30)
        return (t - timedelta(days=buf), t + timedelta(days=buf))

    s, e = best
    buf = max(_MIN_BUFFER_DAYS, int(round(best_span * _BUFFER_PERCENT)))
    return (s - timedelta(days=buf), e + timedelta(days=buf))

def render_timeline(items, groups, selected_id: str = ""):
    rows = max(1, len(groups))
    height_px = max(260, 80 * rows + 120)

    # Compute dynamic initial window from the longest event
    win_start, win_end = _dynamic_window(items)
    win_start_s = win_start.isoformat()
    win_end_s   = win_end.isoformat()

    # Light background per row spanning the chosen window
    bg_items = [{
        "id": f"bg-{g['id']}",
        "group": g["id"],
        "start": win_start_s,
        "end": win_end_s,
        "type": "background",
        "className": "row-bg"
    } for g in groups]

    # Serialize (support date objects via default=str)
    items_json  = json.dumps(items + bg_items, default=str)
    groups_json = json.dumps(groups, default=str)
    selected_js = json.dumps(selected_id or "")

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
      body, #timeline, .vis-timeline, .vis-item, .vis-item-content, .vis-label, .vis-time-axis {{ font-family: var(--font); }}
      #timeline {{ height:{height_px}px; background:#fff; border-radius:14px; border:1px solid #e7e9f2 }}
      .row-bg {{ background: rgba(37,99,235,.05) }}
      .vis-time-axis .text {{ font-size:12px; font-weight:500 }}
      .vis-labelset .vis-label .vis-inner {{ font-weight:600 }}
      .vis-item .vis-item-content {{ line-height:1.15 }}
      .ttl {{ font-weight:600 }}
      .sub {{ font-size:12px; opacity:.9; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }}
      .vis-item.vis-selected {{ box-shadow: 0 0 0 2px rgba(37,99,235,.7) inset, 0 0 0 2px rgba(37,99,235,.25); border-color:#2563eb !important }}

      .toolbar {{ display:flex; gap:8px; margin:8px 0 12px }}
      .toolbar button {{
        padding:6px 10px; border:1px solid #e5e7eb; background:#fff; border-radius:8px; cursor:pointer
      }}
      .toolbar button:hover {{ background:#f3f4f6 }}
    </style>
  </head>
  <body>
    <div class="toolbar">
      <button id="btn-fit">Fit all</button>
      <button id="btn-window">Show longest ± buffer</button>
      <button id="btn-today">Today</button>
    </div>
    <div id="timeline"></div>

    <script src="{_VIS_JS}"></script>
    <script>
      function esc(s) {{
        return String(s ?? "")
          .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
      }}

      const ITEMS  = {items_json};
      const GROUPS = {groups_json};
      const selId  = {selected_js};
      const container = document.getElementById('timeline');

      const options = {{
        orientation: 'top',
        margin: {{ item: 8, axis: 12 }},
        start: '{win_start_s}',   // initial window (dynamic)
        end:   '{win_end_s}',
        template: function(item) {{
          if (item.type === 'background') return '';
          const t = item.content ? `<div class="ttl">${{esc(item.content)}}</div>` : '';
          const s = item.subtitle ? `<div class="sub">${{esc(item.subtitle)}}</div>` : '';
          return t + s;
        }},
      }};

      const timeline = new vis.Timeline(container, ITEMS, GROUPS, options);

      // Optional: preselect item (no auto-focus to avoid big jumps)
      if (selId) {{
        try {{ timeline.setSelection([selId], {{ focus:false }}); }} catch(e) {{}}
      }}

      // Toolbar actions
      document.getElementById('btn-fit').onclick = () => {{
        try {{ timeline.fit({{ animation: true }}); }} catch(e){{}}
      }};
      document.getElementById('btn-window').onclick = () => {{
        try {{ timeline.setWindow('{win_start_s}', '{win_end_s}', {{ animation: true }}); }} catch(e){{}}
      }};
      document.getElementById('btn-today').onclick = () => {{
        try {{ timeline.moveTo(new Date(), {{ animation: true }}); }} catch(e){{}}
      }};
    </script>
  </body>
</html>
    """
    components.html(html, height=height_px + 52, scrolling=False)