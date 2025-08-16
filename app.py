from datetime import date
import logging
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import normalize_state, reset_defaults, ensure_range, export_items_groups
from lib.timeline import render_timeline
from lib.sidebar import render_sidebar
from lib.ids import ensure_stable_ids, prefill_from_item_id
from lib.debug import render_debug_panel

# ----------------- Setup -----------------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("roadmap")

# ----------------- Session bootstrap -----------------
for k, v in {"items": [], "groups": [], "active_group_id": "", "editing_item_id": ""}.items():
    st.session_state.setdefault(k, v)

# Handle delete/reset flags BEFORE widgets render (no widget state errors)
if st.session_state.get("_pending_delete_id"):
    eid = st.session_state.pop("_pending_delete_id")
    st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
    st.session_state["editing_item_id"] = ""
    LOG.info("Deleted item %s", eid)

if st.session_state.get("_pending_reset"):
    st.session_state.pop("_pending_reset")
    reset_defaults(st.session_state)
    st.session_state["editing_item_id"] = ""
    LOG.info("Reset all")

# Normalize & ensure stable ids
normalize_state(st.session_state)
if ensure_stable_ids(st.session_state):
    st.session_state["editing_item_id"] = ""

# --------- Selection via URL (?sel=<id>) — NO RERUN HERE ---------
# We process it once and clear it; render continues normally.
sel_from_url = st.query_params.get("sel")
if isinstance(sel_from_url, list):
    sel_from_url = sel_from_url[0] if sel_from_url else None

last_processed = st.session_state.get("_last_sel_processed")
if sel_from_url and sel_from_url != last_processed:
    ok = prefill_from_item_id(st.session_state, sel_from_url)
    st.session_state["_last_sel_processed"] = sel_from_url  # prevent re-processing
    # Clear param without forcing a rerun; next navigation will use fresh state.
    if "sel" in st.query_params:
        del st.query_params["sel"]
    LOG.info("URL selection sel=%s -> prefill=%s", sel_from_url, ok)

# ----------------- Sidebar -----------------
actions = render_sidebar(st.session_state, ensure_range, export_items_groups)

# Act on sidebar results (rerun only for user actions)
if actions.get("add"):
    st.rerun()
if actions.get("edit"):
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
    st.info("No items yet. Use the sidebar to add your first event 👈")
else:
    selected_names = st.multiselect(
        "Filter categories",
        [g["content"] for g in st.session_state["groups"]],
    )
    selected_ids = {g["id"] for g in st.session_state["groups"] if g["content"] in selected_names} if selected_names else set()

    items_view  = [i for i in st.session_state["items"]  if not selected_ids or i.get("group") in selected_ids]
    groups_view = [g for g in st.session_state["groups"] if not selected_ids or g["id"] in selected_ids]

    # Renders the timeline. The component sets ?sel=<id> (target="_top") on tap/click.
    render_timeline(items_view, groups_view, st.session_state.get("editing_item_id",""))

# ----------------- Debug -----------------
render_debug_panel(st.session_state)