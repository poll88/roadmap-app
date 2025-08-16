from datetime import date, datetime
import uuid
import logging
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, ensure_range, export_items_groups
)
from lib.timeline import render_timeline

from core.ids import ensure_stable_ids, prefill_from_item_id, get_selected_item
from ui.sidebar import render_sidebar
from core.debug import dbg, render_debug_panel

# ----------------- Setup -----------------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# server logs
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("roadmap")

# ----------------- Session bootstrap -----------------
for k, v in {
    "items": [], "groups": [], "active_group_id": "", "editing_item_id": ""
}.items():
    st.session_state.setdefault(k, v)

# Process pending destructive actions BEFORE widgets render
if st.session_state.get("_pending_delete_id"):
    eid = st.session_state.pop("_pending_delete_id")
    st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
    st.session_state["editing_item_id"] = ""
    st.session_state.setdefault("form_title", "")
    st.session_state.setdefault("form_subtitle", "")
    st.session_state.setdefault("form_start", date.today())
    st.session_state.setdefault("form_end", date.today())
    st.session_state.setdefault("form_color_label", "Lavender (#E9D5FF)")
    LOG.info("Deleted item id=%s", eid)

if st.session_state.get("_pending_reset"):
    st.session_state.pop("_pending_reset")
    reset_defaults(st.session_state)
    st.session_state["editing_item_id"] = ""
    LOG.info("Reset all items/groups")

# Normalize & ensure stable ids
normalize_state(st.session_state)
if ensure_stable_ids(st.session_state):
    st.session_state["editing_item_id"] = ""
    LOG.info("Migrated unstable ids to stable UUIDs")

# --------- URL selection (?sel=<id>) from timeline click ---------
# Read early, prefill, then clear to avoid stickiness.
qp = dict(st.query_params)  # MappingProxy -> plain dict
sel_from_url = qp.get("sel")
if isinstance(sel_from_url, list):
    sel_from_url = sel_from_url[0] if sel_from_url else None

if sel_from_url:
    ok = prefill_from_item_id(st.session_state, sel_from_url)
    LOG.info("URL selection sel=%s -> prefill=%s", sel_from_url, ok)
    if "sel" in st.query_params:
        del st.query_params["sel"]
    if ok:
        st.rerun()

# ----------------- UI: Sidebar -----------------
actions = render_sidebar(
    st.session_state,
    normalize_item=normalize_item,
    ensure_range=ensure_range,
    export_items_groups=export_items_groups
)

# Handle actions (set flags + rerun)
if actions.get("add"):
    st.success("Item added.")
    st.rerun()
if actions.get("edit"):
    st.success("Item updated.")
    st.rerun()
if actions.get("delete"):
    st.session_state["_pending_delete_id"] = actions["delete"]
    st.rerun()
if actions.get("reset"):
    st.session_state["_pending_reset"] = True
    st.rerun()

# ----------------- Main area -----------------
st.title("Roadmap Timeline")

if not st.session_state["items"]:
    st.markdown(
        '<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>',
        unsafe_allow_html=True
    )
else:
    # Optional filters
    selected_names = st.multiselect(
        "Filter categories", [g["content"] for g in st.session_state["groups"]]
    )
    selected_ids = {g["id"] for g in st.session_state["groups"] if g["content"] in selected_names} if selected_names else set()

    items_view  = [i for i in st.session_state["items"]  if not selected_ids or i.get("group","") in selected_ids]
    groups_view = [g for g in st.session_state["groups"] if not selected_ids or g["id"] in selected_ids]

    # Render timeline (selection is passed via ?sel=<id> by the component)
    render_timeline(
        items_view,
        groups_view,
        selected_id=st.session_state.get("editing_item_id","")
    )

# ----------------- Debug panel -----------------
render_debug_panel(st.session_state)