import logging
import streamlit as st
LOG = logging.getLogger("roadmap")

def render_debug_panel(state):
    with st.expander("🐞 Debug", expanded=False):
        snap = {
            "items": len(state.get("items", [])),
            "groups": len(state.get("groups", [])),
            "active_group_id": state.get("active_group_id", ""),
            "editing_item_id": state.get("editing_item_id", ""),
            "query_params": dict(st.query_params),
        }
        st.json(snap)
        if st.button("Log snapshot"):
            LOG.info("DEBUG_SNAPSHOT: %s", snap)
            st.toast("Snapshot logged", icon="🪵")