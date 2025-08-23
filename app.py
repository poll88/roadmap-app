# app.py — server-side PNG export (300 PPI) with Month/Quarter granularity

import uuid
import io
import logging
from datetime import date, datetime
import streamlit as st

from lib.styles import GLOBAL_CSS
from lib.state import (
    normalize_item, normalize_group, normalize_state,
    reset_defaults, ensure_range, export_items_groups
)
from lib.timeline import render_timeline  # unchanged (no click selection)

# NEW: matplotlib for server-rendered PNG
from matplotlib import pyplot as plt, dates as mdates
from matplotlib.patches import Rectangle

# ----------------- Setup -----------------
st.set_page_config(page_title="Roadmap", page_icon="🗺️", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("roadmap")

# ----------------- Session bootstrap -----------------
st.session_state.setdefault("items", [])
st.session_state.setdefault("groups", [])
st.session_state.setdefault("active_group_id", "")
st.session_state.setdefault("editing_item_id", "")
st.session_state.setdefault("_last_picker_id", "")

# Be tolerant to either normalize_state signature
try:
    res = normalize_state(st.session_state)
    if isinstance(res, tuple):
        st.session_state["items"], st.session_state["groups"] = res
except TypeError:
    res = normalize_state(st.session_state.get("items"), st.session_state.get("groups"))
    if isinstance(res, tuple):
        st.session_state["items"], st.session_state["groups"] = res

# ---------- Pastel palette ----------
PALETTE = [
    ("Lavender",  "#E9D5FF"), ("Baby Blue", "#BFDBFE"), ("Mint", "#BBF7D0"),
    ("Lemon", "#FEF9C3"), ("Peach", "#FDE1D3"), ("Blush", "#FBCFE8"),
    ("Sky", "#E0F2FE"), ("Mauve", "#F5D0FE"), ("Sage", "#D1FAE5"), ("Sand", "#F5E7C6"),
]
PALETTE_MAP = {f"{n} ({h})": h for n, h in PALETTE}
PALETTE_OPTIONS = list(PALETTE_MAP.keys())

# ---------- Helpers ----------
def _find_item(iid: str):
    for it in st.session_state["items"]:
        if str(it.get("id")) == str(iid):
            return it
    return None

def _ensure_form_defaults():
    st.session_state.setdefault("form_title", "")
    st.session_state.setdefault("form_subtitle", "")
    st.session_state.setdefault("form_start", date.today())
    st.session_state.setdefault("form_end", date.today())
    st.session_state.setdefault("form_color_label", PALETTE_OPTIONS[0])
    st.session_state.setdefault("form_category", "")

def _prefill_form_from_item(it: dict, groups_by_id: dict):
    st.session_state["form_title"] = it.get("content", "")
    st.session_state["form_subtitle"] = it.get("subtitle", "")
    st.session_state["form_start"] = it.get("start") or date.today()
    st.session_state["form_end"] = it.get("end") or date.today()
    for label, hexv in PALETTE_MAP.items():
        if hexv == it.get("color"):
            st.session_state["form_color_label"] = label
            break
    gid = it.get("group")
    st.session_state["form_category"] = groups_by_id.get(gid, "") if gid else ""
    if gid:
        st.session_state["active_group_id"] = gid

def _label_for_item(it, groups_by_id):
    gname = groups_by_id.get(it.get("group", ""), "")
    title = it.get("content", "(untitled)")
    start = str(it.get("start", ""))[:10]
    short = str(it.get("id", ""))[:6]
    return f"{title} · {gname} · {start} · {short}"

def _resolve_group_id_from_text(category_text: str) -> str:
    name = (category_text or "").strip()
    if not name:
        return ""
    for g in st.session_state["groups"]:
        if g["content"].lower() == name.lower():
            return g["id"]
    g = normalize_group({"content": name, "order": len(st.session_state["groups"])})
    st.session_state["groups"].append(g)
    LOG.info("Created new category name=%r id=%s", name, g["id"])
    return g["id"]

def _suggest_categories(query: str, k=5):
    q = (query or "").strip().lower()
    if not q:
        return []
    return [g["content"] for g in st.session_state["groups"] if q in g["content"].lower()][:k]

# ---------- PNG export helpers (server-rendered @ 300 PPI) ----------
def _to_date(d):
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, str) and d:
        return datetime.fromisoformat(d[:10]).date()
    return date.today()

def _month_add(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    # clamp day to month length
    _last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return date(y, m, min(d.day, _last))

def _span(items):
    """Earliest start, latest end across items (ignores backgrounds)."""
    if not items:
        t = date.today()
        return t, t
    smin, emax = None, None
    for it in items:
        if it.get("type") == "background":
            continue
        s = _to_date(it.get("start"))
        e = _to_date(it.get("end") or it.get("start"))
        if e < s:
            s, e = e, s
        smin = s if smin is None else min(smin, s)
        emax = e if emax is None else max(emax, e)
    if smin is None:
        t = date.today()
        return t, t
    return smin, emax

def _export_png_bytes(items, groups, *, time_base: str, pad_months_each_side: int, width_in: float, show_grid: bool) -> bytes:
    """
    Render a static PNG timeline using matplotlib.
    time_base: 'Month' or 'Quarter'
    width_in: figure width in inches (height auto based on groups)
    """
    if not items:
        return b""

    # order groups by 'order' if present, else by content
    groups_sorted = sorted(groups, key=lambda g: (g.get("order", 0), g.get("content", "")))
    gid_to_row = {g["id"]: i for i, g in enumerate(groups_sorted)}
    row_labels = [g["content"] for g in groups_sorted]
    nrows = max(1, len(groups_sorted))

    # compute x-span with padding
    start, end = _span(items)
    start = _month_add(start.replace(day=1), -pad_months_each_side)
    end_last = _month_add(end.replace(day=1), pad_months_each_side + 1)  # +1 to include the last month fully
    # figure height based on rows
    height_in = max(3.5, 0.9 * nrows + 1.6)

    # create figure
    dpi = 300
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=dpi)

    # background row shading
    for r in range(nrows):
        if r % 2 == 0:
            ax.axhspan(r - 0.4, r + 0.4, color="#f7f7fb", zorder=0)

    # draw items
    for it in items:
        if it.get("type") == "background":
            continue
        gid = it.get("group", "")
        if gid not in gid_to_row:
            # unseen group (e.g., filtered away) -> skip
            continue
        y = gid_to_row[gid]
        s = _to_date(it.get("start"))
        e = _to_date(it.get("end") or it.get("start"))
        if e < s:
            s, e = e, s
        xs = mdates.date2num(s)
        xe = mdates.date2num(e)
        # ensure visible width
        if xe == xs:
            xe = xs + 1
        color = it.get("color", "#CBD5E1")
        rect = Rectangle((xs, y - 0.25), xe - xs, 0.5, facecolor=color, edgecolor=color, linewidth=1.0, zorder=2)
        ax.add_patch(rect)
        # text (title + subtitle)
        title = (it.get("content") or "").strip()
        subtitle = (it.get("subtitle") or "").strip()
        label = title if not subtitle else f"{title}\n{subtitle}"
        ax.text(xs + 0.1, y, label, va="center", ha="left", fontsize=8, zorder=3)

    # y-axis
    ax.set_ylim(-0.6, nrows - 0.4)
    ax.set_yticks(range(nrows))
    ax.set_yticklabels(row_labels, fontsize=9)

    # x-axis
    ax.set_xlim(mdates.date2num(start), mdates.date2num(end_last))
    if time_base == "Quarter":
        locator = mdates.MonthLocator(bymonth=[1, 4, 7, 10])
        fmt = mdates.DateFormatter("%b %Y")
    else:
        locator = mdates.MonthLocator(interval=1)
        fmt = mdates.DateFormatter("%b %Y")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(fmt)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)

    if show_grid:
        ax.grid(axis="x", color="#e5e7eb", linewidth=0.8, zorder=1)

    # style
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#e5e7eb")
    ax.spines["bottom"].set_color("#e5e7eb")

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    plt.close(fig)
    return buf.getvalue()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.header("📅 Add / Edit")

    groups_by_id = {g["id"]: g["content"] for g in st.session_state["groups"]}
    item_labels = [_label_for_item(it, groups_by_id)
                   for it in st.session_state["items"]
                   if it.get("type") != "background"]
    item_ids = [it["id"] for it in st.session_state["items"] if it.get("type") != "background"]

    PICK_NEW = "➕ New item"
    picker_options = [PICK_NEW] + item_labels

    if st.session_state.get("editing_item_id") and st.session_state["editing_item_id"] in item_ids:
        default_idx = item_ids.index(st.session_state["editing_item_id"]) + 1
    else:
        default_idx = 0

    pick = st.selectbox("Item", picker_options, index=default_idx, key="picker_label")

    # Selection change handling
    if pick == PICK_NEW:
        if st.session_state.get("_last_picker_id"):
            LOG.info("Picker -> NEW (was %s)", st.session_state["_last_picker_id"])
            st.session_state["editing_item_id"] = ""
            st.session_state["_last_picker_id"] = ""
            _ensure_form_defaults()
    else:
        sel_idx = picker_options.index(pick) - 1
        sel_id = item_ids[sel_idx]
        if str(sel_id) != str(st.session_state.get("_last_picker_id", "")):
            LOG.info("Picker selection changed: %s -> %s", st.session_state.get("_last_picker_id", ""), sel_id)
            st.session_state["editing_item_id"] = str(sel_id)
            st.session_state["_last_picker_id"] = str(sel_id)
            _ensure_form_defaults()
            _prefill_form_from_item(_find_item(sel_id), groups_by_id)

    # ---- form with single category box ----
    _ensure_form_defaults()
    with st.form("item_form", clear_on_submit=False):
        colA, colB = st.columns(2)
        start = colA.date_input("Start", key="form_start")
        end = colB.date_input("End", key="form_end")
        start, end = ensure_range(start, end)

        st.text_input("Title", key="form_title", placeholder="Item title")
        st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")

        st.text_input("Category", key="form_category", placeholder="Type to select or create")
        sugg = _suggest_categories(st.session_state.get("form_category", ""), k=5)
        if sugg:
            st.caption("Suggestions: " + " · ".join(sugg))

        st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

        add_clicked = st.form_submit_button("➕ Add item", use_container_width=True)
        edit_clicked = st.form_submit_button("✏️ Edit item", use_container_width=True)
        delete_clicked = st.form_submit_button("🗑 Delete item", use_container_width=True)

    # ------ Actions ------
    if add_clicked:
        col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
        gid = _resolve_group_id_from_text(st.session_state.get("form_category", ""))
        item = normalize_item({
            "id": str(uuid.uuid4()),
            "content": st.session_state["form_title"],
            "subtitle": st.session_state["form_subtitle"],
            "start": st.session_state["form_start"],
            "end": st.session_state["form_end"],
            "group": gid,
            "color": col_hex,
            "style": f"background:{col_hex}; border-color:{col_hex}",
        })
        st.session_state["items"].append(item)
        LOG.info("ADD id=%s title=%r", item["id"], item["content"])
        st.session_state["editing_item_id"] = ""
        st.session_state["_last_picker_id"] = ""
        st.success("Item added."); st.rerun()

    if edit_clicked:
        eid = st.session_state.get("editing_item_id", "")
        if not eid:
            st.warning("Select an item to edit (top dropdown).")
        else:
            col_hex = PALETTE_MAP[st.session_state["form_color_label"]]
            gid = _resolve_group_id_from_text(st.session_state.get("form_category", ""))
            for i, it in enumerate(st.session_state["items"]):
                if str(it.get("id")) == str(eid):
                    st.session_state["items"][i] = normalize_item({
                        "id": eid,
                        "content": st.session_state["form_title"],
                        "subtitle": st.session_state["form_subtitle"],
                        "start": st.session_state["form_start"],
                        "end": st.session_state["form_end"],
                        "group": gid if gid != "" else it.get("group", ""),
                        "color": col_hex,
                        "style": f"background:{col_hex}; border-color:{col_hex}",
                    })
                    LOG.info("EDIT id=%s", eid)
                    break
            st.success("Item updated."); st.rerun()

    if delete_clicked:
        eid = st.session_state.get("editing_item_id", "")
        if not eid:
            st.warning("Select an item to delete (top dropdown).")
        else:
            LOG.info("DELETE id=%s", eid)
            st.session_state["items"] = [it for it in st.session_state["items"] if str(it.get("id")) != str(eid)]
            st.session_state["editing_item_id"] = ""
            st.session_state["_last_picker_id"] = ""
            st.success("Item deleted."); st.rerun()

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        LOG.info("RESET")
        reset_defaults(st.session_state); st.rerun()

    exported = export_items_groups(st.session_state)
    st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

    # ---- NEW: PNG Export (server-rendered) ----
    st.subheader("📸 PNG Export (300 PPI)")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        time_base = st.selectbox("Time base", ["Month", "Quarter"], index=0, help="Tick labels every month or quarter.")
    with col2:
        pad_months = st.slider("Padding (months each side)", 0, 12, 1)
    with col3:
        width_in = st.slider("Width (inches @300 PPI)", 8, 60, 18)

    # We'll generate based on the *filtered* view in the main area (computed below).
    # To keep sidebar stateless, we store choices now:
    st.session_state["export_opts"] = {"time_base": time_base, "pad_months": pad_months, "width_in": float(width_in)}

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded:
        import json
        data = json.loads(uploaded.read().decode("utf-8"))
        st.session_state["items"] = [normalize_item(x) for x in data.get("items", [])]
        st.session_state["groups"] = [normalize_group(x) for x in data.get("groups", [])]
        st.session_state["editing_item_id"] = ""
        st.session_state["_last_picker_id"] = ""
        LOG.info("IMPORT items=%d groups=%d", len(st.session_state["items"]), len(st.session_state["groups"]))
        st.success("Imported."); st.rerun()

# ----------------- MAIN -----------------
st.title("Roadmap Timeline")

if not st.session_state["items"]:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>', unsafe_allow_html=True)
else:
    names = st.multiselect("Filter categories", [g["content"] for g in st.session_state["groups"]])
    ids = {g["id"] for g in st.session_state["groups"] if g["content"] in names} if names else set()
    items_view = [i for i in st.session_state["items"] if not ids or i.get("group", "") in ids]
    groups_view = [g for g in st.session_state["groups"] if not ids or g["id"] in ids]

    render_timeline(items_view, groups_view, selected_id=st.session_state.get("editing_item_id", ""))

    # ---- PNG download button (uses filtered view & current export options) ----
    opts = st.session_state.get("export_opts", {"time_base": "Month", "pad_months": 1, "width_in": 18.0})
    png_bytes = _export_png_bytes(
        items_view, groups_view,
        time_base=opts["time_base"],
        pad_months_each_side=opts["pad_months"],
        width_in=opts["width_in"],
        show_grid=True
    )
    st.download_button(
        "⬇️ Export PNG (300 PPI)",
        data=png_bytes if png_bytes else b"",
        file_name="timeline_300ppi.png",
        mime="image/png",
        disabled=(not items_view)
    )