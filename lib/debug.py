import logging
import streamlit as st

LOG = logging.getLogger("roadmap")

def dbg(msg: str, **kv):
    LOG.info("%s | %s", msg, {k: v for k, v in kv.items()})

def _compact_state_snapshot(state):
    return {
        "items": len(state.get("items", [])),
        "groups": len(state.get("groups", [])),
        "active_group_id": state.get("active_group_id", ""),
        "editing_item_id": state.get("editing_item_id", ""),
        "query_params": dict(st.query_params),
    }

def render_debug_panel(state):
    with st.expander("🐞 Debug", expanded=False):
        snap = _compact_state_snapshot(state)
        st.json(snap)
        if st.button("Write debug snapshot to server log"):
            LOG.info("DEBUG_SNAPSHOT: %s", snap)
            st.toast("Snapshot logged", icon="🪵")