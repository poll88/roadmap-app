import json
import streamlit.components.v1 as components

def render_timeline(items, groups):
    # Only drag/resize inline; no delete/add buttons
    options = {
        "editable": {"add": False, "remove": False, "updateGroup": True, "updateTime": True},
        "stack": True,
        "margin": {"item": 14, "axis": 8},
        "orientation": "top",
        "multiselect": True,
        "zoomKey": "ctrlKey",
        "minHeight": "620px",
        "timeAxis": {"scale": "month", "step": 1},
        "horizontalScroll": True,
        "zoomMin": 1000 * 60 * 60 * 24 * 7,
        "zoomMax": 1000 * 60 * 60 * 24 * 365 * 4
    }

    # Background “lane” items to tint each category row
    bg_items = [{
        "id": f"bg-{g['id']}",
        "group": g["id"],
        "start": "2000-01-01",
        "end": "2100-01-01",
        "type": "background",
        "className": f"lane-{g['id']}"
    } for g in groups]

    # Style each item as a rounded glossy pill (subtitle on its own line)
    styled = []
    for it in items:
        base = it.get("color", "#5ac8fa")
        style = (
            f"background: linear-gradient(180deg,{base} 0%, {base}cc 100%);"
            "border:none;color:#0f172a;border-radius:20px;box-shadow:0 2px 6px rgba(0,0,0,.08);"
            "padding:8px 12px;min-height:44px;display:flex;align-items:flex-start;"
            "overflow:visible;"
        )
        styled.append({**it, "style": style})

    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <!-- Modern font -->
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet"/>
      <link href="https://unpkg.com/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet"/>
      <script src="https://unpkg.com/vis-data@7.1.6/peer/umd/vis-data.min.js"></script>
      <script src="https://unpkg.com/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
      <style>
        body {{ margin:0; font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }}
        #toolbar {{ display:flex; gap:8px; align-items:center; margin: 4px 0 10px; }}
        #tl {{ border:1px solid #e5e7eb; border-radius:14px; height:640px; }}
        .btn {{ padding:7px 12px; border:1px solid #d1d5db; border-radius:10px; background:#fff; cursor:pointer; font-size:13px }}
        .btn:hover {{ background:#f3f4f6; }}

        /* Left category column width + fonts */
        .vis-panel.vis-left {{ width: 240px !important; }}
        .vis-labelset .vis-label {{ font-weight: 700; color:#0f172a; font-family: 'Inter', sans-serif; font-size:14px; }}

        /* Axis fonts (months/years) */
        .vis-time-axis .vis-text {{ color:#111827; font-family:'Inter',sans-serif; font-size:12.5px; }}

        /* Item composition */
        .vis-item .pill {{ display:flex; flex-direction:column; gap:2px; line-height:1.1; }}
        .vis-item .title {{ font-weight:700; font-size:13.5px; }}
        .vis-item .subtitle {{ font-size:12px; color:#374151; opacity:.95; }}
        .vis-item .status {{ margin-left:8px; font-weight:600; background:#0ea5e9; color:#fff;
                             padding:2px 8px; border-radius:999px; font-size:10px; display:inline-block; }}

        /* Rounded lane backgrounds */
        .vis-item.vis-background {{ border-radius:16px; }}

        /* Just in case: hide built-in delete handles */
        .vis-delete {{ display:none !important; }}
      </style>
    </head>
    <body>
      <div id="toolbar">
        <button id="export" class="btn">Export PNG</button>
        <button id="today" class="btn">Today</button>
      </div>
      <div id="tl"></div>

      <script>
        const itemsData  = new vis.DataSet({json.dumps(styled)});
        const groupsData = new vis.DataSet({json.dumps(groups)});
        const bgData     = new vis.DataSet({json.dumps(bg_items)});

        const container = document.getElementById('tl');
        const timeline  = new vis.Timeline(
          container,
          new vis.DataSet([...bgData.get(), ...itemsData.get()]),
          groupsData,
          {json.dumps(options)}
        );

        // Item template: title + (optional) status pill + subtitle (new line)
        timeline.setOptions({{
          template: function (item, element, data) {{
            if (!item || item.type === 'background') return '';
            const title = item.content || '';
            const status = item.status ? `<span class="status">${{item.status}}</span>` : '';
            const sub = item.subtitle ? `<span class="subtitle">${{item.subtitle}}</span>` : '';
            return `<div class="pill"><span class="title">${{title}}</span>${{status}}${{sub}}</div>`;
          }}
        }});

        // Lane tints (category backgrounds)
        const styleEl = document.createElement('style');
        styleEl.innerHTML = {json.dumps("".join([f".lane-{g['id']}{{ background:{g['laneColor']}; }} " for g in groups]))};
        document.head.appendChild(styleEl);

        // Today marker
        function addToday() {{
          const now = new Date();
          timeline.addCustomTime(now, 'today');
          const el = timeline.customTimes.get('today').line;
          if (el) {{ el.style.background = '#ef4444'; el.style.width = '2px'; }}
        }}
        addToday();

        // Buttons
        document.getElementById('today').addEventListener('click', () => {{
          const now = new Date();
          const w = timeline.getWindow(); const span = w.end - w.start;
          timeline.setWindow(new Date(+now - span/2), new Date(+now + span/2));
        }});
        document.getElementById('export').addEventListener('click', async () => {{
          const canvas = await html2canvas(container, {{backgroundColor: '#ffffff', useCORS: true}});
          const link = document.createElement('a');
          link.download = 'roadmap.png';
          link.href = canvas.toDataURL('image/png');
          link.click();
        }});
      </script>
    </body>
    </html>
    """
    components.html(html, height=700, scrolling=False)
