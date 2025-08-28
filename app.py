# app.py — unified Category input, working Save, add multiple items,
# PNG export option (include background), correct form submit buttons

import uuid
import hashlib
import logging
from datetime import date
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, export_items_groups
)
from lib.timeline import render_timeline

# ------ Setup ------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("roadmap")

# ------ Session bootstrap ------
ss = st.session_state
ss.setdefault("items", [])
ss.setdefault("groups", [])
ss.setdefault("editing_item_id", "")
ss.setdefault("_last_import_hash", "")
ss.setdefault("_export_exact", None)
ss.setdefault("png_include_bg", True)  # export option

# ------ Colors ------
PALETTE_MAP = {
    "Blue":   "#3B82F6",
    "Green":  "#10B981",
    "Amber":  "#F59E0B",
    "Rose":   "#F43F5E",
    "Purple": "#8B5CF6",
    "Slate":  "#64748B",
}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# ------ Helpers ------
def _normalize_form_defaults():
    ss.setdefault("form_title", "")
    ss.setdefault("form_subtitle", "")
    ss.setdefault("form_category_name", "")  # unified category input
    ss.setdefault("form_start", date.today())
    ss.setdefault("form_end", date.today())
    ss.setdefault("form_color_label", PALETTE_OPTIONS[0])

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    ss["form_title"] = it.get("content", "")
    ss["form_subtitle"] = it.get("subtitle", "")
    ss["form_category_name"] = groups_by_id.get(it.get("group", ""), "")
    ss["form_start"] = it.get("start") or date.today()
    ss["form_end"] = it.get("end") or date.today()
    # color label from hex
    cur_color = it.get("color")
    for label, hexv in PALETTE_MAP.items():
        if hexv == cur_color:
            ss["form_color_label"] = label
            break

def _ensure_group_id_from_name(name_text: str) -> str:
    """If name exists (case-insensitive), return its id; else create it."""
    name = (name_text or "").strip()
    if not name:
        return ""  # allowed — items will show in the Ungrouped lane
    for g in ss["groups"]:
        if (g.get("content") or "").strip().lower() == name.lower():
            return g.get("id", "")
    gid = str(uuid.uuid4())
    ss["groups"].append(normalize_group({"id": gid, "content": name, "order": len(ss["groups"])}))
    return gid

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group", ""), "")
    title = it.get("content", "(untitled)")
    start = str(it.get("start", ""))[:10]
    short = str(it.get("id", ""))[:6]
    return f"{title} · {gname} · {start} · {short}"

# ------ Page ------
st.title("🗺️ Product Roadmap")

# Sidebar: load / save / reset
with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded is not None:
        data_bytes = uploaded.read()
        h = hashlib.sha256(data_bytes).hexdigest()
        if h != ss.get("_last_import_hash", ""):
            ss["_last_import_hash"] = h
            normalize_state(ss, data_bytes.decode("utf-8"))
            st.success("Imported!")
            st.rerun()

    exported = export_items_groups(ss)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    st.divider()
    if st.button("Reset (clear all)", type="secondary"):
        keep_bg = ss.get("png_include_bg", True)
        reset_defaults(ss)
        ss["png_include_bg"] = keep_bg  # keep the user's PNG setting
        st.rerun()

# Lookups & defaults
groups_by_id = {g.get("id"): g.get("content", "") for g in ss["groups"]}
_normalize_form_defaults = _normalize_form_defaults
_normalize_form_defaults()

# ---- Pick item to edit (stable selection) ----
picker_labels = [_label_for_item(it, groups_by_id) for it in ss["items"]]
picker_ids    = [str(it.get("id", "")) for it in ss["items"]]
id_by_label   = {lbl: iid for lbl, iid in zip(picker_labels, picker_ids)}

if "picker_index" not in ss:
    ss["picker_index"] = 0
if ss.get("editing_item_id"):
    try:
        ss["picker_index"] = 1 + picker_ids.index(ss["editing_item_id"])
    except ValueError:
        ss["picker_index"] = 0

selected_label = st.selectbox(
    "Select item to edit",
    options=["(none)"] + picker_labels,
    index=min(ss["picker_index"], len(picker_labels))
)
eid = id_by_label.get(selected_label, "")
ss["editing_item_id"] = eid
ss["picker_index"] = (["(none)"] + picker_labels).index(selected_label)

# Prefill form when selecting an item
if eid:
    for it in ss["items"]:
        if str(it.get("id")) == str(eid):
            _prefill_form_from_item(it, groups_by_id)
            break

# ---- Form (tab order: Title → Subtitle → Category → Start → End → Color) ----
with st.form("item_form", clear_on_submit=False):
    r1c1, r1c2 = st.columns([2, 2])
    with r1c1:
        st.text_input("Title", key="form_title")
    with r1c2:
        st.text_input("Subtitle (optional)", key="form_subtitle")

    r2c1, r2c2 = st.columns([2, 2])
    with r2c1:
        hint = ", ".join([g["content"] for g in ss["groups"]][:6])
        st.text_input("Category", key="form_category_name", help=("Existing: " + hint) if hint else None)
    with r2c2:
        st.date_input("Start", key="form_start")

    r3c1, r3c2 = st.columns([2, 2])
    with r3c1:
        st.date_input("End", key="form_end")
    with r3c2:
        st.selectbox("Color", PALETTE_OPTIONS, key="form_color_label")

    c1, c2, c3 = st.columns(3)
    # NOTE: st.form_submit_button does NOT support key= -> removed
    with c1: btn_add  = st.form_submit_button("Add new",   type="primary",  use_container_width=True)
    with c2: btn_save = st.form_submit_button("Save changes",               use_container_width=True)
    with c3: btn_del  = st.form_submit_button("Delete",     type="secondary",use_container_width=True)

# ---- Actions ----
if btn_add:
    title = (ss["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        col_hex = PALETTE_MAP[ss["form_color_label"]]
        gid = _ensure_group_id_from_name(ss.get("form_category_name", ""))
        item = normalize_item({
            "id": str(uuid.uuid4()),
            "content": title,
            "subtitle": ss["form_subtitle"],
            "start": ss["form_start"],
            "end":   ss["form_end"],
            "group": gid,
            "color": col_hex,
            "style": f"background:{col_hex}; border-color:{col_hex}",
        })
        ss["items"].append(item)
        LOG.info("ADD %s", item["id"])
        ss["editing_item_id"] = ""   # stay in add mode
        st.success("Item added.")
        st.rerun()

if btn_save:
    if not ss.get("editing_item_id"):
        st.warning("Select an item to edit (top dropdown).")
    else:
        col_hex = PALETTE_MAP[ss["form_color_label"]]
        gid = _ensure_group_id_from_name(ss.get("form_category_name", ""))
        updated = False
        for i, it in enumerate(ss["items"]):
            if str(it.get("id")) == str(ss["editing_item_id"]):
                ss["items"][i] = normalize_item({
                    "id": ss["editing_item_id"],
                    "content": ss["form_title"],
                    "subtitle": ss["form_subtitle"],
                    "start": ss["form_start"],
                    "end":   ss["form_end"],
                    "group": gid if gid != "" else it.get("group", ""),
                    "color": col_hex,
                    "style": f"background:{col_hex}; border-color:{col_hex}",
                })
                updated = True
                break
        if updated:
            st.success("Item updated.")
            st.rerun()
        else:
            st.error("Could not find the selected item to update.")

if btn_del:
    if not ss.get("editing_item_id"):
        st.warning("Select an item to delete (top dropdown).")
    else:
        ss["items"] = [it for it in ss["items"] if str(it.get("id")) != str(ss["editing_item_id"])]
        ss["editing_item_id"] = ""
        st.success("Item deleted.")
        st.rerun()

st.divider()

# ---- PNG export options ----
st.subheader("🎨 Export PNG")
st.checkbox("Include background color in PNG", key="png_include_bg")
if st.button("Download PNG", use_container_width=True):
    ss["_export_exact"] = {
        "kind": "png",
        "mode": "visible",
        "includeBg": bool(ss.get("png_include_bg", True)),
    }
    st.toast("Exporting PNG…", icon="🖼️")

# ---- Filters & Timeline ----
st.subheader("📂 View options")
names = st.multiselect("Filter categories", [g["content"] for g in ss["groups"]], key="filter_categories")
ids = {g["id"] for g in ss["groups"] if g["content"] in names} if names else set()
items_view  = [i for i in ss["items"]  if not ids or i.get("group", "") in ids]
groups_view = [g for g in ss["groups"] if not ids or g["id"] in ids]

export_req = ss.get("_export_exact")
render_timeline(items_view, groups_view, selected_id=ss.get("editing_item_id", ""), export=export_req)
if export_req is not None:
    ss["_export_exact"] = None
