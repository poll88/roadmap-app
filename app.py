import json
import uuid
from datetime import date
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components

# ---------------------- PAGE SETUP ----------------------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown("""
<style>
:root{
  --bg: #ffffff;
  --muted: #6b7280;
  --border: #e5e7eb;
  --card: #f7f8fb;
  --primary: #2563eb;
}
.block-container {padding-top: 1.2rem; padding-bottom: 0.5rem; max-width: 1200px;}
.card {background: var(--card); border-radius:18px; padding:14px 16px; border:1px solid #e7e9f2}
.empty {text-align:center; color:var(--muted); padding:56px 16px; border:1px dashed var(--border); border-radius:16px;}
.empty b {color:#0f172a}
h1 {letter-spacing: .2px}
</style>
""", unsafe_allow_html=True)

# ---------------------- HELPERS ----------------------
def iso(x: Any) -> Any:
    return x.isoformat() if hasattr(x, "isoformat") else x

def normalize_item(it: Any) -> Dict[str, Any]:
    if not isinstance(it, dict):
        it = {}
    return {
        "id": str(it.get("id") or uuid.uuid4()),
        "content": str(it.get("content", "")),     # title inside bar (bold)
        "subtitle": str(it.get("subtitle", "")),   # small text under title
        "status": str(it.get("status", "")),       # small pill (e.g., Phase-In / Stock Clearance)
        "start": iso(it.get("start", "")),
        "end": iso(it.get("end", "")),
        "group": str(it.get("group", "")),
        "title": str(it.get("title", "")),         # tooltip
        "color": str(it.get("color", "#5ac8fa")),  # base color, used for gradient
        "style": str(it.get("style", "")),         # gets overridden by color gradient
    }

def normalize_group(g: Any) -> Dict[str, Any]:
    if not isinstance(g, dict):
        g = {}
    gid = g.get("id") or g.get("content") or ""
    return {
        "id": str(gid),
        "content": str(g.get("content", gid)),
        "laneColor": str(g.get("laneColor", "rgba(37,99,235,.06)")),  # band tint
    }

def as_list(x: Any) -> List[Any]:
    if isinstance(x, list):
        return x
    return [] if x is None or isinstance(x, (str, bytes, dict)) else (list(x) if hasattr(x, "__iter__") else [])

def normalize_state(items_any: Any, groups_any: Any):
    items_n = [normalize_item(i) for i in as_list(items_any) if i is not None]
    groups_n = [normalize_group(g) for g in as_list(groups_any) if g is not None]
    return items_n, groups_n

def reset_defaults():
    # start empty (you’ll add categories)
    st.session_state["items"] = []
    st.session_state["groups"] = []

# ---------------------- INITIAL STATE ----------------------
if "items" not in st.session_state or "groups" not in st.session_state:
    reset_defaults()

items_n, groups_n = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
st.session_state["items"] = items_n
st.session_state["groups"] = groups_n

# ---------------------- HEADER ----------------------
lcol, rcol = st.columns([1, 1], vertical_alignment="center")
with lcol:
    st.title("Roadmap")
    st.caption("Drag & resize on the timeline. Click bars to see comments.")
with rcol:
    with st.container(border=True):
        st.markdown("**Filters**")
        selected_groups = st.multiselect(
            "Categories",
            [g["id"] for g in st.session_state["groups"]],
            default=[g["id"] for g in st.session_state["groups"]],
            label_visibility="collapsed",
            placeholder="No options to select"
        )

# ---------------------- SIDEBAR ----------------------
with st.sidebar:
    st.header("➕ Add item")

    group_ids = [g["id"] for g in st.session_state["groups"]]
    group = st.selectbox("Category", group_ids or ["(none)"])
    if group == "(none)":
        group = ""

    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("Start", date.today())
    with c2:
        end = st.date_input("End", date.today())

    content = st.text_input("Title (bold on bar)", "")
    subtitle = st.text_input("Subtitle (smaller)", "")
    status = st.text_input("Status pill (optional)", "")  # e.g. "Phase‑In", "Stock Clearance"
    color = st.color_picker("Bar color", "#5ac8fa")
    comment = st.text_area("Tooltip (hover)", "")

    if st.button("Add"):
        if not isinstance(st.session_state.get("items"), list):
            st.session_state["items"] = []
        st.session_state["items"].append(
            normalize_item({
                "id": str(uuid.uuid4()),
                "content": content or "Untitled",
                "subtitle": subtitle,
                "status": status,
                "start": start,
                "end": end,
                "group": group,
                "title": comment,
                "color": color,
            })
        )
        st.success("Item added.")

    st.divider()
    st.header("🏷️ Categories")
    new_cat = st.text_input("New category id (shown on the left)")
    lane_color = st.color_picker("Lane tint", "#e8efff")
    cols = st.columns(2)
    if cols[0].button("Add category"):
        if new_cat and not any(g["id"] == new_cat for g in st.session_state["groups"]):
            st.session_state["groups"].append(
                normalize_group({"id": new_cat, "content": new_cat, "laneColor": lane_color})
            )
            st.success(f"Added category “{new_cat}”.")
    if cols[1].button("Remove last category") and st.session_state["groups"]:
        removed = st.session_state["groups"].pop()
        st.warning(f"Removed “{removed['id']}”")

    st.divider()
    if st.button("🔄 Reset data"):
        reset_defaults()
        st.experimental_rerun()

# ---------------------- FILTER ----------------------
selected_ids = {str(x) for x in (selected_groups or [])}
safe_items = []
for raw in st.session_state.get("items", []):
    it = normalize_item(raw)
    if not selected_ids or str(it.get("group", "")) in selected_ids:
        safe_items.append(it)

safe_groups = []
for raw in st.session_state.get("groups", []):
    g = normalize_group(raw)
    if not selected_ids or g["id"] in selected_ids:
        safe_groups.append(g)

# ---------------------- RENDER (vis-timeline with modern template) ----------------------
def render_timeline(items: List[Dict[str, Any]], groups: List[Dict[str, Any]]):
    # We’ll paint group “lanes” with background items and use an itemTemplate for the pill.
    options = {
        "stack": True,
        "editable": True,
        "margin": {"item": 14, "axis": 8},
        "orientation": "top",
        "multiselect": True,
        "zoomKey": "ctrlKey",
        "minHeight": "620px",
        "timeAxis": {"scale": "month", "step": 1},
        "horizontalScroll": True,
        "zoomMin": 1000 * 60 * 60 * 24 * 7,      # 1 week
        "zoomMax": 1000 * 60 * 60 * 24 * 365 * 4 # 4 years
    }

    # Build background items per group to create soft category bands
    bg_items = []
    for g in groups:
        bg_items.append({
            "id": f"bg-{g['id']}",
            "group": g["id"],
            "start": "2000-01-01",  # far past
            "end": "2100-01-01",    # far future
            "type": "background",
            "className": f"lane-{g['id']}"
        })

    # Vis data
    all_items = []
    for it in items:
        # compute a nice gradient from the base color
        base = it.get("color", "#5ac8fa")
        style = (
            f"background: linear-gradient(180deg,{base} 0%, {base}cc 100%);"
            "border:none;color:#0f172a;border-radius:22px;box-shadow:0 2px 6px rgba(0,0,0,.08);"
            "padding:0 10px;height:36px;display:flex;align-items:center;"
        )
        all_items.append({
            **it,
            "style": style
        })

    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <link href="https://unpkg.com/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet"/>
      <script src="https://unpkg.com/vis-data@7.1.6/peer/umd/vis-data.min.js"></script>
      <script src="https://unpkg.com/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
      <style>
        body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; }}
        #toolbar {{ display:flex; gap:8px; align-items:center; margin: 4px 0 10px; }}
        #tl {{ border:1px solid #e5e7eb; border-radius:14px; height:640px; }}
        .btn {{ padding:7px 12px; border:1px solid #d1d5db; border-radius:10px; background:#fff; cursor:pointer; font-size:13px }}
        .btn:hover {{ background:#f3f4f6; }}
        .vis-panel.vis-left {{ width: 240px !important; }}         /* big category column */
        .vis-labelset .vis-label {{ font-weight: 700; color:#0f172a; }}
        .vis-time-axis .vis-text {{ color:#111827; }}
        .vis-item .title {{ font-weight:700; font-size:12.5px; line-height: 1.1; }}
        .vis-item .subtitle {{ display:block; font-size:11px; color:#334155; opacity:.9 }}
        .vis-item .status {{ margin-left:8px; font-weight:600; background: #0ea5e9; color:#fff;
                             padding:2px 8px; border-radius:999px; font-size:10px; }}
        /* Rounded ends on background lanes */
        .vis-item.vis-background {{ border-radius:16px; }}
      </style>
    </head>
    <body>
      <div id="toolbar">
        <button id="export" class="btn">Export PNG</button>
        <button id="today" class="btn">Today</button>
      </div>
      <div id="tl"></div>

      <script>
        const itemsData = new vis.DataSet({json.dumps(all_items)});
        const bgData    = new vis.DataSet({json.dumps(bg_items)});
        const groupsData = new vis.DataSet({json.dumps(groups)});
        const container = document.getElementById('tl');
        const options = {json.dumps(options)};

        // Merge background items + normal items (background renders behind)
        const merged = new vis.DataSet([...bgData.get(), ...itemsData.get()]);
        const timeline = new vis.Timeline(container, merged, groupsData, options);

        // Item template for modern pill content
        timeline.setOptions({{
          template: function (item, element, data) {{
            if (!item || item.type === 'background') return '';
            const title = item.content || '';
            const sub = item.subtitle ? `<span class="subtitle">${{item.subtitle}}</span>` : '';
            const status = item.status ? `<span class="status">${{item.status}}</span>` : '';
            return `<span class="title">${{title}}</span>${{status}}${{sub}}`;
          }}
        }});

        // Paint group lane tint via CSS variables per className
        const styleEl = document.createElement('style');
        styleEl.innerHTML = {json.dumps(
            "".join([f".lane-{g['id']}{{ background:{g['laneColor']}; }} " for g in groups])
        )};
        document.head.appendChild(styleEl);

        // Today marker
        function addToday() {{
          const now = new Date();
          timeline.addCustomTime(now, 'today');
          const el = timeline.customTimes.get('today').line;
          if (el) {{
            el.style.background = '#ef4444';
            el.style.width = '2px';
          }}
        }}
        addToday();

        // Buttons
        document.getElementById('today').addEventListener('click', () => {{
          const now = new Date();
          const window = timeline.getWindow();
          const span = window.end - window.start;
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

if not safe_items:
    st.markdown(
        '<div class="empty"><b>No items yet.</b><br/>Add your first event with the sidebar 👈</div>',
        unsafe_allow_html=True,
    )
else:
    render_timeline(safe_items, safe_groups)

# ---------------------- DANGER ZONE ----------------------
with st.expander("Danger zone: delete item by ID"):
    del_id = st.text_input("Item ID to delete")
    if st.button("Delete item"):
        if not isinstance(st.session_state.get("items"), list):
            st.session_state["items"] = []
        before = len(st.session_state["items"])
        st.session_state["items"] = [i for i in st.session_state["items"] if normalize_item(i)["id"] != del_id]
        st.info(f"Deleted {before - len(st.session_state['items'])} item(s).")
