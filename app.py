# app.py — organized layout + instant toggles + per-side dashed borders for open ranges

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

# ---------- Page & logging ----------
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

# App state (NOT widget keys)
ss.setdefault("selected_item_id", "(none)")
ss.setdefault("_last_prefill_from", "(none)")
ss.setdefault("_goto_item_id", None)

# ---------- Palette ----------
PALETTE_MAP = {
    "Blue":   "#3B82F6",
    "Green":  "#10B981",
    "Amber":  "#F59E0B",
    "Rose":   "#F43F5E",
    "Purple": "#8B5CF6",
    "Slate":  "#64748B",
}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# Color order so Green sits near Blue
COLOR_RANK = {
    "#3B82F6": 10,  # Blue
    "#10B981": 11,  # Green
    "#F59E0B": 12,  # Amber
    "#8B5CF6": 13,  # Purple
    "#F43F5E": 14,  # Rose
    "#64748B": 15,  # Slate
}

# Sentinels for open ranges
OPEN_START_SENTINEL = date(1970, 1, 1)
OPEN_END_SENTINEL   = date(2100, 1, 1)

# ---------- Helpers ----------
def _normalize_form_defaults():
    ss.setdefault("form_title", "")
    ss.setdefault("form_subtitle", "")
    ss.setdefault("form_category_name", "")
    ss.setdefault("form_no_start", False)
    ss.setdefault("form_no_end", False)
    ss.setdefault("form_start", date.today())
    ss.setdefault("form_end", date.today())
    ss.setdefault("form_color_label", PALETTE_OPTIONS[0])

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    ss["form_title"] = it.get("content", "")
    ss["form_subtitle"] = it.get("subtitle", "")
    ss["form_category_name"] = groups_by_id.get(it.get("group", ""), "")
    ss["form_no_start"] = bool(it.get("openStart", False))
    ss["form_no_end"]   = bool(it.get("openEnd", False))
    ss["form_start"] = _date_from_any(it.get("start")) or date.today()
    ss["form_end"]   = _date_from_any(it.get("end"))   or ss["form_start"]
    cur_color = it.get("color")
    for label, hexv in PALETTE_MAP.items():
        if hexv == cur_color:
            ss["form_color_label"] = label
            break

def _ensure_group_id_from_name(name_text: str) -> str:
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
    if v is None or v == "":
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        s = v.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            pass
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
    return None

def hex_to_rgba(hex_color: str, alpha: float = 0.22) -> str:
    if not isinstance(hex_color, str):
        return f"rgba(59,130,246,{alpha})"
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join([c*2 for c in h])
    try:
        r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    except Exception:
        return f"rgba(59,130,246,{alpha})"

def soft_style_from_color(hex_color: str, open_start: bool = False, open_end: bool = False) -> str:
    """Pastel fill + black text; dashed only on the open side(s)."""
    rgba = hex_to_rgba(hex_color, 0.22)
    # base: solid on all sides
    css = [
        f"background:{rgba}",
        "color:#111",
        f"border-color:{hex_color}",
        "border-width:2px",
        "border-style:solid",
    ]
    if open_start:
        css += ["border-left-style:dashed"]
    if open_end:
        css += ["border-right-style:dashed"]
    return "; ".join(css)

def _build_item_dict(item_id: str) -> dict:
    col_hex = PALETTE_MAP[ss["form_color_label"]]
    gid = _ensure_group_id_from_name(ss.get("form_category_name", ""))
    no_start = bool(ss.get("form_no_start"))
    no_end   = bool(ss.get("form_no_end"))
    start = _date_from_any(ss.get("form_start")) or date.today()
    end   = _date_from_any(ss.get("form_end")) or start
    if end < start:
        start, end = end, start

    s_for_store = OPEN_START_SENTINEL if no_start else start
    e_for_store = OPEN_END_SENTINEL   if no_end   else end

    item = {
        "id": item_id,
        "content": (ss["form_title"] or "").strip(),
        "subtitle": ss["form_subtitle"],
        "start": s_for_store,
        "end":   e_for_store,
        "group": gid,
        "color": col_hex,
        "openStart": no_start,
        "openEnd": no_end,
        "className": " ".join([c for c in ["open-start" if no_start else "", "open-end" if no_end else ""] if c]),
        "style": soft_style_from_color(col_hex, open_start=no_start, open_end=no_end),
    }
    normalized = normalize_item(item)
    for k in ("openStart", "openEnd", "className", "style", "color"):
        normalized[k] = item[k]
    return normalized

# ---- Height helpers ----
def _as_datetime(d):
    if isinstance(d, datetime): return d
    if isinstance(d, date):     return datetime(d.year, d.month, d.day)
    if isinstance(d, str):
        s = d.strip()
        try:
            if s.endswith("Z"): s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None

def _max_overlap(intervals):
    events = []
    for s, e in intervals:
        if s is None: continue
        if e is None: e = s
        events.append((s, +1)); events.append((e, -1))
    events.sort()
    cur = 0; mx = 0
    for _, d in events:
        cur += d; mx = max(mx, cur)
    return max(1, mx) if events else 1

def compute_auto_height(items, groups, stack=True):
    group_ids = [g.get("id") for g in groups] or ["_ungrouped"]
    per_lane, top_pad = 80, 120
    total = 0
    for gid in group_ids:
        ivs = []
        for it in items:
            g = it.get("group") or "_ungrouped"
            if g == gid:
                s = _as_datetime(it.get("start"))
                e = _as_datetime(it.get("end") or it.get("start"))
                ivs.append((s, e))
        total += _max_overlap(ivs) if stack else 1
    return max(260, top_pad + per_lane * total)

# ---------- Smart JSON importer ----------
def smart_import(text: str):
    doc = json.loads(text)

    def _get_case_insensitive(d: dict, key: str):
        for k in d.keys():
            if k.lower() == key.lower():
                return d[k]
        return None

    root = doc
    if isinstance(root, dict) and "data" in {k.lower() for k in root.keys()}:
        cand = _get_case_insensitive(root, "data")
        if isinstance(cand, dict):
            root = cand

    items_in  = _get_case_insensitive(root, "items")
    groups_in = _get_case_insensitive(root, "groups")

    if items_in is None and isinstance(root, dict):
        for v in root.values():
            if isinstance(v, dict):
                items_in  = items_in  or _get_case_insensitive(v, "items")
                groups_in = groups_in or _get_case_insensitive(v, "groups")

    if items_in is None:
        for v in root.values() if isinstance(root, dict) else []:
            if isinstance(v, list) and v and isinstance(v[0], dict):
                sample = v[0]
                if any(k in sample for k in ("content", "title", "name", "start", "startDate")):
                    items_in = v
                    break

    if not isinstance(items_in, list):
        return [], []

    groups_norm, items_norm, name_to_id = [], [], {}

    if isinstance(groups_in, list):
        for idx, g in enumerate(groups_in):
            gid = str(g.get("id") or uuid.uuid4())
            name = g.get("content") or g.get("name") or g.get("title") or f"Group {idx+1}"
            grp = normalize_group({"id": gid, "content": name, "order": idx})
            groups_norm.append(grp)
            name_to_id[(name or "").strip().lower()] = gid

    def _ensure_group_from_item_name(name: str) -> str:
        nm = (name or "").strip()
        if not nm: return ""
        lid = nm.lower()
        if lid in name_to_id: return name_to_id[lid]
        gid = str(uuid.uuid4())
        groups_norm.append(normalize_group({"id": gid, "content": nm, "order": len(groups_norm)}))
        name_to_id[lid] = gid
        return gid

    for it in items_in:
        if not isinstance(it, dict): continue
        iid = str(it.get("id") or uuid.uuid4())
        title = it.get("content") or it.get("title") or it.get("name") or "(untitled)"
        subtitle = it.get("subtitle") or it.get("description") or ""
        group_id = it.get("group") or it.get("groupId")
        if not group_id:
            gname = it.get("category") or it.get("groupName") or it.get("group_name")
            group_id = _ensure_group_from_item_name(gname) if gname else ""
        start = _date_from_any(it.get("start") or it.get("startDate"))
        end   = _date_from_any(it.get("end")   or it.get("endDate")) or start
        if end and start and end < start:
            start, end = end, start

        color = it.get("color") or PALETTE_MAP["Blue"]
        if not color.startswith("#"):
            color = PALETTE_MAP["Blue"]

        open_start = bool(it.get("openStart", False)) or (start and start <= OPEN_START_SENTINEL)
        open_end   = bool(it.get("openEnd", False))   or (end   and end   >= OPEN_END_SENTINEL)

        items_norm.append(normalize_item({
            "id": iid,
            "content": title,
            "subtitle": subtitle,
            "start": start or OPEN_START_SENTINEL if open_start else start,
            "end":   end   or OPEN_END_SENTINEL   if open_end   else end,
            "group": group_id,
            "color": color,
            "openStart": open_start,
            "openEnd": open_end,
            "className": " ".join([c for c in ["open-start" if open_start else "", "open-end" if open_end else ""] if c]),
            "style": soft_style_from_color(color, open_start=open_start, open_end=open_end),
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
            items_in, groups_in = smart_import(text)
            if items_in:
                ss["items"] = items_in
                ss["groups"] = groups_in
                ss["_goto_item_id"] = "(none)"
                ss["_last_prefill_from"] = "(none)"
                st.success(f"Imported {len(items_in)} items, {len(groups_in)} groups.")
                st.rerun()
            else:
                try:
                    normalize_state(ss, text)
                    ss["_goto_item_id"] = "(none)"
                    ss["_last_prefill_from"] = "(none)"
                    st.success("Imported using legacy normalizer.")
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
        ss["_goto_item_id"] = "(none)"
        ss["_last_prefill_from"] = "(none)"
        st.rerun()

# Lookups & defaults
groups_by_id = {g.get("id"): g.get("content", "") for g in ss["groups"]}
_normalize_form_defaults()

# Build items map BEFORE rendering the picker
item_by_id = {str(it.get("id")): it for it in ss["items"]}
picker_options = ["(none)"] + list(item_by_id.keys())

# Determine selection (no widget key → we control)
proposed = ss.get("_goto_item_id")
if proposed is None:
    proposed = ss.get("selected_item_id", "(none)")
if proposed not in picker_options:
    proposed = "(none)"
ss["_goto_item_id"] = None

default_index = picker_options.index(proposed)
selected_id = st.selectbox(
    "Select item to edit",
    options=picker_options,
    index=default_index,
    format_func=lambda v: "(none)" if v == "(none)" else _label_for_item(item_by_id[v], groups_by_id),
)
ss["selected_item_id"] = selected_id

# Prefill only when the selection actually changes
if selected_id != ss.get("_last_prefill_from"):
    if selected_id != "(none)":
        _prefill_form_from_item(item_by_id[selected_id], groups_by_id)
    ss["_last_prefill_from"] = selected_id

# ---- Instant toggles (outside the form so they rerun immediately) ----
st.markdown("##### Date options")
opt1, opt2 = st.columns([1, 1])
with opt1:
    st.checkbox("No start date (ongoing)", key="form_no_start", help="Show as running from the distant past; start side is dashed.")
with opt2:
    st.checkbox("No end date (open-ended)", key="form_no_end", help="Show as continuing into the future; end side is dashed.")

# ---- Organized Edit/Add form ----
with st.form("item_form", clear_on_submit=False):
    r1c1, r1c2 = st.columns([2, 2])
    with r1c1:
        st.text_input("Title", key="form_title")
    with r1c2:
        st.text_input("Subtitle (optional)", key="form_subtitle")

    r2c1, r2c2 = st.columns([2, 2])
    with r2c1:
        hint = ", ".join([g["content"] for g in ss["groups"]][:6])
        st.text_input("Category", key="form_category_name", help=("Existing: " + hint) if hint else None)
    with r2c2:
        st.selectbox("Color", PALETTE_OPTIONS, key="form_color_label")

    r3c1, r3c2 = st.columns([2, 2])
    with r3c1:
        st.date_input("Start", key="form_start", disabled=ss["form_no_start"])
    with r3c2:
        st.date_input("End", key="form_end", disabled=ss["form_no_end"])

    b1, b2, b3 = st.columns(3)
    with b1:
        btn_add = st.form_submit_button("Add new", type="primary", use_container_width=True)
    with b2:
        btn_save = st.form_submit_button("Save changes", use_container_width=True)
    with b3:
        btn_del = st.form_submit_button("Delete", type="secondary", use_container_width=True)

# ---- Actions ----
def _add_and_goto():
    new_id = str(uuid.uuid4())
    ss["items"].append(_build_item_dict(new_id))
    ss["_goto_item_id"] = new_id
    st.success("Item added.")
    st.rerun()

def _save_selected():
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
        ss["items"].append(_build_item_dict(target))
        ss["_goto_item_id"] = target
        st.info("Selected item not found; created it.")
        st.rerun()

if btn_add:
    title = (ss["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        _add_and_goto()

if btn_save:
    title = (ss["form_title"] or "").strip()
    if not title:
        st.warning("Title is required.")
    else:
        if ss["selected_item_id"] == "(none)":
            _add_and_goto()
        else:
            _save_selected()

if btn_del:
    if ss["selected_item_id"] == "(none)":
        st.warning("Select an item to delete (top dropdown).")
    else:
        tgt = ss["selected_item_id"]
        ss["items"] = [it for it in ss["items"] if str(it.get("id")) != tgt]
        ss["_goto_item_id"] = "(none)"
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

# ---- View options & Timeline ----
st.subheader("📂 View options")
names = st.multiselect("Filter categories", [g["content"] for g in ss["groups"]], key="filter_categories")
ids = {g["id"] for g in ss["groups"] if g["content"] in names} if names else set()
items_view  = [i for i in ss["items"]  if not ids or i.get("group", "") in ids]
groups_view = [g for g in ss["groups"] if not ids or g["id"] in ids]

# Enrich items for render
enriched = []
for i in items_view:
    j = dict(i)
    j["orderKey"] = COLOR_RANK.get(j.get("color", ""), 99)
    j["style"] = soft_style_from_color(
        j.get("color", "#3B82F6"),
        open_start=bool(j.get("openStart")),
        open_end=bool(j.get("openEnd")),
    )
    cls = []
    if j.get("openStart"): cls.append("open-start")
    if j.get("openEnd"):   cls.append("open-end")
    j["className"] = " ".join(cls)
    enriched.append(j)

height_px = compute_auto_height(enriched, groups_view, stack=True)

export_req = ss.get("_export_exact")
render_timeline(
    enriched, groups_view,
    selected_id=ss.get("selected_item_id", ""),
    export=export_req,
    stack=True,
    height_px=height_px
)
if export_req is not None:
    ss["_export_exact"] = None

# ---- Debug ----
with st.expander("Debug"):
    st.write({
        "items_count": len(ss["items"]),
        "groups_count": len(ss["groups"]),
        "selected_item_id": ss.get("selected_item_id"),
        "_last_prefill_from": ss.get("_last_prefill_from"),
        "_goto_item_id": ss.get("_goto_item_id"),
        "auto_height_px": height_px,
        "first_item": ss["items"][0] if ss["items"] else None,
        "first_group": ss["groups"][0] if ss["groups"] else None,
    })
