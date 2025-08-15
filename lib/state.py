import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

# ---------- helpers ----------
def _iso(x: Any) -> str:
    """Return YYYY-MM-DD for date/datetime/string, else empty string."""
    if isinstance(x, datetime):
        return x.date().isoformat()
    if isinstance(x, date):
        return x.isoformat()
    if isinstance(x, str):
        return x[:10]
    return ""

def _coerce_date_any(x: Any) -> date:
    """Coerce None/str/date/datetime into date (defaults to today)."""
    if x is None:
        return date.today()
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    if isinstance(x, str) and x:
        return date.fromisoformat(x[:10])
    return date.today()

# ---------- core API used by app.py ----------
def normalize_item(it: Any) -> Dict[str, Any]:
    """Ensure an item has all required fields and valid dates."""
    it = it or {}
    s = _coerce_date_any(it.get("start"))
    e = _coerce_date_any(it.get("end"))
    s, e = ensure_range(s, e)

    color = str(it.get("color") or "#E9D5FF")
    style = str(it.get("style") or f"background:{color}; border-color:{color}")

    return {
        "id": str(it.get("id") or uuid.uuid4()),
        "content": str(it.get("content", "")).strip(),
        "subtitle": str(it.get("subtitle", "")).strip(),
        "start": _iso(s),
        "end": _iso(e),
        "group": str(it.get("group", "")).strip(),
        "color": color,
        "style": style,
        "type": "range",
        # NOTE: no 'status' field anymore by design
    }

def normalize_group(g: Any) -> Dict[str, Any]:
    """Ensure a group (category) has id/content/order."""
    g = g or {}
    return {
        "id": str(g.get("id") or uuid.uuid4()),
        "content": (str(g.get("content") or "Group")).strip(),
        "order": int(g.get("order", 0)),
    }

def normalize_state(state: Dict[str, Any]) -> None:
    """Normalize items and groups inside session_state dict."""
    state.setdefault("items", [])
    state.setdefault("groups", [])
    state["items"] = [normalize_item(x) for x in state["items"]]
    state["groups"] = [normalize_group(x) for x in state["groups"]]

def reset_defaults(state: Dict[str, Any]) -> None:
    state["items"] = []
    state["groups"] = []

def ensure_range(start: date, end: date) -> Tuple[date, date]:
    """Return (start,end) with end>=start and min 1-day length."""
    start = _coerce_date_any(start)
    end   = _coerce_date_any(end)
    if end < start:
        start, end = end, start
    if end == start:
        end = start + timedelta(days=1)
    return start, end

def export_items_groups(state: Dict[str, Any]) -> str:
    """Pretty JSON export of current items/groups."""
    payload = {
        "items": state.get("items", []),
        "groups": state.get("groups", []),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
