import uuid
from datetime import date, datetime

def _iso_to_date(s: str) -> date:
    if not s:
        return date.today()
    return datetime.fromisoformat(s[:10]).date()

def ensure_stable_ids(state) -> bool:
    """
    Ensure every item/group has a stable string id. Returns True if mutated.
    """
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