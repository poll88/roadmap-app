# app.py — robust Save (actually updates), stable selection, multi-item add,
# unified Category, resilient JSON import, PNG bg toggle

import uuid
import hashlib
import json
import logging
from datetime import date
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, export_items_groups
)
from lib.timeline import render_timeline

# ---------- Setup ----------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("roadmap")

# ---------- Session ----------
ss = st.session_state
ss.setdefault("items", [])
ss.setdefault("groups", [])
ss.setdefault("_last_import_hash", "")
ss.setdefault("_export_exact", None)
ss.setdefault("png_include_bg", True)
ss.setdefault("selected_item_id", "(none)")  # <-- bind selectbox to this (stable across reruns)

# ---------- Colors ----------
PALETTE_MAP = {
    "Blue":   "#3B82F6",
    "Green":  "#10B981",
    "Amber":  "#F59E0B",
    "Rose":   "#F43F5E",
    "Purple": "#8B5CF6",
    "Slate":  "#64748B",
}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# ---------- Helpers ----------
def _normalize_form_defaults():
    ss.setdefault("form_title", "")
    ss.setdefault("form_subtitle", "")
    ss.setdefault("form_category_name", "")
    ss.setdefault("form_start", date.today())
    ss.setdefault("form_end", date.today())
    ss.setdefault("form_color_label", PALETTE_OPTIONS[0])

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    ss["form_title"] = it.get("content", "")
    ss["form_subtitle"] = it.get("subtitle", "")
    ss["form_category_name"] = groups_by_id.get(it.get("group", ""), "")
    ss["form_start"] = it.get("start") or date.today()
    ss["form_end"]   = it.get("end")   or date.today()
    cur_color = it.get("color")
    for label, hexv in PALETTE_MAP.items():
        if hexv == cur_color:
            ss["form_color_label"] = label
            break

def _ensure_group_id_from_name(name_text: str) -> str:
    """Case-insensitive match; create new if not found; empty -> ungrouped."""
    name = (name_text or "").strip()
    if not name:
        return ""
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

def _build_item_dict(item_id: str) -> dict:
    col_hex = PALETTE_MAP[ss["form_color_label"]]
    gid = _ensure_group_id_from_name(ss.get("form_category_name", ""))
    return normalize_item({
        "id": item_id,
        "content": (ss["form_title"] or "").strip(),
        "subtitle": ss["form_subtitle"],
        "start": ss["form_start"],
        "end":   ss["form_end"],
        "group": gid,  # empty => Ungrouped lane (handled in renderer)
        "color": col_hex,
        "style": f"background:{col_hex}; border-color:{col_hex}",
    })

# ---------- Page ----------
st.title("🗺️ Product Roadmap")

# Sidebar: Import / Export / Reset
with st.sidebar:
    st.header("Data")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded is not None:
        text = uploaded.read().decode("utf-8", errors="replace")
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if h != ss.get("_last_import_hash", ""):
            ss["_last_import_hash"] = h
            # Try the project's normalizer first; if signature mismatch, fall back.
            try:
                normalize_state(ss, text)
                st.success("Imported!")
                ss["selected_item_id"] = "(none)"
                st.rerun()
            except Exception as e:
                try:
                    doc = json.loads(text)
                    items_in = doc.get("items") or doc.get("Items") or []
                    groups_in = doc.get("groups") or doc.get("Groups") or []
                    ss["groups"] = [normalize_group(g) for g in groups_in]
                    ss["items"]  = [normalize_item(i)  for i in items_in]
                    st.success("Imported!")
                    ss["selected_item_id"] = "(none)"
                    st.rerun()
                except Exception as e2:
                    st.error("Import failed. Expected JSON with 'items' and 'groups' arrays.")

    exported = export_items_groups(ss)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    st.divider()
    if st.button("Reset (clear all)"):
        keep_bg = ss.get("png_include_bg", True)
        reset_defaults(ss)
        ss["png_include_bg"] = keep_bg
        ss["selected_item_id"] = "(none)"
        st.rerun()

# Build lookups and defaults
groups_by_id = {g.get("id"): g.get("content", "") for g in ss["groups"]}
_normalize_form_defaults()

# ---- Picker bound to session (no label juggling) ----
item_by_id = {str(it.get("id")): it for it in ss["items"]}
options = ["(none)"] + list(item_by_id.keys())

# Ensure selected value is valid
if ss["selected_item_id"] not in options:
    ss["selected_item_id"] = "(none)"

selected_id = st.selectbox(
    "Select item to edit",
    options=options,
    key="selected_item_id",
    format_func=lambda v: "(none)" if v == "(none)" else _label_for_item(item_by_id[v], groups_by_id),
)

# Prefill form for selection
if selected_id != "(none)":
    _prefill_form_from_item(item_by_id[selected_id], groups_by_id)

# ---- Form (tab order: Title → Subtitle → Category → Start → End → Color) ----
with st.form("item_form", clear_on_submit=False):
    c1, c2 = st.columns([2, 2])
    with c1:
        st.text_input("Title", key="form_title")
    with c2:
        st.text_input("Subtitle (optional)", key="form_subtitle")

    c3, c4 = st.columns([2, 2])
    with c3:
        hint = ", ".join([g["content"] for g in ss["groups"]][:6])
        st.text_input("Category", key="form_category_name", help=("Existing: " + hint) if hint else None)
    with c4:
        st.date_input("Start", key="form_start")

    c5, c6 = st.columns([2, 2])
    with c5:
        st.date_input("End", key="form_end")
    with c6:
        st.selectbox("Color", PALETTE_OPTIONS, key="form_color_label")

    b1, b2, b3 = st.columns(3)
    with b1: btn_add  = st.form_submit_button("Add new",   type="primary",  use_container_width=True)
    with b2: btn_save = st.form_submit_button("Save changes",               use_container_width=True)
    with b3: btn_del  = st.form_submit_button("Delete",     type="secondary",use_container_width=True)

# ---- Actions ----
if btn_add:
    title = (ss["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        new_id = str(uuid.uuid4())
        ss["items"].append(_build_item_dict(new_id))
        ss["selected_item_id"] = new_id   # auto-select the newly added item
        st.success("Item added.")
        st.rerun()

if btn_save:
    title = (ss["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        if ss["selected_item_id"] == "(none)":
            # No selection? Treat Save as "create"
            new_id = str(uuid.uuid4())
            ss["items"].append(_build_item_dict(new_id))
            ss["selected_item_id"] = new_id
            st.success("Item saved (new).")
            st.rerun()
        else:
            # Update the selected item in-place
            target = ss["selected_item_id"]
            found = False
            for i, it in enumerate(ss["items"]):
                if str(it.get("id")) == target:
                    ss["items"][i] = _build_item_dict(target)
                    found = True
                    break
            if found:
                st.success("Item updated.")
                st.rerun()
            else:
                # Fallback: create if somehow missing
                ss["items"].append(_build_item_dict(target))
                st.info("Selected item not found; created it.")
                st.rerun()

if btn_del:
    if ss["selected_item_id"] == "(none)":
        st.warning("Select an item to delete (top dropdown).")
    else:
        tgt = ss["selected_item_id"]
        ss["items"] = [it for it in ss["items"] if str(it.get("id")) != tgt]
        ss["selected_item_id"] = "(none)"
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
render_timeline(items_view, groups_view, selected_id=ss.get("selected_item_id", ""), export=export_req)
if export_req is not None:
    ss["_export_exact"] = None
