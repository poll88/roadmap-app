from datetime import date
import streamlit as st

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

def _ensure_form_defaults(state):
    state.setdefault("form_title", "")
    state.setdefault("form_subtitle", "")
    state.setdefault("form_start", date.today())
    state.setdefault("form_end", date.today())
    state.setdefault("form_color_label", PALETTE_OPTIONS[0])

def render_sidebar(state, *, normalize_item, ensure_range, export_items_groups):
    actions = {}

    with st.sidebar:
        st.header("📅 Add / Edit")

        # Category management (+ active category)
        group_names = {g["content"]: g["id"] for g in state["groups"]}
        new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")

        if new_group_name and new_group_name in group_names:
            state["active_group_id"] = group_names[new_group_name]
        if new_group_name and new_group_name not in group_names:
            g = {"content": new_group_name, "order": len(state["groups"])}
            from lib.state import normalize_group
            g = normalize_group(g)
            state["groups"].append(g)
            group_names[new_group_name] = g["id"]
            state["active_group_id"] = g["id"]

        active_name = next((g["content"] for g in state["groups"]
                            if g["id"] == state.get("active_group_id","")), "(none)")
        st.caption(f"Active category: **{active_name or '(none)'}**")

        # Show current selection for clarity
        sel_id = state.get("editing_item_id","")
        if sel_id:
            title = next((i.get("content","(untitled)") for i in state["items"] if str(i.get("id"))==str(sel_id)), "(untitled)")
            st.caption(f"Selected: **{title}** · id `{str(sel_id)[:8]}`")
        else:
            st.caption("Selected: *(none)*")

        # One form (prevents reruns on each keystroke)
        _ensure_form_defaults(state)
        with st.form("item_form", clear_on_submit=False):
            colA, colB = st.columns(2)
            start = colA.date_input("Start", key="form_start")
            end   = colB.date_input("End",   key="form_end")
            start, end = ensure_range(start, end)

            st.text_input("Title",               key="form_title",    placeholder="Item title")
            st.text_input("Subtitle (optional)", key="form_subtitle", placeholder="Short note")

            st.selectbox("Bar color", PALETTE_OPTIONS, key="form_color_label")

            col1, col2, col3 = st.columns(3)
            add_clicked    = col1.form_submit_button("➕ Add item")
            edit_clicked   = col2.form_submit_button("✏️ Edit item")
            delete_clicked = col3.form_submit_button("🗑 Delete item")

        # -------- Actions (set flags/perform) --------
        if add_clicked:
            color_hex = PALETTE_MAP[state["form_color_label"]]
            gid = state.get("active_group_id","")
            item = normalize_item({
                "content": state["form_title"],
                "subtitle": state["form_subtitle"],
                "start": state["form_start"],
                "end": state["form_end"],
                "group": gid,
                "color": color_hex,
                "style": f"background:{color_hex}; border-color:{color_hex}",
            })
            state["items"].append(item)
            state["editing_item_id"] = item["id"]
            actions["add"] = True

        if edit_clicked:
            eid = state.get("editing_item_id","")
            if not eid:
                st.warning("Select an item on the timeline to edit.")
            else:
                color_hex = PALETTE_MAP[state["form_color_label"]]
                for idx, it in enumerate(state["items"]):
                    if str(it.get("id")) == str(eid):
                        updated = normalize_item({
                            "id": eid,
                            "content": state["form_title"],
                            "subtitle": state["form_subtitle"],
                            "start": state["form_start"],
                            "end": state["form_end"],
                            "group": state.get("active_group_id", it.get("group","")),
                            "color": color_hex,
                            "style": f"background:{color_hex}; border-color:{color_hex}",
                        })
                        state["items"][idx] = updated
                        actions["edit"] = True
                        break

        if delete_clicked:
            eid = state.get("editing_item_id","")
            if not eid:
                st.warning("Select an item on the timeline to delete.")
            else:
                actions["delete"] = eid

        st.divider()
        st.subheader("🧰 Utilities")
        if st.button("Reset (clear all)", type="secondary"):
            actions["reset"] = True

        exported = export_items_groups(state)
        st.download_button("⬇️ Export JSON", data=exported, file_name="roadmap.json", mime="application/json")

        uploaded = st.file_uploader("Import JSON", type=["json"])
        if uploaded:
            import json
            payload = json.loads(uploaded.read().decode("utf-8"))
            from lib.state import normalize_item as _norm_item, normalize_group as _norm_group
            state["items"] = [_norm_item(x) for x in payload.get("items", [])]
            state["groups"] = [_norm_group(x) for x in payload.get("groups", [])]
            state["active_group_id"] = (state["groups"][-1]["id"] if state["groups"] else "")
            state["editing_item_id"] = ""
            st.success("Imported.")
            actions["reset"] = False  # no reset, but we will rerun externally
            st.rerun()

    return actions