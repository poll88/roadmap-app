from datetime import date, datetime
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, ensure_range, export_items_groups
)
from lib.timeline import render_timeline

st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ---------- SESSION ----------
if "items" not in st.session_state:
    st.session_state["items"] = []
if "groups" not in st.session_state:
    st.session_state["groups"] = []
normalize_state(st.session_state)

# Track selection and active category
if "active_group_id" not in st.session_state:
    st.session_state["active_group_id"] = (st.session_state["groups"][-1]["id"] if st.session_state["groups"] else "")
if "editing_item_id" not in st.session_state:
    st.session_state["editing_item_id"] = ""

# ---------- COLOR PALETTE ----------
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
HEX_TO_LABEL = {hexcode: label for label, hexcode in PALETTE_MAP.items()}

# ---------- Helpers ----------
def iso_to_date(s: str) -> date:
    if not s:
        return date.today()
    # Accept "YYYY-MM-DD" and "YYYY-MM-DDTHH:MM:SS"
    return datetime.fromisoformat(s[:10]).date()

def _init_form_defaults():
    if "form_title" not in st.session_state:
        st.session_state["form_title"] = ""
    if "form_subtitle" not in st.session_state:
        st.session_state["form_subtitle"] = ""
    if "form_start" not in st.session_state:
        st.session_state["form_start"] = date.today()
    if "form_end" not in st.session_state:
        st.session_state["form_end"] = date.today()
    if "form_color_label" not in st.session_state:
        st.session_state["form_color_label"] = PALETTE_OPTIONS[0]

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("📅 Add / Edit")

    # Create / activate categories (groups)
    group_names = {g["content"]: g["id"] for g in st.session_state["groups"]}
    new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")

    # If existing name is typed, switch active
    if new_group_name and new_group_name in group_names:
        st.session_state["active_group_id"] = group_names[new_group_name]

    # If new name, create and make active
    if new_group_name and new_group_name not in group_names:
        g = normalize_group({"content": new_group_name, "order": len(st.session_state["groups"])})
        st.session_state["groups"].append(g)
        group_names[new_group_name] = g["id"]
        st.session_state["active_group_id"] = g["id"]

    active_name = next((g["content"] for g in st.session_state["groups"]
                        if g["id"] == st.session_state.get("active_group_id", "")), "(none)")
    st.caption(f"Active category: **{active_name or '(none)'}**")

    # Form state (prefilled when selecting on timeline)
    _init_form_defaults()

    colA, colB = st.columns(2)
    start = colA.date_input("Start", value=st.session_state.get("form_start") or date.today(), key="form_start")
    end   = colB.date_input("End",   value=st.session_state.get("form_end")   or date.today(), key="form_end")
    start, end = ensure_range(start, end)

    content  = st.text_input("Title",               value=st.session_state["form_title"],    key="form_title",    placeholder="Item title")
    subtitle = st.text_input("Subtitle (optional)", value=st.session_state["form_subtitle"], key="form_subtitle", placeholder="Short note")

    color_label = st.selectbox(
        "Bar color",
        PALETTE_OPTIONS,
        index=PALETTE_OPTIONS.index(st.session_state["form_color_label"]) if st.session_state["form_color_label"] in PALETTE_OPTIONS else 0,
        key="form_color_label"
    )
    color_hex = PALETTE_MAP[color_label]

    # Add / Edit buttons
    with st.form("add_edit_item_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        add_clicked  = col1.form_submit_button("➕ Add item")
        edit_clicked = col2.form_submit_button("✏️ Edit item")

        if add_clicked:
            gid = st.session_state.get("active_group_id", "")
            item = normalize_item({
                "content": content,
                "subtitle": subtitle,
                "start": start,
                "end": end,
                "group": gid,
                "color": color_hex,
                "style": f"background:{color_hex}; border-color:{color_hex}",
            })
            st.session_state["items"].append(item)
            st.session_state["editing_item_id"] = item["id"]
            st.success("Item added.")
            st.rerun()

        if edit_clicked:
            eid = st.session_state.get("editing_item_id", "")
            if not eid:
                st.warning("Select an item on the timeline to edit.")
            else:
                for idx, it in enumerate(st.session_state["items"]):
                    if str(it.get("id")) == str(eid):
                        updated = normalize_item({
                            "id": eid,  # preserve ID
                            "content": content,
                            "subtitle": subtitle,
                            "start": start,
                            "end": end,
                            "group": st.session_state.get("active_group_id", it.get("group", "")),
                            "color": color_hex,
                            "style": f"background:{color_hex}; border-color:{color_hex}",
                        })
                        st.session_state["items"][idx] = updated
                        st.success("Item updated.")
                        st.rerun()

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        reset_defaults
