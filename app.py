# app.py — simple & reliable orchestrator

import uuid
from datetime import date
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, ensure_range, export_items_groups
)
from lib.timeline import render_timeline

# ----------------- Setup -----------------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ----------------- Session bootstrap -----------------
st.session_state.setdefault("items", [])
st.session_state.setdefault("groups", [])
st.session_state.setdefault("active_group_id", "")
st.session_state.setdefault("editing_item_id", "")

# Normalize existing state (safe even if empty)
# Some versions of normalize_state mutate in place; handle both patterns:
ns = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
if isinstance(ns, tuple):
    st.session_state["items"], st.session_state["groups"] = ns
else:
    # old behavior: normalize_state(st.session_state)
    pass

# ---------- Pastel palette (10 fixed) ----------
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
PALETTE_MAP = {f"{name} ({hexcode})": hexcode for name, hexcode in PALETTE}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# ---------- Helpers ----------
def _find_item(iid: str):
    for it in st.session_state["items"]:
        if str(it.get("id")) == str(iid):
            return it
    return None

def _prefill_form_from_item(item: dict):
    """Set form fields in session_state BEFORE rendering the form widgets."""
    st.session_state["form_title"] = item.get("content", "")
    st.session_state["form_subtitle"] = item.get("subtitle", "")
    # `normalize_item` keeps dates as date objects
    st.session_state["form_start"] = item.get("start") or date.today()
    st.session_state["form_end"]   = item.get("end") or date.today()
    # sync category
    gid = item.get("group", "")
    if gid:
        st.session_state["active_group_id"] = gid
    # pick matching color label if available
    chosen = next((lab for lab, hexv in PALETTE_MAP.items() if hexv == item.get("color")), None)
    st.session_state["form_color_label"] = chosen or PALETTE_OPTIONS[0]

def _ensure_form_defaults():
    st.session_state.setdefault("form_title", "")
    st.session_state.setdefault("form_subtitle", "")
    st.session_state.setdefault("form_start", date.today())
    st.session_state.setdefault("form_end", date.today())
    st.session_state.setdefault("form_color_label", PALETTE_OPTIONS[0])

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group",""), "")
    title = it.get("content","(untitled)")
    start = str(it.get("start",""))[:10]
    short = str(it.get("id",""))[:6]
    return f"{title} · {gname} · {start} · {short}"

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("📅 Add / Edit")

    # Category field (type to pick-or-create)
    group_names = {g["content"]: g["id"] for g in st.session_state["groups"]}
    new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")

    # If user typed a name, make it active; create when missing
    if new_group_name:
        if new_group_name in group_names:
            st.session_state["active_group_id"] = group_names[new_group_name]
        else:
            g = normalize_group({"content": new_group_name, "order": len(st.session_state["groups"])})
            st.session_state["groups"].append(g)
            st.session_state["active_group_id"] = g["id"]

    active_name = next((g["content"] for g in st.session_state["groups"]
                        if g["id"] == st.session_state.get("active_group_id","")), "")
    st.caption(f"Active category: **{active_name or '(none)'}**")

    # Reliable item picker (drives which item is edited/deleted)
    groups_by_id = {g["id"]: g["content"] for g in st.session_state["groups"]}
    options = [(it["id"], _label_for_item(it, groups_by_id))
               for it in st.session_state["items"]
               if it.get("type") != "background"]
    labels = [lbl for _, lbl in options]

    # Compute index from current editing_item_id (default to first if exists)
    selected_idx = 0
    if st.session_state.get("editing_item_id"):
        for i,(iid,_) in enumerate(options):
            if str(iid) == str(st.session_state["editing_item_id"]):
                selected_idx = i
                break

    picked_label = st.selectbox("Select existing", labels or ["(none)"],
                                index=selected_idx if labels else 0,
                                key="picker_label")

    # Map label -> id (only if we have items)
    picked_id = ""
    if labels:
        for iid, lbl in options:
            if lbl == picked_label:
                picked_id = iid
                break

    # If user changed selection, prefill form and remember the id
    if picked_id and str(picked_id) != str(st.session_state.get("editing_item_id","")):
        st.session_state["editing_item_id"] = str(picked_id)
        _prefill_form_from_item(_find_item(picked_id))

    # Ensure defaults exist BEFORE drawing the form
    _ensure_form_defaults()

    # Single form (prevents keystroke reruns/focus loss)
    with st.form("item_form", clear_on_submit=False):
        colA, colB = st.columns(2)
        start = colA.date_input("Start", key="form_start")
        end   = colB.date_input("End",   key="form_end")
        start, end = ensure_range(start, end)

        st.text_input("Title",               key="form_title",    placeholder="Item title")
        st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")

        st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

        c1, c2, c3 = st.columns(3)
        add_clicked    = c1.form_submit_button("➕ Add item")
        edit_clicked   = c2.form_submit_button("✏️ Edit item")
        delete_clicked = c3.form_submit_button("🗑 Delete item")

    # ------ Actions ------
    if add_clicked:
        color_hex = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = st.session_state.get("active_group_id","")
        # If no active group but we have existing groups, default to the last one
        if not gid and st.session_state["groups"]:
            gid = st.session_state["groups"][-1]["id"]

        item = normalize_item({
            "id": str(uuid.uuid4()),  # stable ID
            "content": st.session_state["form_title"],
            "subtitle": st.session_state["form_subtitle"],
            "start": st.session_state["form_start"],
            "end": st.session_state["form_end"],
            "group": gid,
            "color": color_hex,
            "style": f"background:{color_hex}; border-color:{color_hex}",
        })
        st.session_state["items"].append(item)
        st.session_state["editing_item_id"] = item["id"]
        st.success("Item added.")
        st.rerun()

    if edit_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to edit (picker above).")
        else:
            color_hex = PALETTE_MAP[st.session_state["form_color_label"]]
            for idx, it in enumerate(st.session_state["items"]):
                if str(it.get("id")) == str(eid):
                    updated = normalize_item({
                        "id": eid,  # keep same id
                        "content": st.session_state["form_title"],
                        "subtitle": st.session_state["form_subtitle"],
                        "start": st.session_state["form_start"],
                        "end": st.session_state["form_end"],
                        "group": st.session_state.get("active_group_id", it.get("group","")),
                        "color": color_hex,
                        "style": f"background:{color_hex}; border-color:{color_hex}",
                    })
                    st.session_state["items"][idx] = updated
                    break
            st.success("Item updated.")
            st.rerun()

    if delete_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to delete (picker above).")
        else:
            st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
            st.session_state["editing_item_id"] = ""
            st.success("Item deleted.")
            st.rerun()

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        reset_defaults(st.session_state)
        st.rerun()

    exported = export_items_groups(st.session_state)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded is not None:
        import json
        payload = json.loads(uploaded.read().decode("utf-8"))
        st.session_state["items"] = [normalize_item(x) for x in payload.get("items", [])]
        st.session_state["groups"] = [normalize_group(x) for x in payload.get("groups", [])]
        st.session_state["editing_item_id"] = ""
        st.success("Imported.")
        st.rerun()

# ----------------- MAIN -----------------
st.title("Roadmap Timeline")

if not st.session_state["items"]:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>', unsafe_allow_html=True)
else:
    selected_names = st.multiselect("Filter categories", [g["content"] for g in st.session_state["groups"]])
    selected_ids = {g["id"] for g in st.session_state["groups"] if g["content"] in selected_names} if selected_names else set()

    items_view  = [i for i in st.session_state["items"]  if not selected_ids or i.get("group","") in selected_ids]
    groups_view = [g for g in st.session_state["groups"] if not selected_ids or g["id"] in selected_ids]

    render_timeline(items_view, groups_view, selected_id=st.session_state.get("editing_item_id",""))