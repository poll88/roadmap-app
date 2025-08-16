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

    # Dynamic min date: at most 1 year ago
    min_date = (date.today() - timedelta(days=365)).isoformat()

    # Background rows tint (capped at 2028)
    bg_items = [{
        "id": f"bg-{g['id']}",
        "group": g["id"],
        "start": min_date,
        "end": "2028-12-31",
        "type": "background",
        "className": "row-bg"
    } for g in groups]

    # IMPORTANT: real items FIRST, then backgrounds (so selection prefers real items)
    items_json  = json.dumps(items + bg_items)
    groups_json = json.dumps(groups)
    selected_id_js = json.dumps(selected_id or "")

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
      body, #timeline, .toolbar, .vis-timeline, .vis-panel, .vis-label, .vis-time-axis, .vis-item, .vis-item-content {{ font-family: var(--font); }}
      #timeline {{ height:{height_px}px; background:#fff; border-radius:14px; border:1px solid #e7e9f2}}
      .row-bg {{ background: rgba(37,99,235,.05) }}

      .vis-time-axis .text {{ font-size:12px; font-weight:500; }}
      .vis-labelset .vis-label .vis-inner {{ font-weight:600; }}

      .toolbar {{ display:flex; gap:8px; margin:8px 0 12px }}
      .toolbar button {{ padding:6px 10px; border:1px solid #e5e7eb; background:#fff; border-radius:8px; cursor:pointer }}
      .toolbar button:hover {{ background:#f3f4f6 }}

      /* Item content (title + subtitle) */
      .itm {{ display:flex; flex-direction:column; gap:2px; line-height:1.15; cursor:pointer }}
      .itm .ttl {{ font-weight:600 }}
      .itm .sub {{ font-size:12px; opacity:.85; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:260px }}

      /* Highlight selected item */
      .vis-item.vis-selected {{
        box-shadow: 0 0 0 2px rgba(37,99,235,.7) inset, 0 0 0 2px rgba(37,99,235,.25);
        border-color:#2563eb !important;
      }}
    </style>
  </head>
  <body>
    <div class="toolbar">
      <button id="btn-today">Today</button>
      <button id="btn-fit">Fit</button>
    </div>
    <div id="timeline"></div>

    <script src="{_VIS_JS}"></script>
    <script>
      // ---- Streamlit glue ----
      function sendToStreamlit(value) {{
        // Preferred (newer Streamlit)
        if (window.Streamlit && typeof window.Streamlit.setComponentValue === "function") {{
          window.Streamlit.setComponentValue(value);
          return;
        }}
        // Fallback for older Streamlit
        try {{
          window.parent.postMessage({{
            isStreamlitMessage: true,
            type: "streamlit:setComponentValue",
            value
          }}, "*");
        }} catch (e) {{}}
      }}

      const items  = new vis.DataSet({items_json});
      const groups = new vis.DataSet({groups_json});
      const container = document.getElementById('timeline');

      function escapeHtml(s) {{
        return String(s ?? "")
          .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
      }}

      const options = {{
        stack: true,
        selectable: true,
        multiselect: false,
        horizontalScroll: true,
        zoomKey: 'ctrlKey',
        min: '{min_date}',
        max: '2028-12-31',
        showCurrentTime: true,
        orientation: 'top',
        margin: {{ item: 8, axis: 12 }},
        template: function (item) {{
          if (item.type === 'background') return '';
          const title = item.content ? `<div class="ttl">${{escapeHtml(item.content)}}</div>` : '';
          const sub = item.subtitle ? `<div class="sub">${{escapeHtml(item.subtitle)}}</div>` : '';
          return `<div class="itm" data-id="${{item.id}}">${{title}}${{sub}}</div>`;
        }},
      }};

      const timeline = new vis.Timeline(container, items, groups, options);

      // Preselect id from Python
      const preselectId = {selected_id_js};
      if (preselectId) {{
        try {{ timeline.setSelection([preselectId], {{ focus: false }}); }} catch (e) {{}}
      }}

      // Click ANYWHERE on the bar -> send selection to Streamlit
      timeline.on('click', (props) => {{
        const id = props && props.item ? props.item : null;
        if (!id || String(id).startsWith('bg-')) return;
        const itm = items.get(id);
        // Ensure color is present even if vis drops it
        if (itm && !itm.color && itm.style) {{
          const m = String(itm.style).match(/background:([^;]+)/);
          if (m) itm.color = m[1].trim();
        }}
        sendToStreamlit({{ type: 'select', item: itm }});
      }});

      // Also handle keyboard selection changes
      timeline.on('select', (props) => {{
        const id = props && props.items && props.items[0] ? props.items[0] : null;
        if (!id || String(id).startsWith('bg-')) return;
        const itm = items.get(id);
        if (itm && !itm.color && itm.style) {{
          const m = String(itm.style).match(/background:([^;]+)/);
          if (m) itm.color = m[1].trim();
        }}
        sendToStreamlit({{ type: 'select', item: itm }});
      }});

      // Toolbar actions
      function fit() {{ try {{ timeline.fit({{ animation: true }}); }} catch(e){{}} }}
      document.getElementById('btn-fit').onclick = fit;
      document.getElementById('btn-today').onclick = () => {{
        const now = new Date();
        timeline.moveTo(now, {{ animation: true }});
      }};

      setTimeout(fit, 50);

      // Smooth trackpad/mouse horizontal wheel (hold Shift to zoom)
      function attachWheel(el) {{
        el.addEventListener('wheel', (e) => {{
          if (!e.shiftKey || e.deltaY === 0) return;
          e.preventDefault();
          const sc = e.deltaY > 0 ? 1.05 : 0.95;
          timeline.zoom(sc, {{ animation: false }});
        }}, {{ passive: false }});
      }}
      const center = container.querySelector('.vis-panel.vis-center') || container;
      attachWheel(center);
    </script>
  </body>
</html>
    """
    # Return the selection payload to Python (Streamlit will rerun on setComponentValue)
    return components.html(html, height=height_px + 80, scrolling=False)