# app.py — simple & reliable orchestrator (with normalize_state signature guard)

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

# Normalize existing state (works with both normalize_state signatures)
try:
    # Preferred: function that takes the whole session_state dict
    res = normalize_state(st.session_state)
    if isinstance(res, tuple):
        st.session_state["items"], st.session_state["groups"] = res
except TypeError:
    # Fallback: function that takes (items, groups) and returns a tuple
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

def _prefill_from_item(it: dict):
    st.session_state["form_title"] = it.get("content","")
    st.session_state["form_subtitle"] = it.get("subtitle","")
    st.session_state["form_start"] = it.get("start") or date.today()
    st.session_state["form_end"]   = it.get("end") or date.today()
    if it.get("group"):
        st.session_state["active_group_id"] = it["group"]
    for label, hexv in PALETTE_MAP.items():
        if hexv == it.get("color"):
            st.session_state["form_color_label"] = label
            break

def _ensure_form_defaults():
    st.session_state.setdefault("form_title","")
    st.session_state.setdefault("form_subtitle","")
    st.session_state.setdefault("form_start", date.today())
    st.session_state.setdefault("form_end",   date.today())
    st.session_state.setdefault("form_color_label", PALETTE_OPTIONS[0])

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group",""), "")
    title = it.get("content","(untitled)")
    start = str(it.get("start",""))[:10]
    short = str(it.get("id",""))[:6]
    return f"{title} · {gname} · {start} · {short}"

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("📅 Add / Edit")

    # Category (type to create/select)
    names = {g["content"]: g["id"] for g in st.session_state["groups"]}
    cat = st.text_input("Category", placeholder="e.g., Germany · Residential")
    if cat:
        if cat in names:
            st.session_state["active_group_id"] = names[cat]
        else:
            g = normalize_group({"content": cat, "order": len(st.session_state["groups"])})
            st.session_state["groups"].append(g)
            st.session_state["active_group_id"] = g["id"]

    active_name = next((g["content"] for g in st.session_state["groups"]
                        if g["id"] == st.session_state.get("active_group_id","")), "")
    st.caption(f"Active category: **{active_name or '(none)'}**")

    # Picker (reliable selection for edit/delete)
    gids = {g["id"]: g["content"] for g in st.session_state["groups"]}
    opts = [(it["id"], _label_for_item(it, gids))
            for it in st.session_state["items"]
            if it.get("type")!="background"]
    labels = [lbl for _,lbl in opts]

    current_idx = 0
    if st.session_state.get("editing_item_id"):
        for i,(iid,_) in enumerate(opts):
            if str(iid) == str(st.session_state["editing_item_id"]):
                current_idx = i; break

    pick_label = st.selectbox("Select existing", labels or ["(none)"], index=current_idx if labels else 0)
    picked_id = next((iid for iid,lbl in opts if lbl == pick_label), "")

    if picked_id and str(picked_id) != str(st.session_state.get("editing_item_id","")):
        st.session_state["editing_item_id"] = str(picked_id)
        _prefill_from_item(_find_item(picked_id))

    _ensure_form_defaults()
    with st.form("item_form", clear_on_submit=False):
        cA,cB = st.columns(2)
        start = cA.date_input("Start", key="form_start")
        end   = cB.date_input("End",   key="form_end")
        start, end = ensure_range(start, end)

        st.text_input("Title", key="form_title", placeholder="Item title")
        st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")
        st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

        b1,b2,b3 = st.columns(3)
        add_clicked    = b1.form_submit_button("➕ Add item")
        edit_clicked   = b2.form_submit_button("✏️ Edit item")
        delete_clicked = b3.form_submit_button("🗑 Delete item")

    if add_clicked:
        col = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = st.session_state.get("active_group_id","")
        if not gid and st.session_state["groups"]:
            gid = st.session_state["groups"][-1]["id"]
        item = normalize_item({
            "id": str(uuid.uuid4()),
            "content": st.session_state["form_title"],
            "subtitle": st.session_state["form_subtitle"],
            "start": st.session_state["form_start"],
            "end":   st.session_state["form_end"],
            "group": gid,
            "color": col,
            "style": f"background:{col}; border-color:{col}",
        })
        st.session_state["items"].append(item)
        st.session_state["editing_item_id"] = item["id"]
        st.success("Item added."); st.rerun()

    if edit_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to edit.")
        else:
            col = PALETTE_MAP[st.session_state["form_color_label"]]
            for i,it in enumerate(st.session_state["items"]):
                if str(it.get("id")) == str(eid):
                    st.session_state["items"][i] = normalize_item({
                        "id": eid,
                        "content": st.session_state["form_title"],
                        "subtitle": st.session_state["form_subtitle"],
                        "start": st.session_state["form_start"],
                        "end":   st.session_state["form_end"],
                        "group": st.session_state.get("active_group_id", it.get("group","")),
                        "color": col,
                        "style": f"background:{col}; border-color:{col}",
                    })
                    break
            st.success("Item updated."); st.rerun()

    if delete_clicked:
        eid = st.session_state.get("editing_item_id","")
        if not eid:
            st.warning("Select an item to delete.")
        else:
            st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
            st.session_state["editing_item_id"] = ""
            st.success("Item deleted."); st.rerun()

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
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