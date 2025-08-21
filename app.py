# app.py — simple & reliable, with in-form Category dropdown and "New item" picker

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

# Be tolerant to either normalize_state signature
try:
    res = normalize_state(st.session_state)
    if isinstance(res, tuple):
        st.session_state["items"], st.session_state["groups"] = res
except TypeError:
    res = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
    if isinstance(res, tuple):
        st.session_state["items"], st.session_state["groups"] = res

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

def _ensure_form_defaults():
    st.session_state.setdefault("form_title","")
    st.session_state.setdefault("form_subtitle","")
    st.session_state.setdefault("form_start", date.today())
    st.session_state.setdefault("form_end",   date.today())
    st.session_state.setdefault("form_color_label", PALETTE_OPTIONS[0])
    st.session_state.setdefault("form_category_choice", "+ New…")
    st.session_state.setdefault("form_new_category_name","")

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    st.session_state["form_title"] = it.get("content","")
    st.session_state["form_subtitle"] = it.get("subtitle","")
    st.session_state["form_start"] = it.get("start") or date.today()
    st.session_state["form_end"]   = it.get("end") or date.today()
    # color -> label
    for label, hexv in PALETTE_MAP.items():
        if hexv == it.get("color"):
            st.session_state["form_color_label"] = label
            break
    # category -> dropdown default
    gid = it.get("group")
    if gid and gid in groups_by_id:
        st.session_state["form_category_choice"] = groups_by_id[gid]
        st.session_state["form_new_category_name"] = ""
        st.session_state["active_group_id"] = gid
    else:
        st.session_state["form_category_choice"] = "+ New…"
        st.session_state["form_new_category_name"] = ""

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group",""), "")
    title = it.get("content","(untitled)")
    start = str(it.get("start",""))[:10]
    short = str(it.get("id",""))[:6]
    return f"{title} · {gname} · {start} · {short}"

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("📅 Add / Edit")

    # --- Top picker: "New item" by default; no timeline-click selection ---
    groups_by_id = {g["id"]: g["content"] for g in st.session_state["groups"]}
    item_labels = [ _label_for_item(it, groups_by_id)
                    for it in st.session_state["items"]
                    if it.get("type") != "background" ]
    item_ids    = [ it["id"] for it in st.session_state["items"] if it.get("type") != "background" ]

    # Build options with "New item" at the top
    PICK_NEW = "➕ New item"
    picker_options = [PICK_NEW] + item_labels

    # Compute default index: if editing_item_id is set, point to that; else "New item"
    if st.session_state.get("editing_item_id"):
        try:
            idx = item_ids.index(st.session_state["editing_item_id"])
            default_picker_index = idx + 1  # shift by 1 due to "New item"
        except ValueError:
            default_picker_index = 0
    else:
        default_picker_index = 0

    pick = st.selectbox("Item", picker_options, index=default_picker_index, key="picker_label")

    # If user picked an existing item, sync selection and prefill form; if "New", clear it
    if pick == PICK_NEW:
        st.session_state["editing_item_id"] = ""
        _ensure_form_defaults()  # clears the form to defaults
    else:
        # map label -> id and prefill
        sel_idx = picker_options.index(pick) - 1  # back to item index
        sel_id  = item_ids[sel_idx]
        if str(sel_id) != str(st.session_state.get("editing_item_id","")):
            st.session_state["editing_item_id"] = str(sel_id)
        _ensure_form_defaults()
        _prefill_form_from_item(_find_item(sel_id), groups_by_id)

    # --- Form (includes Category dropdown) ---
    _ensure_form_defaults()
    # Build category options from existing groups
    existing_categories = [g["content"] for g in st.session_state["groups"]]
    category_options = ["+ New…"] + existing_categories
    # Compute default category index *before* rendering the widget
    if st.session_state["form_category_choice"] in category_options:
        cat_index = category_options.index(st.session_state["form_category_choice"])
    else:
        cat_index = 0

    with st.form("item_form", clear_on_submit=False):
        colA, colB = st.columns(2)
        start = colA.date_input("Start", key="form_start")
        end   = colB.date_input("End",   key="form_end")
        start, end = ensure_range(start, end)

        st.text_input("Title",               key="form_title",    placeholder="Item title")
        st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")

        # Category dropdown INSIDE the form
        choice = st.selectbox("Category", category_options, index=cat_index, key="form_category_choice")
        new_cat_name = ""
        if choice == "+ New…":
            new_cat_name = st.text_input("New category name", key="form_new_category_name")

        st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

        # Buttons stacked vertically
        add_clicked    = st.form_submit_button("➕ Add item",    use_container_width=True)
        edit_clicked   = st.form_submit_button("✏️ Edit item",   use_container_width=True)
        delete_clicked = st.form_submit_button("🗑 Delete item", use_container_width=True)

    # ------ Actions ------
    def _resolve_group_id_from_form():
        """Return a group id based on the category widgets; create group if needed."""
        # Existing category selected?
        if st.session_state["form_category_choice"] != "+ New…":
            name = st.session_state["form_category_choice"]
            # map name -> id
            for g in st.session_state["groups"]:
                if g["content"] == name:
                    return g["id"]
            # Shouldn't happen, but fallback to create it
            g = normalize_group({"content": name, "order": len(st.session_state["groups"])})
            st.session_state["groups"].append(g)
            return g["id"]
        # New category
        name = (st.session_state.get("form_new_category_name") or "").strip()
        if not name:
            return ""  # allow empty if user didn't type
        # Reuse if exists; else create
        for g in st.session_state["groups"]:
            if g["content"] == name:
                return g["id"]
        g = normalize_group({"content": name, "order": len(st.session_state["groups"])})
        st.session_state["groups"].append(g)
        return g["id"]

    if add_clicked:
        col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = _resolve_group_id_from_form()
        item = normalize_item({
            "id": str(uuid.uuid4()),
            "content": st.session_state["form_title"],
            "subtitle": st.session_state["form_subtitle"],
            "start": st.session_state["form_start"],
            "end":   st.session_state["form_end"],
            "group": gid,
            "color": col_hex,
            "style": f"background:{col_hex}; border-color:{col_hex}",
        })
        st.session_state["items"].append(item)

        # After adding, default picker back to "New item"
        st.session_state["editing_item_id"] = ""
        st.success("Item added.")
        st.rerun()

    if edit_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to edit (top dropdown).")
        else:
            col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
            gid = _resolve_group_id_from_form()
            for i,it in enumerate(st.session_state["items"]):
                if str(it.get("id")) == str(eid):
                    st.session_state["items"][i] = normalize_item({
                        "id": eid,
                        "content": st.session_state["form_title"],
                        "subtitle": st.session_state["form_subtitle"],
                        "start": st.session_state["form_start"],
                        "end":   st.session_state["form_end"],
                        "group": gid if gid != "" else it.get("group",""),
                        "color": col_hex,
                        "style": f"background:{col_hex}; border-color:{col_hex}",
                    })
                    break
            st.success("Item updated.")
            st.rerun()

    if delete_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to delete (top dropdown).")
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
    if uploaded:
        import json
        data = json.loads(uploaded.read().decode("utf-8"))
        st.session_state["items"]  = [normalize_item(x) for x in data.get("items", [])]
        st.session_state["groups"] = [normalize_group(x) for x in data.get("groups", [])]
        st.session_state["editing_item_id"] = ""
        st.success("Imported.")
        st.rerun()

# ----------------- MAIN -----------------
st.title("Roadmap Timeline")

if not st.session_state["items"]:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>', unsafe_allow_html=True)
else:
    names = st.multiselect("Filter categories", [g["content"] for g in st.session_state["groups"]])
    ids = {g["id"] for g in st.session_state["groups"] if g["content"] in names} if names else set()
    items_view  = [i for i in st.session_state["items"]  if not ids or i.get("group","") in ids]
    groups_view = [g for g in st.session_state["groups"] if not ids or g["id"] in ids]
    render_timeline(items_view, groups_view, selected_id=st.session_state.get("editing_item_id",""))