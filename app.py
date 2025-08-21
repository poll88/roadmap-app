import uuid
from datetime import date, datetime, timedelta
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

# Always render something so you see the app boot
st.write("🧭 Booting…")

# ---- Session defaults ----
if "items" not in st.session_state or "groups" not in st.session_state:
    reset_defaults(st.session_state)

# Normalize state defensively
st.session_state["items"], st.session_state["groups"] = normalize_state(
    st.session_state.get("items"), st.session_state.get("groups")
)

# Pastel palette (10 options)
PALETTE = [
    ("Lavender",  "#E9D5FF"),
    ("Baby Blue", "#BFDBFE"),
    ("Mint",      "#BBF7D0"),
    ("Lemon",     "#FEF9C3"),
    ("Peach",     "#FDE1D3"),
    ("Blush",     "#FBCFE8"),
    ("Sky",       "#E0F2FE"),
    ("Mauve",     "#F5D0FE"),
    ("Sage",      "#D1FAE5"),
    ("Sand",      "#F5E7C6"),
]
PALETTE_MAP = {f"{n} ({h})": h for n,h in PALETTE}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# ---- Sidebar ----
with st.sidebar:
    st.header("Add / Edit")

    # Category creation / selection (type to create)
    group_names = {g["content"]: g["id"] for g in st.session_state["groups"]}
    new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")
    if new_group_name and new_group_name not in group_names:
        g = normalize_group({"content": new_group_name, "order": len(st.session_state["groups"])})
        st.session_state["groups"].append(g)
        group_names[new_group_name] = g["id"]

    active_group = group_names.get(new_group_name) if new_group_name else ""

    # Reliable item picker (drives which item Edit/Delete will affect)
    labels = [f'{i.get("content") or "Untitled"} · {i.get("id","")[:6]}' for i in st.session_state["items"]]
    ids    = [i.get("id") for i in st.session_state["items"]]
    picked_label = st.selectbox("Pick existing", labels or ["(none)"])
    picked_id = ids[labels.index(picked_label)] if labels and picked_label in labels else ""

    def find_item(iid):
        for it in st.session_state["items"]:
            if str(it.get("id")) == str(iid):
                return it
        return None

    sel = find_item(picked_id) if picked_id else None

    # Form fields (prefill from selection if present)
    t_title = st.text_input("Title", sel.get("content","") if sel else "")
    t_sub   = st.text_input("Subtitle (optional)", sel.get("subtitle","") if sel else "")
    col1, col2 = st.columns(2)
    s_val = date.fromisoformat(sel["start"][:10]) if sel and sel.get("start") else date.today()
    e_val = date.fromisoformat(sel["end"][:10]) if sel and sel.get("end") else date.today()
    s_date = col1.date_input("Start", value=s_val)
    e_date = col2.date_input("End",   value=e_val)
    s_date, e_date = ensure_range(s_date, e_date)

    color_label_default = next((lab for lab,hexv in PALETTE_MAP.items() if hexv==(sel or {}).get("color")), PALETTE_OPTIONS[0])
    color_label = st.selectbox(
        "Bar color",
        PALETTE_OPTIONS,
        index=PALETTE_OPTIONS.index(color_label_default) if color_label_default in PALETTE_OPTIONS else 0
    )
    color_hex = PALETTE_MAP[color_label]

    c1, c2, c3 = st.columns(3)
    if c1.button("➕ Add item"):
        item = normalize_item({
            "content": t_title,
            "subtitle": t_sub,
            "start": s_date,
            "end": e_date,
            "group": active_group or (st.session_state["groups"][-1]["id"] if st.session_state["groups"] else ""),
            "color": color_hex,
            "style": f"background:{color_hex}; border-color:{color_hex}",
        })
        st.session_state["items"].append(item)
        st.success("Item added")

    if c2.button("✏️ Edit item"):
        if not picked_id:
            st.warning("Pick an existing item above.")
        else:
            for ix, it in enumerate(st.session_state["items"]):
                if str(it.get("id")) == str(picked_id):
                    updated = normalize_item({
                        "id": picked_id,
                        "content": t_title,
                        "subtitle": t_sub,
                        "start": s_date,
                        "end": e_date,
                        "group": active_group or it.get("group",""),
                        "color": color_hex,
                        "style": f"background:{color_hex}; border-color:{color_hex}",
                    })
                    st.session_state["items"][ix] = updated
                    st.success("Item updated")
                    break

    if c3.button("🗑 Delete item"):
        if not picked_id:
            st.warning("Pick an existing item above.")
        else:
            st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(picked_id)]
            st.success("Item deleted")

    st.divider()
    st.subheader("Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        reset_defaults(st.session_state)
        (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())

    exported = export_items_groups(st.session_state)
    st.download_button("⬇️ Export JSON", exported, file_name="roadmap.json", mime="application/json")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded:
        import json
        payload = json.loads(uploaded.read().decode("utf-8"))
        st.session_state["items"] = [normalize_item(x) for x in payload.get("items", [])]
        st.session_state["groups"] = [normalize_group(x) for x in payload.get("groups", [])]
        st.success("Imported.")
        (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())

# ---- Main area ----
st.title("Roadmap Timeline")
with st.expander("🐞 Debug", expanded=False):
    st.write({
        "items": len(st.session_state.get("items", [])),
        "groups": len(st.session_state.get("groups", [])),
    })

# Filters
selected_names = st.multiselect("Filter categories", [g["content"] for g in st.session_state["groups"]])
selected_ids = {g["id"] for g in st.session_state["groups"] if g["content"] in selected_names} if selected_names else set()

items_view  = [i for i in st.session_state["items"]  if not selected_ids or i.get("group","") in selected_ids]
groups_view = [g for g in st.session_state["groups"] if not selected_ids or g["id"] in selected_ids]

if not items_view:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>', unsafe_allow_html=True)
else:
    render_timeline(items_view, groups_view, selected_id="")