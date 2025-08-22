# app.py — one-box category (type to reuse or create), reliable edit, with server logs

import uuid
import logging
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("roadmap")

# ----------------- Session bootstrap -----------------
st.session_state.setdefault("items", [])
st.session_state.setdefault("groups", [])
st.session_state.setdefault("active_group_id", "")
st.session_state.setdefault("editing_item_id", "")
st.session_state.setdefault("_last_picker_id", "")  # to detect selection changes

# Be tolerant to either normalize_state signature
try:
    res = normalize_state(st.session_state)
    if isinstance(res, tuple):
        st.session_state["items"], st.session_state["groups"] = res
except TypeError:
    res = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
    if isinstance(res, tuple):
        st.session_state["items"], st.session_state["groups"] = res

# ---------- Pastel palette ----------
PALETTE = [
    ("Lavender",  "#E9D5FF"), ("Baby Blue", "#BFDBFE"), ("Mint", "#BBF7D0"),
    ("Lemon", "#FEF9C3"), ("Peach", "#FDE1D3"), ("Blush", "#FBCFE8"),
    ("Sky", "#E0F2FE"), ("Mauve", "#F5D0FE"), ("Sage", "#D1FAE5"), ("Sand", "#F5E7C6"),
]
PALETTE_MAP = {f"{n} ({h})": h for n,h in PALETTE}
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
    # one-box category field
    st.session_state.setdefault("form_category","")

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    """Prefill form *only when selection changes*."""
    st.session_state["form_title"] = it.get("content","")
    st.session_state["form_subtitle"] = it.get("subtitle","")
    st.session_state["form_start"] = it.get("start") or date.today()
    st.session_state["form_end"]   = it.get("end") or date.today()
    # color -> label
    for label, hexv in PALETTE_MAP.items():
        if hexv == it.get("color"):
            st.session_state["form_color_label"] = label
            break
    # category (text box holds the category name)
    gid = it.get("group")
    st.session_state["form_category"] = groups_by_id.get(gid, "") if gid else ""
    if gid:
        st.session_state["active_group_id"] = gid

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group",""), "")
    title = it.get("content","(untitled)")
    start = str(it.get("start",""))[:10]
    short = str(it.get("id",""))[:6]
    return f"{title} · {gname} · {start} · {short}"

def _resolve_group_id_from_text(category_text: str) -> str:
    """
    Given a free-typed category name, return an existing group id (case-insensitive)
    or create a new group and return its id. Empty text -> '' (no group).
    """
    name = (category_text or "").strip()
    if not name:
        return ""
    # try case-insensitive match against existing names
    for g in st.session_state["groups"]:
        if g["content"].lower() == name.lower():
            return g["id"]
    # no match -> create
    g = normalize_group({"content": name, "order": len(st.session_state["groups"])})
    st.session_state["groups"].append(g)
    LOG.info("Created new category name=%r id=%s", name, g["id"])
    return g["id"]

def _suggest_categories(query: str, k=5):
    q = (query or "").strip().lower()
    if not q:
        return []
    hits = [g["content"] for g in st.session_state["groups"] if q in g["content"].lower()]
    return hits[:k]

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("📅 Add / Edit")

    groups_by_id = {g["id"]: g["content"] for g in st.session_state["groups"]}
    item_labels = [_label_for_item(it, groups_by_id)
                   for it in st.session_state["items"]
                   if it.get("type") != "background"]
    item_ids = [it["id"] for it in st.session_state["items"] if it.get("type") != "background"]

    PICK_NEW = "➕ New item"
    picker_options = [PICK_NEW] + item_labels

    # Default selection based on current editing_item_id (if present)
    if st.session_state.get("editing_item_id") and st.session_state["editing_item_id"] in item_ids:
        default_idx = item_ids.index(st.session_state["editing_item_id"]) + 1
    else:
        default_idx = 0

    pick = st.selectbox("Item", picker_options, index=default_idx, key="picker_label")

    # --- Selection change handling (no unintended prefill on rerun) ---
    if pick == PICK_NEW:
        if st.session_state.get("_last_picker_id"):
            LOG.info("Picker -> NEW (was %s)", st.session_state["_last_picker_id"])
            st.session_state["editing_item_id"] = ""
            st.session_state["_last_picker_id"] = ""
            _ensure_form_defaults()
    else:
        sel_idx = picker_options.index(pick) - 1
        sel_id = item_ids[sel_idx]
        if str(sel_id) != str(st.session_state.get("_last_picker_id","")):
            LOG.info("Picker selection changed: %s -> %s", st.session_state.get("_last_picker_id",""), sel_id)
            st.session_state["editing_item_id"] = str(sel_id)
            st.session_state["_last_picker_id"] = str(sel_id)
            _ensure_form_defaults()
            _prefill_form_from_item(_find_item(sel_id), groups_by_id)
        # else unchanged: keep user's typed edits

    # ---- form with single category box ----
    _ensure_form_defaults()
    with st.form("item_form", clear_on_submit=False):
        colA, colB = st.columns(2)
        start = colA.date_input("Start", key="form_start")
        end   = colB.date_input("End",   key="form_end")
        start, end = ensure_range(start, end)

        st.text_input("Title", key="form_title", placeholder="Item title")
        st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")

        st.text_input("Category", key="form_category", placeholder="Type to select or create")
        sugg = _suggest_categories(st.session_state.get("form_category",""), k=5)
        if sugg:
            st.caption("Suggestions: " + " · ".join(sugg))

        st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

        add_clicked    = st.form_submit_button("➕ Add item",    use_container_width=True)
        edit_clicked   = st.form_submit_button("✏️ Edit item",   use_container_width=True)
        delete_clicked = st.form_submit_button("🗑 Delete item", use_container_width=True)

    # ------ Actions with LOGS ------
    if add_clicked:
        col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = _resolve_group_id_from_text(st.session_state.get("form_category",""))
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
        LOG.info("ADD id=%s title=%r start=%s end=%s group=%s color=%s",
                 item["id"], item["content"], item["start"], item["end"], item.get("group",""), item.get("color",""))
        # after add -> picker back to NEW
        st.session_state["editing_item_id"] = ""
        st.session_state["_last_picker_id"] = ""
        st.success("Item added."); st.rerun()

    if edit_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to edit (top dropdown).")
        else:
            col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
            gid = _resolve_group_id_from_text(st.session_state.get("form_category",""))
            before = _find_item(eid)
            LOG.info("EDIT requested id=%s (before)=%s", eid, before)
            for i,it in enumerate(st.session_state["items"]):
                if str(it.get("id")) == str(eid):
                    updated = normalize_item({
                        "id": eid,
                        "content": st.session_state["form_title"],
                        "subtitle": st.session_state["form_subtitle"],
                        "start": st.session_state["form_start"],
                        "end":   st.session_state["form_end"],
                        "group": gid if gid != "" else it.get("group",""),
                        "color": col_hex,
                        "style": f"background:{col_hex}; border-color:{col_hex}",
                    })
                    st.session_state["items"][i] = updated
                    LOG.info("EDIT applied id=%s (after)=%s", eid, updated)
                    break
            st.success("Item updated."); st.rerun()

    if delete_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to delete (top dropdown).")
        else:
            LOG.info("DELETE id=%s", eid)
            st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
            st.session_state["editing_item_id"] = ""
            st.session_state["_last_picker_id"] = ""
            st.success("Item deleted."); st.rerun()

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        LOG.info("RESET")
        reset_defaults(st.session_state); st.rerun()

    exported = export_items_groups(st.session_state)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded:
        import json
        data = json.loads(uploaded.read().decode("utf-8"))
        st.session_state["items"]  = [normalize_item(x) for x in data.get("items", [])]
        st.session_state["groups"] = [normalize_group(x) for x in data.get("groups", [])]
        st.session_state["editing_item_id"] = ""
        st.session_state["_last_picker_id"] = ""
        LOG.info("IMPORT count items=%d groups=%d", len(st.session_state["items"]), len(st.session_state["groups"]))
        st.success("Imported."); st.rerun()

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