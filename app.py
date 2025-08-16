from datetime import date, datetime
import uuid
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, ensure_range, export_items_groups
)
from lib.timeline import render_timeline

st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

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

# ---------- HELPERS ----------
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

def clear_form_defaults():
    st.session_state["form_title"] = ""
    st.session_state["form_subtitle"] = ""
    st.session_state["form_start"] = date.today()
    st.session_state["form_end"] = date.today()
    st.session_state["form_color_label"] = PALETTE_OPTIONS[0]

def ensure_stable_ids():
    """Guarantee every item/group has a stable string id (migrates old data)."""
    changed = False
    for it in st.session_state.get("items", []):
        if not it.get("id"):
            it["id"] = str(uuid.uuid4())
            changed = True
        else:
            it["id"] = str(it["id"])
    for g in st.session_state.get("groups", []):
        if not g.get("id"):
            g["id"] = str(uuid.uuid4())
            changed = True
        else:
            g["id"] = str(g["id"])
    return changed

def prefill_from_item_id(item_id: str):
    """Prefill sidebar form + active category from the given item id."""
    for it in st.session_state.get("items", []):
        if str(it.get("id")) == str(item_id):
            st.session_state["editing_item_id"] = str(item_id)
            st.session_state["form_title"] = it.get("content", "")
            st.session_state["form_subtitle"] = it.get("subtitle", "")
            st.session_state["form_start"] = iso_to_date(it.get("start", ""))
            st.session_state["form_end"]   = iso_to_date(it.get("end", ""))
            gid = str(it.get("group", ""))
            if gid:
                st.session_state["active_group_id"] = gid
            st.session_state["form_color_label"] = HEX_TO_LABEL.get(
                it.get("color", ""), st.session_state.get("form_color_label", PALETTE_OPTIONS[0])
            )
            return True
    return False

def get_selected_item():
    eid = st.session_state.get("editing_item_id", "")
    for it in st.session_state.get("items", []):
        if str(it.get("id")) == str(eid):
            return it
    return None

# ---------- SESSION BOOTSTRAP ----------
if "items" not in st.session_state:
    st.session_state["items"] = []
if "groups" not in st.session_state:
    st.session_state["groups"] = []
if "active_group_id" not in st.session_state:
    st.session_state["active_group_id"] = (st.session_state["groups"][-1]["id"] if st.session_state["groups"] else "")
if "editing_item_id" not in st.session_state:
    st.session_state["editing_item_id"] = ""

# Handle pending destructive actions BEFORE widgets render
if st.session_state.get("_pending_delete_id"):
    eid = st.session_state.pop("_pending_delete_id")
    st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
    st.session_state["editing_item_id"] = ""
    clear_form_defaults()

if st.session_state.get("_pending_reset"):
    st.session_state.pop("_pending_reset")
    reset_defaults(st.session_state)
    st.session_state["editing_item_id"] = ""
    clear_form_defaults()

# Normalize and migrate IDs (so every item has a stable id)
normalize_state(st.session_state)
if ensure_stable_ids():
    st.session_state["editing_item_id"] = ""

# --------- URL selection (?sel=<id>) from timeline click (modern API) ---------
# Read early, prefill, then clear to avoid stickiness.
qp = dict(st.query_params)  # MappingProxy -> plain dict
sel_from_url = qp.get("sel")
if isinstance(sel_from_url, list):
    sel_from_url = sel_from_url[0] if sel_from_url else None

if sel_from_url:
    if prefill_from_item_id(sel_from_url):
        # clear 'sel' and rerun once
        if "sel" in st.query_params:
            del st.query_params["sel"]
        st.rerun()

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("📅 Add / Edit")

    # Category management (+ active category)
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

    # Show current selection for clarity
    sel = get_selected_item()
    if sel:
        st.caption(f"Selected: **{sel.get('content','(untitled)')}** · id `{str(sel.get('id'))[:8]}`")
    else:
        st.caption("Selected: *(none)*")

    # One form (prevents reruns on each keystroke)
    init_form_defaults()
    with st.form("item_form", clear_on_submit=False):
        colA, colB = st.columns(2)
        start = colA.date_input("Start", key="form_start")
        end   = colB.date_input("End",   key="form_end")
        start, end = ensure_range(start, end)

        content  = st.text_input("Title",               key="form_title",    placeholder="Item title")
        subtitle = st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")

        color_label = st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

        col1, col2, col3 = st.columns(3)
        add_clicked    = col1.form_submit_button("➕ Add item")
        edit_clicked   = col2.form_submit_button("✏️ Edit item")
        delete_clicked = col3.form_submit_button("🗑 Delete item")

    # -------- Actions (set flags, then rerun) --------
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

    if delete_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item on the timeline to delete.")
        else:
            st.session_state["_pending_delete_id"] = eid
            st.rerun()

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        st.session_state["_pending_reset"] = True
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

    # Render timeline; highlight currently selected id
    render_timeline(
        items_view,
        groups_view,
        selected_id=st.session_state.get("editing_item_id","")
    )