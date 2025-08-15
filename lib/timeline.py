import json
import streamlit.components.v1 as components

def render_timeline(items, groups):
    # Drag/resize only in canvas; no accidental add/remove
    options = {
        "editable": {"add": False, "remove": False, "updateGroup": True, "updateTime": True},
        "stack": True,
        "margin": {"item": 14, "axis": 8},
        "orientation": "top",
        "multiselect": True,
        "zoomKey": None,            # disable ctrl+wheel zoom (we'll use buttons)
        "zoomable": False,          # prevent wheel zoom entirely
        "horizontalScroll": True,
        "timeAxis": {"scale": "month", "step": 1},
        "height": "auto",           # auto height to fit items
        "autoResize": True
    }

    # Lane backgrounds
    bg_items = [{
        "id": f"bg-{g['id']}",
        "group": g["id"],
        "start": "2000-01-01",
        "end": "2100-01-01",
        "type": "background",
        "className": f"lane-{g['id']}"
    } for g in groups]

    # Styled bars (pills) – allow two lines (title + subtitle)
    styled = []
    for it in items:
        base = it.get("color", "#5ac8fa")
        style = (
            f"background: linear-gradient(180deg,{base} 0%, {base}cc 100%);"
            "border:none;color:#0f172a;border-radius:22px;box-shadow:0 2px 6px rgba(0,0,0,.08);"
            "padding:8px 14px;min-height:44px;"
        )
        styled.append({**it, "style": style})

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <!-- Modern font -->
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <link href="https://unpkg.com/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet"/>
        <script src="https://unpkg.com/vis-data@7.1.6/peer/umd/vis-data.min.js"></script>
        <script src="https://unpkg.com/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <style>
          body {{ margin:0; font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }}
          #toolbar {{ display:flex; gap:8px; align-items:center; margin: 4px 0 10px; }}
          #tl {{ border:1px solid #e5e7eb; border-radius:14px; }}
          .btn {{ padding:7px 12px; border:1px solid #d1d5db; border-radius:12px; background:#fff; cursor:pointer; font-size:13px }}
          .btn:hover {{ background:#f3f4f6; }}

          /* Left column (categories) */
          .vis-panel.vis-left {{ width: 240px !important; }}
          .vis-labelset .vis-label {{ font-weight: 700; color:#0f172a; font-family: 'Inter', sans-serif; }}

          /* Axis (year/month) */
          .vis-time-axis .vis-text {{ color:#111827; font-family: 'Inter', sans-serif; font-size: 12.5px; }}

          /* Two-line item content */
          .vis-item-content {{ white-space: normal; }}
          .inner {{ display:flex; flex-direction:column; gap:2px; }}
          .row1 {{ display:flex; align-items:center; gap:8px; }}
          .title {{ font-weight:700; font-size:13.5px; line-height:1.1; }}
          .subtitle {{ font-size:12px; color:#334155; opacity:.95; line-height:1.1; }}
          .status {{ font-weight:600; background:#0ea5e9; color:#fff; padding:2px 8px; border-radius:999px; font-size:10px; height:18px; }}

          .vis-item.vis-background {{ border-radius:16px; }}
          .vis-delete {{ display:none !important; }}
        </style>
      </head>
      <body>
        <div id="toolbar">
          <button id="export" class="btn">Export PNG</button>
          <button id="today" class="btn">Today</button>
          <button id="zin" class="btn">Zoom In</button>
          <button id="zout" class="btn">Zoom Out</button>
        </div>
        <div id="tl"></div>

        <script>
          const itemsData  = new vis.DataSet({json.dumps(styled)});
          const groupsData = new vis.DataSet({json.dumps(groups)});
          const bgData     = new vis.DataSet({json.dumps(bg_items)});

          const container  = document.getElementById('tl');
          const timeline   = new vis.Timeline(
            container,
            new vis.DataSet([...bgData.get(), ...itemsData.get()]),
            groupsData,
            {json.dumps(options)}
          );

          // Rich template (title + optional status pill + subtitle)
          timeline.setOptions({{
            template: function (item) {{
              if (!item || item.type === 'background') return '';
              const t = item.content ? `<span class="title">${{item.content}}</span>` : '';
              const s = item.status ? `<span class="status">${{item.status}}</span>` : '';
              const sub = item.subtitle ? `<span class="subtitle">${{item.subtitle}}</span>` : '';
              return `<div class="inner"><div class="row1">${{t}}${{s}}</div>${{sub}}</div>`;
            }}
          }});

          // lane tints
          const styleEl = document.createElement('style');
          styleEl.innerHTML = {json.dumps("".join([f".lane-{g['id']}{{ background:{g['laneColor']}; }} " for g in groups]))};
          document.head.appendChild(styleEl);

          // Today marker + center/zoom helpers
          function addToday() {{
            const now = new Date();
            if (!timeline.customTimes || !timeline.customTimes.get('today')) {{
              timeline.addCustomTime(now, 'today');
            }} else {{
              timeline.setCustomTime(now, 'today');
            }}
            const el = timeline.customTimes.get('today')?.line;
            if (el) {{ el.style.background = '#3b82f6'; el.style.width = '2px'; }}
          }}

          function centerToToday() {{
            const now = new Date();
            const span = 1000 * 60 * 60 * 24 * 90; // +/- 90 days
            timeline.setWindow(new Date(+now - span), new Date(+now + span), {{ animation: true }});
            timeline.moveTo(now, {{ animation: true }});
          }}

          addToday();
          centerToToday();

          // Buttons
          document.getElementById('today').addEventListener('click', () => {{
            addToday();
            centerToToday();
          }});
          document.getElementById('export').addEventListener('click', async () => {{
            const canvas = await html2canvas(container, {{backgroundColor: '#ffffff', useCORS: true}});
            const link = document.createElement('a');
            link.download = 'roadmap.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
          }});
          document.getElementById('zin').addEventListener('click', () => timeline.zoomIn(0.5));
          document.getElementById('zout').addEventListener('click', () => timeline.zoomOut(0.5));
        </script>
      </body>
    </html>
    """
    components.html(html, height=700, scrolling=False)
