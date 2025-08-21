# --- Roadmap "Rescue" launcher: paints immediately, then diagnoses, then runs the app ---

import os, sys, json, traceback
from datetime import date, datetime
import streamlit as st

st.set_page_config(page_title="Roadmap – Rescue", page_icon="🗺️", layout="wide")

# 0) Always show something so you know the script is running
st.title("🧭 Roadmap – Rescue Mode")
st.caption("If you can read this, the script started. Next: quick diagnostics below.")

# 1) Quick repo/ENV diagnostics (no third-party imports yet)
with st.expander("🔎 Diagnostics (click to expand)", expanded=True):
    st.write("**Working directory**:", os.getcwd())
    st.write("**Python**:", sys.version)
    st.write("**Sys.path (first 3)**:", sys.path[:3])

    # List top-level and lib/ contents to verify files are present
    try:
        toplevel = sorted(os.listdir("."))
    except Exception as e:
        toplevel = [f"(os.listdir('.') failed: {e})"]
    st.write("**Repo root files**:", toplevel)

    lib_exists = os.path.isdir("lib")
    st.write("**lib/ exists?**", lib_exists)
    if lib_exists:
        try:
            libfiles = sorted(os.listdir("lib"))
        except Exception as e:
            libfiles = [f"(os.listdir('lib') failed: {e})"]
        st.write("**lib contents**:", libfiles)
        st.caption("Tip: ensure `lib/__init__.py` exists (even empty) so Python treats it as a package.")

# 2) Try to import your modules safely and show errors inline (not only in logs)
imports_ok = False
err = None
try:
    import importlib
    styles   = importlib.import_module("lib.styles")
    state    = importlib.import_module("lib.state")
    timeline = importlib.import_module("lib.timeline")
    sidebar  = importlib.import_module("lib.sidebar") if os.path.exists("lib/sidebar.py") else None
    ids      = importlib.import_module("lib.ids") if os.path.exists("lib/ids.py") else None
    debugmod = importlib.import_module("lib.debug") if os.path.exists("lib/debug.py") else None
    imports_ok = True
except Exception as e:
    err = e

if not imports_ok:
    st.error("❌ Import error: your modules could not be imported.")
    st.exception(err)
    st.write(
        "Common fixes:\n"
        "- Verify your **Main file path** points to `app.py` in Streamlit Cloud settings.\n"
        "- Make sure the `lib/` folder is committed to the same branch and contains your modules.\n"
        "- Add an empty file `lib/__init__.py` to mark it as a package."
    )
    st.stop()

# 3) Apply global CSS (now that imports work)
st.markdown(styles.GLOBAL_CSS, unsafe_allow_html=True)

# 4) Minimal helpers from your modules (fetched via the safe imports above)
normalize_item = state.normalize_item
normalize_group = state.normalize_group
normalize_state = state.normalize_state
reset_defaults = state.reset_defaults
ensure_range = state.ensure_range
export_items_groups = state.export_items_groups

# 5) Session bootstrap (safe & minimal)
session = st.session_state
session.setdefault("items", [])
session.setdefault("groups", [])
session.setdefault("active_group_id", "")
session.setdefault("editing_item_id", "")

# Normalize
try:
    session["items"], session["groups"] = normalize_state(session.get("items"), session.get("groups"))
except TypeError:
    # in some earlier versions normalize_state mutated in-place; fallback
    normalize_state(session)

# 6) Sidebar form + reliable picker (no iframe interaction needed)
with st.sidebar:
    st.header("📅 Add / Edit")

    # Category field (type to create)
    group_names = {g["content"]: g["id"] for g in session["groups"]}
    new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")
    if new_group_name and new_group_name not in group_names:
        g = normalize_group({"content": new_group_name, "order": len(session["groups"])})
        session["groups"].append(g)
        group_names[new_group_name] = g["id"]
    active_group = group_names.get(new_group_name) if new_group_name else ""

    # Reliable picker drives selection
    labels = [f'{i.get("content") or "Untitled"} · {i.get("id","")[:6]}' for i in session["items"]]
    ids_list = [i.get("id") for i in session["items"]]
    picked_label = st.selectbox("Select existing", labels or ["(none)"])
    picked_id = ids_list[labels.index(picked_label)] if labels and picked_label in labels else ""

    def _find_item(iid):
        for it in session["items"]:
            if str(it.get("id")) == str(iid):
                return it
        return None

    sel = _find_item(picked_id) if picked_id else None

    # Form fields (prefill when selection exists)
    t_title = st.text_input("Title", sel.get("content","") if sel else "")
    t_sub   = st.text_input("Subtitle (optional)", sel.get("subtitle","") if sel else "")
    colA, colB = st.columns(2)
    s_val = state._coerce_date(sel["start"]) if sel and sel.get("start") else date.today()
    e_val = state._coerce_date(sel["end"])   if sel and sel.get("end")   else date.today()
    s_date = colA.date_input("Start", value=s_val)
    e_date = colB.date_input("End",   value=e_val)
    s_date, e_date = ensure_range(s_date, e_date)

    # Palette (pastel 10)
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
    PALETTE_MAP = {f"{n} ({h})": h for n,h in PALETTE}
    PALETTE_OPTIONS = list(PALETTE_MAP.keys())
    default_label = next((lab for lab,hexv in PALETTE_MAP.items() if hexv==(sel or {}).get("color")), PALETTE_OPTIONS[0])
    color_label = st.selectbox("Bar color", PALETTE_OPTIONS,
                               index=PALETTE_OPTIONS.index(default_label) if default_label in PALETTE_OPTIONS else 0)
    color_hex = PALETTE_MAP[color_label]

    c1, c2, c3 = st.columns(3)
    if c1.button("➕ Add item"):
        item = normalize_item({
            "content": t_title,
            "subtitle": t_sub,
            "start": s_date,
            "end": e_date,
            "group": active_group or (session["groups"][-1]["id"] if session["groups"] else ""),
            "color": color_hex,
            "style": f"background:{color_hex}; border-color:{color_hex}",
        })
        session["items"].append(item)
        st.success("Item added")

    if c2.button("✏️ Edit item"):
        if not picked_id:
            st.warning("Pick an existing item above.")
        else:
            for ix, it in enumerate(session["items"]):
                if str(it.get("id")) == str(picked_id):
                    updated = normalize_item({
                        "id": picked_id,
                        "content": t_title,
                        "subtitle": t_sub,
                        "start": s_date,
                        "end": e_date,
                        "group": active_group or it.get("group",""),
                        "color": color_hex,
                        "style": f"background:{color_hex}; border-color:{color_hex}",
                    })
                    session["items"][ix] = updated
                    st.success("Item updated")
                    break

    if c3.button("🗑 Delete item"):
        if not picked_id:
            st.warning("Pick an existing item above.")
        else:
            session["items"] = [it for it in session["items"] if str(it.get("id")) != str(picked_id)]
            st.success("Item deleted")

    st.divider()
    st.subheader("🧰 Utilities")
    if st.button("Reset (clear all)", type="secondary"):
        reset_defaults(session)
        (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())

    exported = export_items_groups(session)
    st.download_button("⬇️ Export JSON", exported, file_name="roadmap.json", mime="application/json")

    uploaded = st.file_uploader("Import JSON", type=["json"])
    if uploaded:
        payload = json.loads(uploaded.read().decode("utf-8"))
        session["items"] = [state.normalize_item(x) for x in payload.get("items", [])]
        session["groups"] = [state.normalize_group(x) for x in payload.get("groups", [])]
        st.success("Imported.")
        (st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.rerun())

# 7) Main area with a very safe timeline render (purely visual)
st.header("Roadmap Timeline")
selected_names = st.multiselect("Filter categories", [g["content"] for g in session["groups"]])
selected_ids = {g["id"] for g in session["groups"] if g["content"] in selected_names} if selected_names else set()
items_view  = [i for i in session["items"]  if not selected_ids or i.get("group","") in selected_ids]
groups_view = [g for g in session["groups"] if not selected_ids or g["id"] in selected_ids]

if not items_view:
    st.markdown('<div class="empty"><b>No items yet.</b><br/>Use the sidebar to add your first event 👈</div>', unsafe_allow_html=True)
else:
    # timeline.render_timeline uses vis-timeline CDN; even if the CDN stalls,
    # you will still see the page and sidebar since we already rendered above.
    timeline.render_timeline(items_view, groups_view, selected_id="")