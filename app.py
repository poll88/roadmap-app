import uuid
from datetime import date
from typing import Any, Dict
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, ensure_range, export_items_groups
)
from lib.timeline import render_timeline

st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ---------- SESSION ----------
if "items" not in st.session_state:
    st.session_state["items"] = []
if "groups" not in st.session_state:
    st.session_state["groups"] = []
normalize_state(st.session_state)

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("📅 Add / Edit")

    # Create categories (groups)
    group_names = {g["content"]: g["id"] for g in st.session_state["groups"]}
    new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")
    if new_group_name and new_group_name not in group_names:
        g = normalize_group({"content": new_group_name, "order": len(st.session_state["groups"])})
        st.session_state["groups"].append(g)
        group_names[new_group_name] = g["id"]

    colA, colB = st.columns(2)
    start = colA.date_input("Start", value=date.today())
    end   = colB.date_input("End", value=date.today())
    start, end = ensure_range(start, end)

    content = st.text_input("Title", placeholder="Item title")
    subtitle = st.text_input("Subtitle (optional)", placeholder="Short note")
    color = st.color_picker("Bar color", "#2563EB")

    # Add item form (auto-assigns to first category if any exist)
    with st.form("add_item_form", clear_on_submit=True):
        submitted = st.form_submit_button("➕ Add item")
        if submitted:
            gid = next(iter(group_names.values()), "")  # auto-assign or ungrouped
            item = normalize_item({
                "content": content, "subtitle": subtitle,
                "start": start, "end": end, "group": gid, "color": color,
                "style": f"background:{color}; border-color:{color}"
            })
            st.session_state["items"].append(item)
            st.success("Item added.")

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        reset_defaults(st.session_state)
        st.experimental_rerun()

    exported = export_items_groups(st.session_state)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded:
        try:
            import json
            payload = json.loads(uploaded.read().decode("utf-8"))
            items = [normalize_item(x) for x in payload.get("items", [])]
            groups = [normalize_group(x) for x in payload.get("groups", [])]
            st.session_state["items"] = items
            st.session_state["groups"] = groups
            st.success("Imported.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

# ---------- MAIN ----------
st.title("Roadmap Timeline")
if not st.session_state["items"]:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>', unsafe_allow_html=True)
else:
    # Optional filter by categories
    selected_names = st.multiselect("Filter categories", [g["content"] for g in st.session_state["groups"]])
    selected_ids = {g["id"] for g in st.session_state["groups"] if g["content"] in selected_names} if selected_names else set()

    items_view = [i for i in st.session_state["items"] if not selected_ids or i.get("group","") in selected_ids]
    groups_view = [normalize_group(g) for g in st.session_state["groups"] if not selected_ids or g["id"] in selected_ids]

    render_timeline(items_view, groups_view)
