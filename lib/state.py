import json, uuid
from datetime import date, timedelta, datetime
from typing import Any, Dict, List, Tuple

def iso(x: Any) -> str:
    if isinstance(x, (date, datetime)): return x.date().isoformat() if isinstance(x, datetime) else x.isoformat()
    if isinstance(x, str): return x[:10]
    return ""

def _coerce_date(s: Any) -> date:
    if isinstance(s, date): return s
    if isinstance(s, str) and s: return date.fromisoformat(s[:10])
    return date.today()

def normalize_item(it: Any) -> Dict[str, Any]:
    it = it or {}
    s = _coerce_date(it.get("start"))
    e = _coerce_date(it.get("end"))
    s, e = ensure_range(s, e)
    return {
        "id": str(it.get("id") or uuid.uuid4()),
        "content": str(it.get("content", "")).strip(),
        "subtitle": str(it.get("subtitle", "")).strip(),
        "status": str(it.get("status", "")).strip(),
        "start": iso(s),
        "end": iso(e),
        "group": str(it.get("group", "")),
        "className": str(it.get("className", "")),
        "style": str(it.get("style", "")),
        "title": str(it.get("title", "")),
        "color": str(it.get("color", "#2563eb")),
        "type": "range",
    }

def normalize_group(g: Any) -> Dict[str, Any]:
    g = g or {}
    return {
        "id": str(g.get("id") or uuid.uuid4()),
        "content": str(g.get("content", "")).strip() or "Group",
        "order": int(g.get("order", 0)),
    }

def normalize_state(state):
    state.setdefault("items", [])
    state.setdefault("groups", [])
    state["items"] = [normalize_item(x) for x in state["items"]]
    state["groups"] = [normalize_group(x) for x in state["groups"]]

def reset_defaults(state):
    state["items"] = []
    state["groups"] = []

def ensure_range(start: date, end: date) -> Tuple[date, date]:
    if end < start: start, end = end, start
    if end == start: end = start + timedelta(days=1)
    return start, end

def export_items_groups(state) -> str:
    payload = {"items": state.get("items", []), "groups": state.get("groups", [])}
    return json.dumps(payload, indent=2, ensure_ascii=False)
