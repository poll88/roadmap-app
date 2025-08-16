import uuid
from datetime import date, datetime

def _iso_to_date(s: str) -> date:
    if not s:
        return date.today()
    return datetime.fromisoformat(s[:10]).date()

def ensure_stable_ids(state) -> bool:
    """Ensure every item/group has a stable string id. Returns True if mutated."""
    changed = False
    for it in state.get("items", []):
        if not it.get("id"):
            it["id"] = str(uuid.uuid4())
            changed = True
        else:
            it["id"] = str(it["id"])
    for g in state.get("groups", []):
        if not g.get("id"):
            g["id"] = str(uuid.uuid4())
            changed = True
        else:
            g["id"] = str(g["id"])
    return changed

def prefill_from_item_id(state, item_id: str) -> bool:
    """Prefill sidebar form + active category from item id."""
    for it in state.get("items", []):
        if str(it.get("id")) == str(item_id):
            state["editing_item_id"] = str(item_id)
            state.setdefault("form_title", "")
            state.setdefault("form_subtitle", "")
            state.setdefault("form_start", date.today())
            state.setdefault("form_end", date.today())
            state["form_title"] = it.get("content", "")
            state["form_subtitle"] = it.get("subtitle", "")
            state["form_start"] = _iso_to_date(it.get("start", ""))
            state["form_end"]   = _iso_to_date(it.get("end", ""))
            gid = str(it.get("group", ""))
            if gid:
                state["active_group_id"] = gid
            # color label best effort (if you kept HEX_TO_LABEL in ui)
            color_hex = it.get("color", "")
            # optional: leave existing selection if unknown
            return True
    return False

def get_selected_item(state):
    eid = state.get("editing_item_id", "")
    for it in state.get("items", []):
        if str(it.get("id")) == str(eid):
            return it
    return None