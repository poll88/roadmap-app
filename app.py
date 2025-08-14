import uuid
from datetime import date, timedelta
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

# ----------- INITIAL STATE -----------
if "items" not in st.session_state or "groups" not in st.session_state:
    reset_defaults(st.session_state)

# normalize every run (defensive)
st.session_state["items"], st.session_state["groups"] = normalize_state(
    st.session_state.get("items"), st.session_state.get("groups")
)

# ----------- HEADER -----------
c1, c2 = st.columns([1, 1], vertical_alignment="center")
with c1:
    st.title("Roadmap")
    st.caption("Drag & resize on the timeline. Click bars to see comments.")
with c2:
    with st.container(border=True):
        st.markdown("**Filters**")
        selected_groups = st.multiselect(
            "Categories",
            [g["id"] for g in st.session_state["groups"]],
            default=[g["id"] for g in st.session_state["groups"]],
            label_visibility="collapsed",
            placeholder="No options to select",
        )

# ----------- SIDEBAR: ADD / EDIT -----------
with st.sidebar:
    st.header("➕ Add item")
    group_ids = [g["id"] for g in st.session_state["groups"]]
    group = st.selectbox("Category", group_ids or ["(none)"])
    if group == "(none)": group = ""

    c3, c4 = st.columns(2)
    with c3:
        start = st.date_input("Start", date.today())
    with c4:
        end = st.date_input("End", date.today())

    title = st.text_input("Title (bold on bar)", "")
    subtitle = st.text_input("Subtitle (smaller)", "")
    status = st.text_input("Status pill (optional)", "")
    color = st.color_picker("Bar color", "#5ac8fa")
    tooltip = st.text_area("Tooltip (hover)", "")

    if st.button("Add"):
        s, e = ensure_range(start, end)
        st.session_state["items"].append(normalize_item({
            "id": str(uuid.uuid4()),
            "content": title or "Untitled",
            "subtitle": subtitle,
            "status": status,
            "start": s,
            "end": e,
            "group": group,
            "title": tooltip,
            "color": color,
        }))
        st.success("Item added.")

    st.divider()
    st.header("✏️ Edit item")
    # simple picker labelled by title (fallback to id)
    options = {f'{i.get("content") or "Untitled"} · {i["id"][:6]}': i["id"] for i in st.session_state["items"]}
    picked = st.selectbox("Select an item", list(options.keys()) or ["(none)"])
    if picked != "(none)":
        item_id = options[picked]
        # find the item
        cur: Dict[str, Any] = next((normalize_item(i) for i in st.session_state["items"] if str(i.get("id")) == item_id), None)
        if cur:
            et1, et2 = st.columns(2)
            with et1:
                new_title = st.text_input("Title", cur["content"], key=f"et_{item_id}_title")
                new_status = st.text_input("Status", cur.get("status",""), key=f"et_{item_id}_status")
                new_group = st.selectbox("Category", group_ids or ["(none)"], index=(group_ids.index(cur["group"]) if cur["group"] in group_ids else 0), key=f"et_{item_id}_group")
            with et2:
                new_sub = st.text_input("Subtitle", cur.get("subtitle",""), key=f"et_{item_id}_sub")
                new_color = st.color_picker("Bar color", cur.get("color","#5ac8fa"), key=f"et_{item_id}_col")
            es1, es2 = st.columns(2)
            with es1:
                new_start = st.date_input("Start", date.fromisoformat(cur["start"][:10]) if cur["start"] else date.today(), key=f"et_{item_id}_start")
            with es2:
                new_end = st.date_input("End", date.fromisoformat(cur["end"][:10]) if cur["end"] else date.today(), key=f"et_{item_id}_end")
            new_tip = st.text_area("Tooltip", cur.get("title",""), key=f"et_{item_id}_tip")

            cols = st.columns(2)
            if cols[0].button("Save changes", key=f"save_{item_id}"):
                s2, e2 = ensure_range(new_start, new_end)
                # write back
                for k, it in enumerate(st.session_state["items"]):
                    if str(it.get("id")) == item_id:
                        st.session_state["items"][k] = normalize_item({
                            "id": item_id,
                            "content": new_title or "Untitled",
                            "subtitle": new_sub,
                            "status": new_status,
                            "start": s2, "end": e2,
                            "group": ("" if new_group == "(none)" else new_group),
                            "title": new_tip, "color": new_color
                        })
                        break
                st.success("Saved.")

            if cols[1].button("Delete item", key=f"del_{item_id}"):
                st.session_state["items"] = [i for i in st.session_state["items"] if str(i.get("id")) != item_id]
                st.warning("Item deleted.")

    st.divider()
    st.header("🏷️ Categories")
    new_cat = st.text_input("New category id")
    lane_color = st.color_picker("Lane tint", "#e8efff")
    c5, c6 = st.columns(2)
    if c5.button("Add category"):
        if new_cat and not any(g["id"] == new_cat for g in st.session_state["groups"]):
            st.session_state["groups"].append(normalize_group({"id": new_cat, "content": new_cat, "laneColor": lane_color}))
            st.success(f'Added “{new_cat}”.')
    if c6.button("Remove last category") and st.session_state["groups"]:
        removed = st.session_state["groups"].pop()
        st.warning(f'Removed “{removed["id"]}”.')

    st.divider()
    if st.button("🔄 Reset data"):
        reset_defaults(st.session_state)
        st.experimental_rerun()

# ----------- FILTER FOR VIEW -----------
selected_ids = {str(x) for x in (selected_groups or [])}
items_view = []
for r in st.session_state["items"]:
    i = normalize_item(r)
    if not selected_ids or i.get("group","") in selected_ids:
        items_view.append(i)

groups_view = []
for r in st.session_state["groups"]:
    g = normalize_group(r)
    if not selected_ids or g["id"] in selected_ids:
        groups_view.append(g)

# ----------- RENDER -----------
if not items_view:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Add your first event with the sidebar 👈</div>', unsafe_allow_html=True)
else:
    render_timeline(items_view, groups_view)  # includes Export PNG + Today button
