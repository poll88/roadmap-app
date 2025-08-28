# app.py — robust JSON import (auto-detect schema), working Save (updates selection),
# add multiple items, unified Category input, PNG bg toggle, and a small Debug expander.

import uuid
import hashlib
import json
import logging
from datetime import date, datetime
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, export_items_groups
)
from lib.timeline import render_timeline

# ---------- Setup ----------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("roadmap")

# ---------- Session ----------
ss = st.session_state
ss.setdefault("items", [])
ss.setdefault("groups", [])
ss.setdefault("_last_import_hash", "")
ss.setdefault("_export_exact", None)
ss.setdefault("png_include_bg", True)
ss.setdefault("selected_item_id", "(none)")  # bound to the picker

# ---------- Colors ----------
PALETTE_MAP = {
    "Blue":   "#3B82F6",
    "Green":  "#10B981",
    "Amber":  "#F59E0B",
    "Rose":   "#F43F5E",
    "Purple": "#8B5CF6",
    "Slate":  "#64748B",
}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# ---------- Helpers ----------
def _normalize_form_defaults():
    ss.setdefault("form_title", "")
    ss.setdefault("form_subtitle", "")
    ss.setdefault("form_category_name", "")
    ss.setdefault("form_start", date.today())
    ss.setdefault("form_end", date.today())
    ss.setdefault("form_color_label", PALETTE_OPTIONS[0])

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    ss["form_title"] = it.get("content", "")
    ss["form_subtitle"] = it.get("subtitle", "")
    ss["form_category_name"] = groups_by_id.get(it.get("group", ""), "")
    # tolerate strings/datetimes
    ss["form_start"] = _date_from_any(it.get("start")) or date.today()
    ss["form_end"]   = _date_from_any(it.get("end"))   or ss["form_start"]
    cur_color = it.get("color")
    for label, hexv in PALETTE_MAP.items():
        if hexv == cur_color:
            ss["form_color_label"] = label
            break

def _ensure_group_id_from_name(name_text: str) -> str:
    """Case-insensitive match; create new if not found; empty -> ungrouped."""
    name = (name_text or "").strip()
    if not name:
        return ""
    for g in ss["groups"]:
        if (g.get("content") or "").strip().lower() == name.lower():
            return g.get("id", "")
    gid = str(uuid.uuid4())
    ss["groups"].append(normalize_group({"id": gid, "content": name, "order": len(ss["groups"])}))
    return gid

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group", ""), "")
    title = it.get("content", "(untitled)")
    start = str(_date_from_any(it.get("start")) or "")[:10]
    short = str(it.get("id", ""))[:6]
    return f"{title} · {gname} · {start} · {short}"

def _date_from_any(v):
    """Coerce many date formats into a date(). Accepts date, datetime, or string."""
    if v is None or v == "":
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        # common cleanups
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            # ISO with time or date-only
            dt = datetime.fromisoformat(s)
            return dt.date()
        except Exception:
            pass
        # try date-only simple formats
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
    return None

def _pick_color_hex(label_hint: str = "") -> str:
    """Consistent color choice for imported items when no color provided."""
    if not label_hint:
        return PALETTE_MAP["Blue"]
    keys = list(PALETTE_MAP.values())
    idx = abs(hash(label_hint)) % len(keys)
    return keys[idx]

def _build_item_dict(item_id: str) -> dict:
    col_hex = PALETTE_MAP[ss["form_color_label"]]
    gid = _ensure_group_id_from_name(ss.get("form_category_name", ""))
    start = _date_from_any(ss.get("form_start")) or date.today()
    end   = _date_from_any(ss.get("form_end")) or start
    if end < start:
        start, end = end, start
    return normalize_item({
        "id": item_id,
        "content": (ss["form_title"] or "").strip(),
        "subtitle": ss["form_subtitle"],
        "start": start,
        "end":   end,
        "group": gid,  # empty => Ungrouped lane (renderer handles it)
        "color": col_hex,
        "style": f"background:{col_hex}; border-color:{col_hex}",
    })

# ---------- Smart JSON importer ----------
def smart_import(text: str):
    """
    Accepts many shapes:
      {items:[...], groups:[...]}
      {data:{items:[...], groups:[...]}}
      {Items:[...], Groups:[...]} (case variants)
      Or just {items:[...]} (we will synthesize groups from item.category/name)
    Items fields we recognize:
      id, content/title/name, subtitle/description,
      start/startDate, end/endDate,
      group (id), groupId, category/groupName (string),
      color
    """
    doc = json.loads(text)

    def _get_case_insensitive(d: dict, key: str):
        for k in d.keys():
            if k.lower() == key.lower():
                return d[k]
        return None

    root = doc
    # Allow nested {data:{...}}
    if isinstance(root, dict) and "data" in {k.lower() for k in root.keys()}:
        cand = _get_case_insensitive(root, "data")
        if isinstance(cand, dict):
            root = cand

    items_in  = _get_case_insensitive(root, "items")
    groups_in = _get_case_insensitive(root, "groups")

    if items_in is None and isinstance(root, dict):
        # Look one more level deep for common wrappers
        for v in root.values():
            if isinstance(v, dict):
                items_in  = items_in  or _get_case_insensitive(v, "items")
                groups_in = groups_in or _get_case_insensitive(v, "groups")

    if items_in is None:
        # Try a loose guess: any list of dicts that looks like items
        for v in root.values() if isinstance(root, dict) else []:
            if isinstance(v, list) and v and isinstance(v[0], dict):
                sample = v[0]
                if any(k in sample for k in ("content", "title", "name", "start", "startDate")):
                    items_in = v
                    break

    if not isinstance(items_in, list):
        return [], []  # nothing recognizable

    groups_norm = []
    items_norm  = []

    # Build a groups map from provided groups (if any)
    name_to_id = {}
    if isinstance(groups_in, list):
        for idx, g in enumerate(groups_in):
            gid = str(g.get("id") or uuid.uuid4())
            name = g.get("content") or g.get("name") or g.get("title") or f"Group {idx+1}"
            grp = normalize_group({"id": gid, "content": name, "order": idx})
            groups_norm.append(grp)
            name_to_id[(name or "").strip().lower()] = gid

    def _ensure_group_from_item_name(name: str) -> str:
        nm = (name or "").strip()
        if not nm:
            return ""
        lid = nm.lower()
        if lid in name_to_id:
            return name_to_id[lid]
        gid = str(uuid.uuid4())
        groups_norm.append(normalize_group({"id": gid, "content": nm, "order": len(groups_norm)}))
        name_to_id[lid] = gid
        return gid

    for it in items_in:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id") or uuid.uuid4())
        title = it.get("content") or it.get("title") or it.get("name") or "(untitled)"
        subtitle = it.get("subtitle") or it.get("description") or ""

        # Resolve group
        group_id = it.get("group") or it.get("groupId")
        if not group_id:
            # maybe string category/groupName
            gname = it.get("category") or it.get("groupName") or it.get("group_name")
            group_id = _ensure_group_from_item_name(gname) if gname else ""

        # Dates
        start = _date_from_any(it.get("start") or it.get("startDate"))
        end   = _date_from_any(it.get("end")   or it.get("endDate")) or start
        if not start:
            # If no start at all, skip this item (cannot render)
            continue
        if end and end < start:
            start, end = end, start

        # Color
        color = it.get("color")
        if not color or not isinstance(color, str) or not color.startswith("#"):
            color = _pick_color_hex(title + subtitle)

        items_norm.append(normalize_item({
            "id": iid,
            "content": title,
            "subtitle": subtitle,
            "start": start,
            "end":   end,
            "group": group_id,
            "color": color,
            "style": f"background:{color}; border-color:{color}",
        }))

    return items_norm, groups_norm

# ---------- Page ----------
st.title("🗺️ Product Roadmap")

# Sidebar: Import / Export / Reset
with st.sidebar:
    st.header("Data")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded is not None:
        text = uploaded.read().decode("utf-8", errors="replace")
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if h != ss.get("_last_import_hash", ""):
            ss["_last_import_hash"] = h
            imported_items, imported_groups = smart_import(text)
            if imported_items:
                ss["items"]  = imported_items
                # If file didn't include groups, we may have synthesized them above
                ss["groups"] = imported_groups
                ss["selected_item_id"] = "(none)"
                st.success(f"Imported {len(imported_items)} items, {len(imported_groups)} groups.")
                st.rerun()
            else:
                # Try legacy project normalizer as a fallback
                try:
                    normalize_state(ss, text)
                    st.success("Imported using legacy normalizer.")
                    ss["selected_item_id"] = "(none)"
                    st.rerun()
                except Exception:
                    st.error("Import failed or empty. Expect JSON with an 'items' array (and optionally 'groups').")

    exported = export_items_groups(ss)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    st.divider()
    if st.button("Reset (clear all)"):
        keep_bg = ss.get("png_include_bg", True)
        reset_defaults(ss)
        ss["png_include_bg"] = keep_bg
        ss["selected_item_id"] = "(none)"
        st.rerun()

# Lookups and form defaults
groups_by_id = {g.get("id"): g.get("content", "") for g in ss["groups"]}
_normalize_form_defaults()

# ---- Picker bound directly to ids ----
item_by_id = {str(it.get("id")): it for it in ss["items"]}
picker_options = ["(none)"] + list(item_by_id.keys())
if ss["selected_item_id"] not in picker_options:
    ss["selected_item_id"] = "(none)"

selected_id = st.selectbox(
    "Select item to edit",
    options=picker_options,
    key="selected_item_id",
    format_func=lambda v: "(none)" if v == "(none)" else _label_for_item(item_by_id[v], groups_by_id),
)

# Prefill form for selection
if selected_id != "(none)":
    _prefill_form_from_item(item_by_id[selected_id], groups_by_id)

# ---- Form (tab order: Title → Subtitle → Category → Start → End → Color) ----
with st.form("item_form", clear_on_submit=False):
    c1, c2 = st.columns([2, 2])
    with c1:
        st.text_input("Title", key="form_title")
    with c2:
        st.text_input("Subtitle (optional)", key="form_subtitle")

    c3, c4 = st.columns([2, 2])
    with c3:
        hint = ", ".join([g["content"] for g in ss["groups"]][:6])
        st.text_input("Category", key="form_category_name", help=("Existing: " + hint) if hint else None)
    with c4:
        st.date_input("Start", key="form_start")

    c5, c6 = st.columns([2, 2])
    with c5:
        st.date_input("End", key="form_end")
    with c6:
        st.selectbox("Color", PALETTE_OPTIONS, key="form_color_label")

    b1, b2, b3 = st.columns(3)
    with b1: btn_add  = st.form_submit_button("Add new",   type="primary",  use_container_width=True)
    with b2: btn_save = st.form_submit_button("Save changes",               use_container_width=True)
    with b3: btn_del  = st.form_submit_button("Delete",     type="secondary",use_container_width=True)

# ---- Actions ----
if btn_add:
    title = (ss["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        new_id = str(uuid.uuid4())
        # Build and append
        item = _build_item_dict(new_id)
        ss["items"].append(item)
        # Auto-select new item so Save applies to it
        ss["selected_item_id"] = new_id
        st.success("Item added.")
        st.rerun()

if btn_save:
    title = (ss["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        if ss["selected_item_id"] == "(none)":
            # Treat Save as create when nothing selected
            new_id = str(uuid.uuid4())
            ss["items"].append(_build_item_dict(new_id))
            ss["selected_item_id"] = new_id
            st.success("Item saved (new).")
            st.rerun()
        else:
            target = ss["selected_item_id"]
            updated = False
            for i, it in enumerate(ss["items"]):
                if str(it.get("id")) == target:
                    ss["items"][i] = _build_item_dict(target)
                    updated = True
                    break
            if updated:
                st.success("Item updated.")
                st.rerun()
            else:
                # If somehow missing, create it using the target id
                ss["items"].append(_build_item_dict(target))
                st.info("Selected item not found; created it.")
                st.rerun()

if btn_del:
    if ss["selected_item_id"] == "(none)":
        st.warning("Select an item to delete (top dropdown).")
    else:
        tgt = ss["selected_item_id"]
        ss["items"] = [it for it in ss["items"] if str(it.get("id")) != tgt]
        ss["selected_item_id"] = "(none)"
        st.success("Item deleted.")
        st.rerun()

st.divider()

# ---- PNG export options ----
st.subheader("🎨 Export PNG")
st.checkbox("Include background color in PNG", key="png_include_bg")
if st.button("Download PNG", use_container_width=True):
    ss["_export_exact"] = {
        "kind": "png",
        "mode": "visible",
        "includeBg": bool(ss.get("png_include_bg", True)),
    }
    st.toast("Exporting PNG…", icon="🖼️")

# ---- Filters & Timeline ----
st.subheader("📂 View options")
names = st.multiselect("Filter categories", [g["content"] for g in ss["groups"]], key="filter_categories")
ids = {g["id"] for g in ss["groups"] if g["content"] in names} if names else set()
items_view  = [i for i in ss["items"]  if not ids or i.get("group", "") in ids]
groups_view = [g for g in ss["groups"] if not ids or g["id"] in ids]

export_req = ss.get("_export_exact")
render_timeline(items_view, groups_view, selected_id=ss.get("selected_item_id", ""), export=export_req)
if export_req is not None:
    ss["_export_exact"] = None

# ---- Debug (you asked to use debug to see where we’re stuck) ----
with st.expander("Debug"):
    st.write({
        "items_count": len(ss["items"]),
        "groups_count": len(ss["groups"]),
        "selected_item_id": ss.get("selected_item_id"),
        "first_item": ss["items"][0] if ss["items"] else None,
        "first_group": ss["groups"][0] if ss["groups"] else None,
    })
