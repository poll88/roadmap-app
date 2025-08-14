import json
import uuid
from datetime import date
from typing import Any, Dict, List

import streamlit as st
from streamlit_timeline import timeline

# ---------------------- PAGE SETUP ----------------------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
.tag {display:inline-block; padding:4px 10px; border-radius:999px; margin-right:6px; font-size:0.85rem; border:1px solid rgba(0,0,0,.08)}
.card {background: rgba(127,127,127,0.06); border-radius:16px; padding:14px 16px; border:1px solid rgba(127,127,127,0.15)}
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
        "title": str(it.get("title", "")),
        "style": str(it.get("style", "")),
    }

def normalize_group(g: Any) -> Dict[str, Any]:
    if not isinstance(g, dict):
        g = {}
    gid = g.get("id") or g.get("content") or "General"
    return {"id": str(gid), "content": str(g.get("content", gid))}

def as_list(x: Any) -> List[Any]:
    if isinstance(x, list):
        return x
    return [] if x is None or isinstance(x, (str, bytes, dict)) else (list(x) if hasattr(x, "__iter__") else [])

def normalize_state(items_any: Any, groups_any: Any):
    items_n = [normalize_item(i) for i in as_list(items_any) if i is not None]
    groups_n = [normalize_group(g) for g in as_list(groups_any) if g is not None]
    if not groups_n:  # ensure at least one category
        groups_n = [normalize_group({"id": "General", "content": "General"})]
    return items_n, groups_n

def export_payload() -> Dict[str, Any]:
    items_n, groups_n = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
    return {"items": items_n, "groups": groups_n}

def reset_defaults():
    st.session_state.items = []
    st.session_state.groups = [
        {"id": "Core", "content": "Core"},
        {"id": "UX", "content": "UX"},
        {"id": "Infra", "content": "Infra"},
    ]

# ---------------------- INITIAL STATE (FORCE SANITY) ----------------------
if "items" not in st.session_state and "groups" not in st.session_state:
    reset_defaults()

# Coerce to valid lists every run
items_n, groups_n = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
st.session_state.items = items_n
st.session_state.groups = groups_n

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
            [g["id"] for g in st.session_state.groups],
            default=[g["id"] for g in st.session_state.groups],
            label_visibility="collapsed",
        )

# ---------------------- SIDEBAR ----------------------
with st.sidebar:
    st.header("➕ Add item")

    # Ensure there is at least one category to select
    if not st.session_state.groups:
        st.session_state.groups = [normalize_group({"id": "General", "content": "General"})]

    group_ids = [g["id"] for g in st.session_state.groups] or ["General"]

    with st.form("add_item", clear_on_submit=True):
        content = st.text_input("Title", "")
        group = st.selectbox("Category", group_ids, index=0)
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Start", date.today())
        with c2:
            end = st.date_input("End", date.today())
        color = st.color_picker("Bar color", "#4caf50")
        comment = st.text_area("Comment (tooltip)", "")
        submitted = st.form_submit_button("Add")
        if submitted:
            # Ensure items is a list before appending
            if not isinstance(st.session_state.get("items"), list):
                st.session_state.items = []
            st.session_state.items.append(
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
        if new_cat and not any(g["id"] == new_cat for g in st.session_state.groups):
            st.session_state.groups.append(normalize_group({"id": new_cat, "content": new_cat}))
            st.success(f"Added category “{new_cat}”.")
    if cols[1].button("Remove last category") and st.session_state.groups:
        removed = st.session_state.groups.pop()
        st.warning(f"Removed “{removed['id']}”")

    st.divider()
    st.header("📦 Import / Export")
    safe_payload = export_payload()
    st.download_button(
        "Download JSON",
        data=json.dumps(safe_payload, indent=2, default=str),
        file_name="roadmap.json",
    )

    uploaded = st.file_uploader("Upload JSON", type="json")
    if uploaded:
        try:
            loaded = json.load(uploaded)
            items_in = loaded.get("items", [])
            groups_in = loaded.get("groups", [])
            st.session_state.items, st.session_state.groups = normalize_state(items_in, groups_in)
            st.success("Roadmap loaded.")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

    st.divider()
    if st.button("🔄 Reset data (factory defaults)"):
        reset_defaults()
        st.experimental_rerun()

# ---------------------- FILTER + TIMELINE (HARDENED) ----------------------
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

options = {
    "stack": True,
    "editable": True,
    "margin": {"item": 12, "axis": 6},
    "orientation": "top",
    "multiselect": True,
    "zoomKey": "ctrlKey",
}

payload_for_timeline = {"items": safe_items, "groups": safe_groups, "options": options}

st.markdown('<div class="card">', unsafe_allow_html=True)
timeline(json.dumps(payload_for_timeline, default=str), height=620)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------- DANGER ZONE ----------------------
with st.expander("Danger zone: delete item by ID"):
    del_id = st.text_input("Item ID to delete")
    if st.button("Delete item"):
        if not isinstance(st.session_state.get("items"), list):
            st.session_state.items = []
        before = len(st.session_state.items)
        st.session_state.items = [i for i in st.session_state.items if normalize_item(i)["id"] != del_id]
        st.info(f"Deleted {before - len(st.session_state.items)} item(s).")
