# app.py — dynamic axis + improved tab order + one-click PNG export

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

# ----------------- Setup -----------------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("roadmap")

# ----------------- Session bootstrap -----------------
st.session_state.setdefault("items", [])
st.session_state.setdefault("groups", [])
st.session_state.setdefault("active_group_id", "")
st.session_state.setdefault("editing_item_id", "")
st.session_state.setdefault("_last_picker_id", "")
st.session_state.setdefault("_export_exact", None)
st.session_state.setdefault("_last_import_hash", "")

# ----------------- Color palette -----------------
PALETTE_MAP = {
    "Blue":   "#3B82F6",
    "Green":  "#10B981",
    "Amber":  "#F59E0B",
    "Rose":   "#F43F5E",
    "Purple": "#8B5CF6",
    "Slate":  "#64748B",
}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# ----------------- Helpers -----------------
def normalize_defaults():
    st.session_state.setdefault("form_title", "")
    st.session_state.setdefault("form_subtitle", "")
    st.session_state.setdefault("form_start", date.today())
    st.session_state.setdefault("form_end", date.today())
    st.session_state.setdefault("form_color_label", PALETTE_OPTIONS[0])
    st.session_state.setdefault("form_category_choice", "(new…)")
    st.session_state.setdefault("form_category_new", "")

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    st.session_state["form_title"] = it.get("content", "")
    st.session_state["form_subtitle"] = it.get("subtitle", "")
    st.session_state["form_start"] = it.get("start") or date.today()
    st.session_state["form_end"] = it.get("end") or date.today()

    # color
    cur_color = it.get("color")
    for label, hexv in PALETTE_MAP.items():
        if hexv == cur_color:
            st.session_state["form_color_label"] = label
            break

    # category
    gid = it.get("group")
    gname = groups_by_id.get(gid, "")
    if gname:
        st.session_state["form_category_choice"] = gname
        st.session_state["form_category_new"] = ""
        st.session_state["active_group_id"] = gid
    else:
        st.session_state["form_category_choice"] = "(new…)"
        st.session_state["form_category_new"] = ""

def _resolve_group_id_from_choice(choice_text: str, new_name_text: str) -> str:
    if choice_text != "(new…)" and choice_text.strip():
        for g in st.session_state["groups"]:
            if (g.get("content") or "").strip().lower() == choice_text.strip().lower():
                return g.get("id", "")
    name = (new_name_text or "").strip()
    if not name:
        return ""
    for g in st.session_state["groups"]:
        if (g.get("content") or "").strip().lower() == name.lower():
            return g.get("id", "")
    gid = str(uuid.uuid4())
    st.session_state["groups"].append(normalize_group({
        "id": gid,
        "content": name,
        "order": len(st.session_state["groups"]),
    }))
    return gid

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group", ""), "")
    title = it.get("content", "(untitled)")
    start = str(it.get("start", ""))[:10]
    short = str(it.get("id", ""))[:6]
    return f"{title} · {gname} · {start} · {short}"

# ----------------- Page -----------------
st.title("🗺️ Product Roadmap")

# Sidebar: load / save
with st.sidebar:
    st.header("Data")
    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded is not None:
        data_bytes = uploaded.read()
        h = hashlib.sha256(data_bytes).hexdigest()
        if h != st.session_state.get("_last_import_hash", ""):
            st.session_state["_last_import_hash"] = h
            normalize_state(st.session_state, data_bytes.decode("utf-8"))
            st.success("Imported!"); st.rerun()

    exported = export_items_groups(st.session_state)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    st.divider()
    if st.button("Reset (clear all)", type="secondary"):
        LOG.info("RESET")
        reset_defaults(st.session_state); st.rerun()

# Build lookups
groups_by_id = {g.get("id"): g.get("content", "") for g in st.session_state["groups"]}
normalize_defaults()

# ---- Item picker ----
st.subheader("✏️ Edit / Add")
picker_items = [
    {"label": _label_for_item(it, groups_by_id), "value": str(it.get("id", ""))}
    for it in st.session_state["items"]
]
picker_labels = [p["label"] for p in picker_items]
picker_values = [p["value"] for p in picker_items]
selected_label = st.selectbox("Select item to edit", ["(none)"] + picker_labels)
selected_value = ""
if selected_label != "(none)":
    idx = picker_labels.index(selected_label)
    selected_value = picker_values[idx]
st.session_state["editing_item_id"] = selected_value

# Prefill
if selected_value:
    for it in st.session_state["items"]:
        if str(it.get("id")) == selected_value:
            _prefill_form_from_item(it, groups_by_id)
            break
else:
    if st.session_state["groups"]:
        first_name = st.session_state["groups"][0].get("content", "")
        if first_name:
            st.session_state["form_category_choice"] = first_name
    else:
        st.session_state["form_category_choice"] = "(new…)"

# ---- Form (tab order: Title → Subtitle → Category → Start → End → Color) ----
with st.form("item_form", clear_on_submit=False):
    # Row 1: Title | Subtitle
    r1c1, r1c2 = st.columns([2, 2])
    with r1c1:
        st.text_input("Title", key="form_title")
    with r1c2:
        st.text_input("Subtitle (optional)", key="form_subtitle")

    # Row 2: Category (and possibly new name) | Start
    r2c1, r2c2 = st.columns([2, 2])
    with r2c1:
        category_options = [g["content"] for g in st.session_state["groups"]] + ["(new…)"]
        if st.session_state["form_category_choice"] not in category_options:
            st.session_state["form_category_choice"] = category_options[0] if category_options else "(new…)"
        st.selectbox("Category", category_options, key="form_category_choice")
        if st.session_state["form_category_choice"] == "(new…)":
            st.text_input("New category name", key="form_category_new")
    with r2c2:
        st.date_input("Start", key="form_start")

    # Row 3: End | Color
    r3c1, r3c2 = st.columns([2, 2])
    with r3c1:
        st.date_input("End", key="form_end")
    with r3c2:
        st.selectbox("Color", PALETTE_OPTIONS, key="form_color_label")

    col_add, col_save, col_del = st.columns(3)
    with col_add:
        btn_add = st.form_submit_button("Add new")
    with col_save:
        btn_save = st.form_submit_button("Save changes")
    with col_del:
        btn_del = st.form_submit_button("Delete")

# ---- Form actions ----
if btn_add:
    title = (st.session_state["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = _resolve_group_id_from_choice(
            st.session_state.get("form_category_choice", "(new…)"),
            st.session_state.get("form_category_new", "")
        )
        item = normalize_item({
            "id": str(uuid.uuid4()),
            "content": title,
            "subtitle": st.session_state["form_subtitle"],
            "start": st.session_state["form_start"],
            "end": st.session_state["form_end"],
            "group": gid,
            "color": col_hex,
            "style": f"background:{col_hex}; border-color:{col_hex}",
        })
        st.session_state["items"].append(item)
        LOG.info("ADD id=%s title=%r", item["id"], item["content"])
        st.session_state["editing_item_id"] = ""
        st.session_state["_last_picker_id"] = ""
        st.success("Item added."); st.rerun()

if btn_save:
    eid = st.session_state.get("editing_item_id", "")
    if not eid:
        st.warning("Select an item to edit (top dropdown).")
    else:
        col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = _resolve_group_id_from_choice(
            st.session_state.get("form_category_choice", "(new…)"),
            st.session_state.get("form_category_new", "")
        )
        for i, it in enumerate(st.session_state["items"]):
            if str(it.get("id")) == str(eid):
                st.session_state["items"][i] = normalize_item({
                    "id": eid,
                    "content": st.session_state["form_title"],
                    "subtitle": st.session_state["form_subtitle"],
                    "start": st.session_state["form_start"],
                    "end":   st.session_state["form_end"],
                    "group": gid if gid != "" else it.get("group", ""),
                    "color": col_hex,
                    "style": f"background:{col_hex}; border-color:{col_hex}",
                })
                LOG.info("EDIT id=%s", eid)
                break
        st.success("Item updated."); st.rerun()

if btn_del:
    eid = st.session_state.get("editing_item_id", "")
    if not eid:
        st.warning("Select an item to delete (top dropdown).")
    else:
        st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
        st.session_state["editing_item_id"] = ""
        st.session_state["_last_picker_id"] = ""
        st.success("Item deleted."); st.rerun()

st.divider()

# ---- Export PNG: one-to-one of visible timeline ----
st.subheader("🎨 Export PNG")
if st.button("Download PNG", use_container_width=True):
    st.session_state["_export_exact"] = {"kind": "png", "mode": "visible"}
    st.toast("Exporting PNG…", icon="🖼️")

# ---- Filters & Timeline render ----
st.subheader("📂 View options")
names = st.multiselect(
    "Filter categories",
    [g["content"] for g in st.session_state["groups"]],
    key="filter_categories"
)
ids = {g["id"] for g in st.session_state["groups"] if g["content"] in names} if names else set()
items_view  = [i for i in st.session_state["items"]  if not ids or i.get("group", "") in ids]
groups_view = [g for g in st.session_state["groups"] if not ids or g["id"] in ids]

export_req = st.session_state.get("_export_exact")
render_timeline(
    items_view,
    groups_view,
    selected_id=st.session_state.get("editing_item_id", ""),
    export=export_req
)
if export_req is not None:
    st.session_state["_export_exact"] = None
