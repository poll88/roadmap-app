import json
from datetime import date, datetime, timedelta

def _coerce_date(d):
    if isinstance(d, date):
        return d
    if isinstance(d, str) and d:
        return datetime.fromisoformat(d[:10]).date()
    return date.today()

def ensure_range(start: date, end: date):
    start = _coerce_date(start); end = _coerce_date(end)
    if end < start:
        start, end = end, start
    if end == start:
        end = start + timedelta(days=1)
    return start, end

def normalize_item(raw):
    """Return a vis-timeline compatible item dict."""
    out = dict(raw)
    out["id"] = str(out.get("id") or out.get("_id") or out.get("content","") + str(out.get("start","")))
    out["content"] = out.get("content","").strip()
    out["subtitle"] = out.get("subtitle","").strip()
    out["start"] = _coerce_date(out.get("start"))
    out["end"]   = _coerce_date(out.get("end"))
    out["type"] = "range"
    # Style/color
    color = out.get("color")
    if color:
        out["style"] = f"background:{color}; border-color:{color}"
    return out

def normalize_group(raw):
    out = dict(raw)
    out["id"] = str(out.get("id") or out.get("content",""))
    out["content"] = out.get("content","").strip()
    out["order"] = out.get("order", 0)
    return out

def normalize_state(state):
    state["items"] = [normalize_item(x) for x in state.get("items",[])]
    state["groups"] = [normalize_group(x) for x in state.get("groups",[])]

def reset_defaults(state):
    state["items"] = []
    state["groups"] = []
    state["active_group_id"] = ""
    state["editing_item_id"] = ""

def export_items_groups(state) -> str:
    payload = {
        "items": [
            {
                "id": it.get("id"),
                "content": it.get("content",""),
                "subtitle": it.get("subtitle",""),
                "start": it.get("start").isoformat() if isinstance(it.get("start"), date) else str(it.get("start")),
                "end":   it.get("end").isoformat()   if isinstance(it.get("end"), date)   else str(it.get("end")),
                "group": it.get("group",""),
                "color": it.get("color","") or _extract_color_from_style(it.get("style","")),
            } for it in state.get("items",[])
        ],
        "groups": state.get("groups",[])
    }
    return json.dumps(payload, indent=2)

def _extract_color_from_style(style: str) -> str:
    if not style: return ""
    # parse background: #xxxxxx;
    import re
    m = re.search(r'background:\s*([^;]+)', style)
    return (m.group(1).strip() if m else "")