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
    return datetime.fromisoformat(s[:10]).date()

def init_form_defaults():
    st.session_state.setdefault("form_title", "")
    st.session_state.setdefault("form_subtitle", "")
    st.session_state.setdefault("form_start", date.today())
    st.session_state.setdefault("form_end", date.today())
    st.session_state.setdefault("form_color_label", PALETTE_OPTIONS[0])

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("📅 Add / Edit")

    # Category (group) management with "active" logic
    group_names = {g["content"]: g["id"] for g in st.session_state["groups"]}
    new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")

    if new_group_name and new_group_name in group_names:
        st.session_state["active_group_id"] = group_names[new_group_name]
    if new_group_name and new_group_name not in group_names:
        g = normalize_group({"content": new_group_name, "order": len(st.session_state["groups"])})
        st.session_state["groups"].append(g)
        group_names[new_group_name] = g["id"]
        st.session_state["active_group_id"] = g["id"]

    active_name = next((g["content"] for g in st.session_state["groups"]
                        if g["id"] == st.session_state.get("active_group_id","")), "(none)")
    st.caption(f"Active category: **{active_name or '(none)'}**")

    # One FORM to prevent reruns on every keystroke (keeps focus while typing)
    init_form_defaults()
    with st.form("item_form", clear_on_submit=False):
        colA, colB = st.columns(2)
        start = colA.date_input("Start", key="form_start")
        end   = colB.date_input("End",   key="form_end")

        # guard invalid/partial dates
        start, end = ensure_range(start, end)

        content  = st.text_input("Title",               key="form_title",    placeholder="Item title")
        subtitle = st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")

        color_label = st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

        col1, col2 = st.columns(2)
        add_clicked  = col1.form_submit_button("➕ Add item")
        edit_clicked = col2.form_submit_button("✏️ Edit item")

    # Actions after submit (so they run only on button click)
    if add_clicked:
        color_hex = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = st.session_state.get("active_group_id","")
        item = normalize_item({
            "content": st.session_state["form_title"],
            "subtitle": st.session_state["form_subtitle"],
            "start": st.session_state["form_start"],
            "end": st.session_state["form_end"],
            "group": gid,
            "color": color_hex,
            "style": f"background:{color_hex}; border-color:{color_hex}",
        })
        st.session_state["items"].append(item)
        st.session_state["editing_item_id"] = item["id"]
        st.success("Item added.")
        st.rerun()

    if edit_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item on the timeline to edit.")
        else:
            color_hex = PALETTE_MAP[st.session_state["form_color_label"]]
            for idx, it in enumerate(st.session_state["items"]):
                if str(it.get("id")) == str(eid):
                    updated = normalize_item({
                        "id": eid,
                        "content": st.session_state["form_title"],
                        "subtitle": st.session_state["form_subtitle"],
                        "start": st.session_state["form_start"],
                        "end": st.session_state["form_end"],
                        "group": st.session_state.get("active_group_id", it.get("group","")),
                        "color": color_hex,
                        "style": f"background:{color_hex}; border-color:{color_hex}",
                    })
                    st.session_state["items"][idx] = updated
                    st.success("Item updated.")
                    st.rerun()

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        reset_defaults(st.session_state)
        st.session_state["editing_item_id"] = ""
        st.rerun()

    exported = export_items_groups(st.session_state)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded:
        import json
        payload = json.loads(uploaded.read().decode("utf-8"))
        st.session_state["items"] = [normalize_item(x) for x in payload.get("items", [])]
        st.session_state["groups"] = [normalize_group(x) for x in payload.get("groups", [])]
        st.session_state["active_group_id"] = (st.session_state["groups"][-1]["id"] if st.session_state["groups"] else "")
        st.session_state["editing_item_id"] = ""
        st.success("Imported.")
        st.rerun()

# ---------- MAIN ----------
st.title("Roadmap Timeline")

if not st.session_state["items"]:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>', unsafe_allow_html=True)
else:
    # Optional filters
    selected_names = st.multiselect("Filter categories", [g["content"] for g in st.session_state["groups"]])
    selected_ids = {g["id"] for g in st.session_state["groups"] if g["content"] in selected_names} if selected_names else set()

    items_view  = [i for i in st.session_state["items"]  if not selected_ids or i.get("group","") in selected_ids]
    groups_view = [normalize_group(g) for g in st.session_state["groups"] if not selected_ids or g["id"] in selected_ids]

    # Render timeline (no 'key' param; use your updated lib/timeline.py)
    selection = render_timeline(
        items_view,
        groups_view,
        selected_id=st.session_state.get("editing_item_id","")
    )

    # Update sidebar when a timeline item is clicked — only rerun if selection changed
    if isinstance(selection, dict) and selection.get("type") == "select" and selection.get("item"):
        itm = selection["item"]
        if itm.get("type") != "background":
            sel_id = str(itm.get("id"))
            if sel_id != st.session_state.get("editing_item_id",""):
                st.session_state["editing_item_id"] = sel_id
                st.session_state["form_title"] = itm.get("content","")
                st.session_state["form_subtitle"] = itm.get("subtitle","")
                st.session_state["form_start"] = iso_to_date(itm.get("start",""))
                st.session_state["form_end"]   = iso_to_date(itm.get("end",""))
                # adopt item's group as active
                gid = str(itm.get("group",""))
                if gid:
                    st.session_state["active_group_id"] = gid
                # adopt color label if known
                st.session_state["form_color_label"] = HEX_TO_LABEL.get(itm.get("color",""), st.session_state["form_color_label"])
                st.rerun()
