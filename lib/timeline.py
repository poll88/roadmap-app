import json
from datetime import date, timedelta
import streamlit.components.v1 as components

# Assets
_VIS_CSS = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.css"
_VIS_JS  = "https://unpkg.com/vis-timeline@7.7.3/dist/vis-timeline-graph2d.min.js"
_FONT    = "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&display=swap"

def render_timeline(items, groups, selected_id: str = ""):
    rows = max(1, len(groups))
    height_px = max(260, 80 * rows + 120)

    # Clamp window: at most ~1 year back; end capped at 2028-12-31
    min_date = (date.today() - timedelta(days=365)).isoformat()
    max_date = "2028-12-31"

    # Light background per group
    bg_items = [{
        "id": f"bg-{g['id']}",
        "group": g["id"],
        "start": min_date,
        "end": max_date,
        "type": "background",
        "className": "row-bg"
    } for g in groups]

    payload_items = items + bg_items
    items_json  = json.dumps(payload_items, default=str)
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
    </style>
  </head>
  <body>
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
      const container = document.getElementById('timeline');

      const options = {{
        stack: true,
        horizontalScroll: true,
        zoomKey: 'ctrlKey',
        min: '{min_date}',
        max: '{max_date}',
        orientation: 'top',
        showCurrentTime: true,
        margin: {{ item: 8, axis: 12 }},
        template: function(item) {{
          if (item.type === 'background') return '';
          const t = item.content ? `<div class="ttl">${{esc(item.content)}}</div>` : '';
          const s = item.subtitle ? `<div class="sub">${{esc(item.subtitle)}}</div>` : '';
          return t + s;
        }},
      }};
      const timeline = new vis.Timeline(container, ITEMS, GROUPS, options);

      const pre = {selected_js};
      if (pre) {{ try {{ timeline.setSelection([pre], {{ focus:false }}); }} catch(e) {{}} }}
      try {{ timeline.fit({{ animation: true }}); }} catch (e) {{}}
    </script>
  </body>
</html>
    """
    components.html(html, height=height_px + 40, scrolling=False)