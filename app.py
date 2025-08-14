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
    """Return ISO string for date/datetime, else x as-is."""
    return x.isoformat() if hasattr(x, "isoformat") else x

def normalize_item(it: Any) -> Dict[str, Any]:
    """Ensure an item contains only JSON-safe primitives."""
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
    """Ensure a group is JSON-safe."""
    if not isinstance(g, dict):
        g = {}
    gid = g.get("id") or g.get("content") or "Group"
    return {"id": str(gid), "content": str(g.get("content", gid))}

def as_list(x: Any) -> List[Any]:
    """Coerce anything to a list safely."""
    if isinstance(x, list):
        return x
    if x is None:
        return []
    # Avoid turning strings/dicts into lists of chars/keys
    if isinstance(x, (str, bytes, dict)):
        return []
    try:
        return list(x)
    except Exception:
        return []

def normalize_state(items_any: Any, groups_any: Any):
    items_seq = as_list(items_any)
    groups_seq = as_list(groups_any)
    items_n = [normalize_item(i) for i in items_seq if i is not None]
    groups_n = [normalize_group(g) for g in groups_seq if g is not None]
    return items_n, groups_n

def export_payload() -> Dict[str, Any]:
    items_n, groups_n = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
    return {"items": items_n, "groups": groups_n}

# ---------------------- INITIAL STATE ----------------------
# Always coerce to normalized defaults once per run
base_items = st.session_state.get("items")
base_groups = st.session_state.get("groups")

items_n, groups_n = normalize_state(
    base_items if base_items is not None else [],
    base_groups if base_groups is not None else [
        {"id": "Core", "content": "Core"},
        {"id": "UX", "content": "UX"},
        {"id": "Infra", "content": "Infra"},
    ],
)

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
    with st.form("add_item", clear_on_submit=True):
        content = st.text_input("Title", "")
        group = st.selectbox("Category", [g["id"] for g in st.session_state.groups])
        c1, c2 = st.columns(2)
        with c1:
            start = st.date_input("Start", date.today())
        with c2:
            end = st.date_input("End", date.today())
        color = st.color_picker("Bar color", "#4caf50")
        comment = st.text_area("Comment (tooltip)", "")
        submitted = st.form_submit_button("Add")
        if submitted:
            st.session_state.items.append(
                normalize_item({
                    "id": str(uuid.uuid4()),
                    "content": content or "Untitled",
                    "start": start,   # normalized to ISO
                    "end": end,       # normalized to ISO
                    "group": group,
                    "title": comment,
                    "style": f"background-color:{color}",
                })
            )
            st.success("Item added.")

    st.divider()
    st.header("🏷️ Categories")
    new_cat = st.text_input("New category id")
    if st.button("Add category"):
        if new_cat and not any(g["id"] == new_cat for g in st.session_state.groups):
            st.session_state.groups.append(normalize_group({"id": new_cat, "content": new_cat}))
            st.success(f"Added category “{new_cat}”.")
    if st.button("Remove last category") and st.session_state.groups:
        removed = st.session_state.groups.pop()
        st.warning(f"Removed “{removed['id']}”")

    st.divider()
    st.header("📦 Import / Export")

    # --- Export (safe) ---
    safe_payload = export_payload()
    st.download_button(
        "Download JSON",
        data=json.dumps(safe_payload, indent=2, default=str),
        file_name="roadmap.json",
    )

    # --- Import (normalize) ---
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

# ---------------------- FILTER + TIMELINE ----------------------
visible_items = [i for i in st.session_state.items if i.get("group") in selected_groups]
groups_for_timeline = [g for g in st.session_state.groups if g["id"] in selected_groups]

options = {
    "stack": True,
    "editable": True,              # drag / resize
    "margin": {"item": 12, "axis": 6},
    "orientation": "top",
    "multiselect": True,
    "zoomKey": "ctrlKey",
}

payload_for_timeline = {
    "items": visible_items,
    "groups": groups_for_timeline,
    "options": options
}

st.markdown('<div class="card">', unsafe_allow_html=True)
# default=str protects against any residual non-JSON values
timeline(json.dumps(payload_for_timeline, default=str), height=620)
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------- DANGER ZONE ----------------------
with st.expander("Danger zone: delete item by ID"):
    del_id = st.text_input("Item ID to delete")
    if st.button("Delete item"):
        before = len(st.session_state.items)
        st.session_state.items = [i for i in st.session_state.items if i["id"] != del_id]
        removed = before - len(st.session_state.items)
        st.info(f"Deleted {removed} item(s).")
