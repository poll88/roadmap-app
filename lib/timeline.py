import json
import streamlit.components.v1 as components

def render_timeline(items, groups):
    # ---- computed height (80px per group + header), min 260 ----
    rows = max(1, len(groups))
    height_px = max(260, 80 * rows + 120)

    # Prepare JSON strings to avoid f-string brace pitfalls
    items_json  = json.dumps(items)
    groups_json = json.dumps(groups)
    # Background lane items
    bg_items = [{
        "id": f"bg-{g['id']}",
        "group": g["id"],
        "start": "2000-01-01",
        "end": "2100-01-01",
        "type": "background",
        "className": f"lane-{g['id']}"
    } for g in groups]
    bg_json = json.dumps(bg_items)

    # Inline CSS for lane tints
    lane_css = "".join([f".lane-{g['id']}{{{{ background:{g['laneColor']}; }}}} " for g in groups])

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <link href="https://unpkg.com/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet"/>
        <script src="https://unpkg.com/vis-data@7.1.6/peer/umd/vis-data.min.js"></script>
        <script src="https://unpkg.com/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <style>
          body {{ margin:0; font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }}
          #toolbar {{ display:flex; gap:8px; align-items:center; margin: 4px 0 10px; }}
          #tl {{ border:1px solid #e5e7eb; border-radius:14px; height:{height_px}px; }}
          .btn {{ padding:7px 12px; border:1px solid #d1d5db; border-radius:12px; background:#fff; cursor:pointer; font-size:13px }}
          .btn:hover {{ background:#f3f4f6; }}

          .vis-panel.vis-left {{ width: 240px !important; }}
          .vis-labelset .vis-label {{ font-weight: 700; color:#0f172a; font-family: 'Inter', sans-serif; }}

          .vis-time-axis .vis-text {{ color:#111827; font-family: 'Inter', sans-serif; font-size: 12.5px; }}

          .vis-item-content {{ white-space: normal; }}
          .inner {{ display:flex; flex-direction:column; gap:2px; }}
          .row1 {{ display:flex; align-items:center; gap:8px; }}
          .title {{ font-weight:700; font-size:13.5px; line-height:1.1; }}
          .subtitle {{ font-size:12px; color:#334155; opacity:.95; line-height:1.1; }}
          .status {{ font-weight:600; background:#0ea5e9; color:#fff; padding:2px 8px; border-radius:999px; font-size:10px; height:18px; }}

          .vis-item.vis-background {{ border-radius:16px; }}
          .vis-delete {{ display:none !important; }}
          /* lane tints injected below */
        </style>
      </head>
      <body>
        <div id="toolbar">
          <button id="btn-export" class="btn">Export PNG</button>
          <button id="btn-today"  class="btn">Today</button>
          <button id="btn-zoom-in"  class="btn">Zoom In</button>
          <button id="btn-zoom-out" class="btn">Zoom Out</button>
        </div>
        <div id="tl"></div>

        <script>
          // Data from Python
          const ITEMS   = JSON.parse({json.dumps(items_json)});
          const GROUPS  = JSON.parse({json.dumps(groups_json)});
          const BG      = JSON.parse({json.dumps(bg_json)});

          // Style for lane tints
          const styleEl = document.createElement('style');
          styleEl.innerHTML = {json.dumps(lane_css)};
          document.head.appendChild(styleEl);

          // Decorate items (style + keep subtitle/status)
          const styled = ITEMS.map(it => {{
            const base = it.color || "#5ac8fa";
            const style = [
              "background: linear-gradient(180deg,"+base+" 0%,"+base+"cc 100%)",
              "border:none",
              "color:#0f172a",
              "border-radius:22px",
              "box-shadow:0 2px 6px rgba(0,0,0,.08)",
              "padding:8px 14px",
              "min-height:44px"
            ].join(";");
            return Object.assign({{}}, it, {{ style }});
          }});

          // Build timeline
          const container  = document.getElementById('tl');
          const itemsDS    = new vis.DataSet([...BG, ...styled]);
          const groupsDS   = new vis.DataSet(GROUPS);

          const options = {{
            editable: {{ add:false, remove:false, updateGroup:true, updateTime:true }},
            stack: true,
            margin: {{ item:14, axis:8 }},
            orientation: "top",
            multiselect: true,
            zoomKey: "ctrlKey",     // Ctrl+wheel zooms
            zoomable: true,
            horizontalScroll: false, // default wheel -> page scrolls
            timeAxis: {{ scale:"month", step:1 }}
          }};

          const timeline = new vis.Timeline(container, itemsDS, groupsDS, options);

          // Rich template: title + status pill + subtitle
          timeline.setOptions({{
            template: function(item) {{
              if (!item || item.type === 'background') return '';
              const t   = item.content  ? `<span class="title">${{item.content}}</span>`     : '';
              const pill= item.status   ? `<span class="status">${{item.status}}</span>`     : '';
              const sub = item.subtitle ? `<span class="subtitle">${{item.subtitle}}</span>` : '';
              return `<div class="inner"><div class="row1">${{t}}${{pill}}</div>${{sub}}</div>`;
            }}
          }});

          // Today line
          function showToday() {{
            const now = new Date();
            if (!timeline.customTimes || !timeline.customTimes.get('today')) {{
              timeline.addCustomTime(now, 'today');
            }} else {{
              timeline.setCustomTime(now, 'today');
            }}
            const line = timeline.customTimes.get('today')?.line;
            if (line) {{ line.style.background = '#3b82f6'; line.style.width = '2px'; }}
          }}

          // Fit to data (not the whole century)
          function fitToData() {{
            const realItems = styled.filter(i => !i.type || i.type !== 'background');
            if (realItems.length === 0) return;
            const starts = realItems.map(i => new Date(i.start)).filter(d => !isNaN(+d));
            const ends   = realItems.map(i => new Date(i.end   || i.start)).filter(d => !isNaN(+d));
            if (starts.length === 0 || ends.length === 0) return;
            const min = new Date(Math.min.apply(null, starts));
            const max = new Date(Math.max.apply(null, ends));
            const pad = (max - min) * 0.08 + 1000*60*60*24*7; // 8% + 1 week
            timeline.setWindow(new Date(min - pad), new Date(+max + pad), {{ animation: true }});
          }}

          // Buttons
          document.getElementById('btn-export').addEventListener('click', async () => {{
            const canvas = await html2canvas(container, {{backgroundColor:'#ffffff', useCORS:true}});
            const link = document.createElement('a');
            link.download = 'roadmap.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
          }});
          document.getElementById('btn-today').addEventListener('click', () => {{
            showToday();
            const now = new Date();
            const span = 1000 * 60 * 60 * 24 * 90; // +/- 90 days
            timeline.setWindow(new Date(+now - span), new Date(+now + span), {{ animation: true }});
            timeline.moveTo(now, {{ animation: true }});
          }});
          document.getElementById('btn-zoom-in').addEventListener('click',  () => timeline.zoomIn(0.5));
          document.getElementById('btn-zoom-out').addEventListener('click', () => timeline.zoomOut(0.5));

          // Wheel behavior:
          //  - default wheel: bubble -> page scrolls
          //  - Shift + wheel: horizontal pan (prevent page scroll)
          //  - Ctrl  + wheel: zoom (handled by vis via zoomKey, but we prevent page zoom)
          function attachWheelHandlers(el) {{
            el.addEventListener('wheel', (e) => {{
              if (e.shiftKey) {{
                e.preventDefault();
                const w = timeline.getWindow();
                const span = w.end - w.start;
                const shift = span * 0.15 * Math.sign(e.deltaY);
                timeline.setWindow(new Date(+w.start + shift), new Date(+w.end + shift));
              }} else if (e.ctrlKey) {{
                e.preventDefault();
                if (e.deltaY < 0) timeline.zoomIn(0.5); else timeline.zoomOut(0.5);
              }} else {{
                // do nothing -> page scrolls
              }}
            }}, {{ passive:false }});
          }}

          // Attach to the main center panel (not just the outer container)
          function hookPanels() {{
            const center = container.querySelector('.vis-panel.vis-center');
            if (center) attachWheelHandlers(center);
          }
          hookPanels();
          // re-hook after redraws
          timeline.on('changed', hookPanels);

          // Initial view
          showToday();
          fitToData();
        </script>
      </body>
    </html>
    """

    # Give the outer iframe enough room for toolbar + timeline
    components.html(html, height=height_px + 110, scrolling=False)
