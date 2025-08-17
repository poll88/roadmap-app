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

def _item_label(it, groups_by_id):
    gname = groups_by_id.get(it.get("group",""), "")
    title = it.get("content","(untitled)")
    start = str(it.get("start",""))[:10]
    return f"{title} · {gname} · {start}"

def render_sidebar(state, ensure_range, export_items_groups):
    from lib.state import normalize_item, normalize_group

    actions = {}
    with st.sidebar:
        st.header("📅 Add / Edit")

        # --- Category management (+ active category) ---
        group_names = {g["content"]: g["id"] for g in state["groups"]}
        new_group_name = st.text_input("Category", placeholder="e.g., Germany · Residential")

        if new_group_name and new_group_name in group_names:
            state["active_group_id"] = group_names[new_group_name]
        if new_group_name and new_group_name not in group_names:
            g = normalize_group({"content": new_group_name, "order": len(state["groups"])})
            state["groups"].append(g)
            group_names[new_group_name] = g["id"]
            state["active_group_id"] = g["id"]

        active_name = next((g["content"] for g in state["groups"]
                            if g["id"] == state.get("active_group_id","")), "(none)")
        st.caption(f"Active category: **{active_name or '(none)'}**")

        # --- Reliable item picker (drives selection; mobile friendly) ---
        groups_by_id = {g["id"]: g["content"] for g in state["groups"]}
        options = []
        index = 0
        selected_idx = None
        for it in state["items"]:
            if it.get("type") == "background":
                continue
            options.append((it["id"], _item_label(it, groups_by_id)))
        if options:
            current_id = state.get("editing_item_id","")
            # figure current index
            for i,(iid,_) in enumerate(options):
                if str(iid) == str(current_id):
                    selected_idx = i
                    break

            choice = st.selectbox(
                "Select existing item",
                options=[lbl for _,lbl in options],
                index=selected_idx if selected_idx is not None else 0,
                key="picker_select",
            )
            # When user picks, sync editing_item_id + prefill form
            pick_id = None
            for iid, lbl in options:
                if lbl == choice:
                    pick_id = iid
                    break
            if pick_id and str(pick_id) != str(state.get("editing_item_id","")):
                state["editing_item_id"] = str(pick_id)
                # prefill form from picked item
                picked = next((x for x in state["items"] if str(x.get("id")) == str(pick_id)), None)
                if picked:
                    from lib.ids import _iso_to_date  # internal helper
                    state["form_title"] = picked.get("content","")
                    state["form_subtitle"] = picked.get("subtitle","")
                    state["form_start"] = _iso_to_date(picked.get("start",""))
                    state["form_end"]   = _iso_to_date(picked.get("end",""))
                    if picked.get("group"):
                        state["active_group_id"] = picked.get("group")
                    # try match color label
                    hexcol = picked.get("color","")
                    for label, hexcode in PALETTE_MAP.items():
                        if hexcode == hexcol:
                            state["form_color_label"] = label
                            break

            # Show current selection
            st.caption(f"Selected: **{choice}**")
        else:
            st.caption("Selected: *(none)*")

        # --- Form (keeps focus; no rerun on each keystroke) ---
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

        # -------- Actions (perform now; orchestrator triggers rerun) --------
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
                st.warning("Select an item to edit (picker above).")
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
                st.warning("Select an item to delete (picker above).")
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
            st.rerun()

    return actions