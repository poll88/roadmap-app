import json
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

def iso(x: Any) -> str:
    return x.isoformat() if hasattr(x, "isoformat") else str(x or "")

def normalize_item(it: Any) -> Dict[str, Any]:
    if not isinstance(it, dict): it = {}
    return {
        "id": str(it.get("id") or uuid.uuid4()),
        "content": str(it.get("content", "")),
        "subtitle": str(it.get("subtitle", "")),
        "status": str(it.get("status","")),
        "start": iso(it.get("start","")),
        "end": iso(it.get("end","")),
        "group": str(it.get("group","")),
        "title": str(it.get("title","")),
        "color": str(it.get("color","#5ac8fa")),
        "style": str(it.get("style","")),
    }

def normalize_group(g: Any) -> Dict[str, Any]:
    if not isinstance(g, dict): g = {}
    gid = g.get("id") or g.get("content") or ""
    return {"id": str(gid), "content": str(g.get("content", gid)), "laneColor": str(g.get("laneColor","rgba(37,99,235,.06)"))}

def _as_list(x: Any) -> List[Any]:
    if isinstance(x, list): return x
    return []

def normalize_state(items_any: Any, groups_any: Any):
    items = [normalize_item(i) for i in _as_list(items_any)]
    groups = [normalize_group(g) for g in _as_list(groups_any)]
    return items, groups

def reset_defaults(state):
    state["items"] = []
    state["groups"] = []

def ensure_range(start: date, end: date) -> Tuple[date, date]:
    """Avoid point items: if same day, make end = start + 1 day."""
    if end < start:
        start, end = end, start
    if end == start:
        end = start + timedelta(days=1)
    return start, end

def export_items_groups(state) -> str:
    payload = {"items": state.get("items", []), "groups": state.get("groups", [])}
    return json.dumps(payload, indent=2, default=str)
