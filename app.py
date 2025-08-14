import json, uuid
from datetime import date
import streamlit as st
from streamlit_timeline import timeline

st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")

# ---------- THEME / CSS POLISH ----------
st.markdown("""
<style>
/* tighten layout a bit */
.block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
/* pill-style tags */
.tag {display:inline-block; padding:4px 10px; border-radius:999px; margin-right:6px; font-size:0.85rem; border:1px solid rgba(0,0,0,.08)}
/* subtle card */
.card {background: rgba(127,127,127,0.06); border-radius:16px; padding:14px 16px; border:1px solid rgba(127,127,127,0.15)}
</style>
""", unsafe_allow_html=True)

# ---------- STATE ----------
if "items" not in st.session_state:
    st.session_state.items = []
if "groups" not in st.session_state:
    st.session_state.groups = [
        {"id": "Core", "content": "Core"},
        {"id": "UX", "content": "UX"},
        {"id": "Infra", "content": "Infra"},
    ]

# ---------- HEADER ----------
left, right = st.columns([1,1], vertical_alignment="center")
with left:
    st.title("Roadmap")
    st.caption("Drag & resize on the timeline. Click bars to see comments.")
with right:
    with st.container(border=True):
        st.markdown("**Filters**")
        # category filter
        selected_groups = st.multiselect(
            "Categories", [g["id"] for g in st.session_state.groups],
            default=[g["id"] for g in st.session_state.groups],
            label_visibility="collapsed"
        )

# ---------- SIDEBAR: ADD / EDIT ----------
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
            st.session_state.items.append({
                "id": str(uuid.uuid4()),
                "content": content or "Untitled",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "group": group,
                "title": comment,                 # tooltip on hover
                "style": f"background-color:{color}"
            })
            st.success("Item added.")

    st.divider()
    st.header("🏷️ Categories")
    new_cat = st.text_input("New category id")
    if st.button("Add category"):
        if new_cat and not any(g["id"] == new_cat for g in st.session_state.groups):
            st.session_state.groups.append({"id": new_cat, "content": new_cat})
            st.success(f"Added category “{new_cat}”.")
    if st.button("Remove last category") and st.session_state.groups:
        removed = st.session_state.groups.pop()
        st.warning(f"Removed “{removed['id']}”")

    st.divider()
    st.header("📦 Import / Export")
    data = {"items": st.session_state.items, "groups": st.session_state.groups}
    st.download_button("Download JSON", data=json.dumps(data, indent=2), file_name="roadmap.json")
    uploaded = st.file_uploader("Upload JSON", type="json")
    if uploaded:
        try:
            loaded = json.load(uploaded)
            st.session_state.items = loaded.get("items", [])
            st.session_state.groups = loaded.get("groups", st.session_state.groups)
            st.success("Roadmap loaded.")
        except Exception as e:
            st.error(f"Invalid JSON: {e}")

# ---------- FILTER + TIMELINE OPTIONS ----------
visible_items = [it for it in st.session_state.items if it.get("group") in selected_groups]
groups = [g for g in st.session_state.groups if g["id"] in selected_groups]

options = {
    "stack": True,
    "editable": True,              # drag / resize
    "margin": {"item": 12, "axis": 6},
    "orientation": "top",
    "multiselect": True,
    "zoomKey": "ctrlKey",
}

payload = {"items": visible_items, "groups": groups, "options": options}

# ---------- RENDER TIMELINE ----------
st.markdown('<div class="card">', unsafe_allow_html=True)
timeline(json.dumps(payload), height=620)
st.markdown('</div>', unsafe_allow_html=True)

# ---------- SIMPLE DELETE (by id) ----------
with st.expander("Danger zone: delete item by ID"):
    del_id = st.text_input("Item ID to delete")
    if st.button("Delete item"):
        before = len(st.session_state.items)
        st.session_state.items = [i for i in st.session_state.items if i["id"] != del_id]
        st.info(f"Deleted {before - len(st.session_state.items)} item(s).")
