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
.block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
.card {background: rgba(127,127,127,0.06); border-radius:16px; padding:14px 16px; border:1px solid rgba(127,127,127,0.15)}
.empty {text-align:center; color:#6b7280; padding:48px 16px; border:1px dashed #e5e7eb; border-radius:16px;}
.empty b {color:#111827}
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
        "content": str(it.get("content", "")),
        "start": iso(it.get("start", "")),
        "end": iso(it.get("end", "")),
        "group": str(it.get("group", "")),
        "title": str(it.get("title", "")),       # tooltip
        "style": str(it.get("style", "")),       # css style for bar (e.g., background-color:#4caf50)
    }

def normalize_group(g: Any) -> Dict[str, Any]:
    if not isinstance(g, dict):
        g = {}
    gid = g.get("id") or g.get("content") or ""
    return {"id": str(gid), "content": str(g.get("content", gid))}

def as_list(x: Any) -> List[Any]:
    if isinstance(x, list):
        return x
    return [] if x is None or isinstance(x, (str, bytes, dict)) else (list(x) if hasattr(x, "__iter__") else [])

def normalize_state(items_any: Any, groups_any: Any):
    items_n = [normalize_item(i) for i in as_list(items_any) if i is not None]
    groups_n = [normalize_group(g) for g in as_list(groups_any) if g is not None]
    return items_n, groups_n

def reset_defaults():
    # Start with NO categories, as requested
    st.session_state["items"] = []
    st.session_state["groups"] = []

# ---------------------- INITIAL STATE ----------------------
if "items" not in st.session_state or "groups" not in st.session_state:
    reset_defaults()

items_n, groups_n = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
st.session_state["items"] = items_n
st.session_state["groups"] = groups_n

# ---------------------- HEADER ----------------------
left, right = st.columns([1, 1], vertical_alignment="center")
with left:
    st.title("Roadmap")
    st.caption("Drag & resize on the timeline. Click bars to see comments.")
with right:
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
        group = ""  # store empty group id

    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("Start", date.today())
    with c2:
        end = st.date_input("End", date.today())

    content = st.text_input("Title", "")
    color = st.color_picker("Bar color", "#4caf50")
    comment = st.text_area("Comment (tooltip)", "")
    if st.button("Add"):
        if not isinstance(st.session_state.get("items"), list):
            st.session_state["items"] = []
        st.session_state["items"].append(
            normalize_item({
                "id": str(uuid.uuid4()),
                "content": content or "Untitled",
                "start": start,
                "end": end,
                "group": group,
                "title": comment,
                "style": f"background-color:{color}",
            })
        )
        st.success("Item added.")

    st.divider()
    st.header("🏷️ Categories")
    new_cat = st.text_input("New category id")
    cols = st.columns(2)
    if cols[0].button("Add category"):
        if new_cat and not any(g["id"] == new_cat for g in st.session_state["groups"]):
            st.session_state["groups"].append(normalize_group({"id": new_cat, "content": new_cat}))
            st.success(f"Added category “{new_cat}”.")
    if cols[1].button("Remove last category") and st.session_state["groups"]:
        removed = st.session_state["groups"].pop()
        st.warning(f"Removed “{removed['id']}”")

    st.divider()
    if st.button("🔄 Reset data"):
        reset_defaults()
        st.experimental_rerun()

# ---------------------- FILTER & SAFE COPIES ----------------------
selected_ids = {str(x) for x in (selected_groups or [])}
safe_items = []
for raw in st.session_state.get("items", []):
    it = normalize_item(raw)
    # show all items if no filter selected; otherwise filter by group id match
    if not selected_ids or str(it.get("group", "")) in selected_ids:
        safe_items.append(it)

safe_groups = []
for raw in st.session_state.get("groups", []):
    g = normalize_group(raw)
    if not selected_ids or g["id"] in selected_ids:
        safe_groups.append(g)

# ---------------------- RENDER (vis-timeline via HTML component) ----------------------
def render_timeline(items: List[Dict[str, Any]], groups: List[Dict[str, Any]]):
    options = {
        "stack": True,
        "editable": True,
        "margin": {"item": 12, "axis": 6},
        "orientation": "top",
        "multiselect": True,
        "zoomKey": "ctrlKey",
        # You can tweak more vis options here if you like
    }

    html = f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <link href="https://unpkg.com/vis-timeline@7.7.0/styles/vis-timeline-graph2d.min.css" rel="stylesheet"/>
      <script src="https://unpkg.com/vis-data@7.1.6/peer/umd/vis-data.min.js"></script>
      <script src="https://unpkg.com/vis-timeline@7.7.0/standalone/umd/vis-timeline-graph2d.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
      <style>
        #toolbar {{ display:flex; gap:8px; align-items:center; margin-bottom:8px; }}
        #tl {{ border:1px solid #e5e7eb; border-radius:12px; height:620px; }}
        .btn {{ padding:6px 10px; border:1px solid #d1d5db; border-radius:8px; background:#fff; cursor:pointer; }}
        .btn:hover {{ background:#f3f4f6; }}
      </style>
    </head>
    <body>
      <div id="toolbar">
        <button id="export" class="btn">Export PNG</button>
      </div>
      <div id="tl"></div>
      <script>
        const itemsData = new vis.DataSet({json.dumps(items)});
        const groupsData = new vis.DataSet({json.dumps(groups)});
        const container = document.getElementById('tl');
        const options = {json.dumps(options)};
        const timeline = new vis.Timeline(container, itemsData, groupsData, options);

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
    components.html(html, height=680, scrolling=False)

# Friendly empty state if no items survive filtering
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
