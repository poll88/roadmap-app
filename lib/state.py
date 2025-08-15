# lib/state.py
from datetime import date, timedelta

def _coerce_date_any(x) -> date:
    if x is None:
        return date.today()
    if isinstance(x, date):
        return x
    if isinstance(x, str) and x:
        return date.fromisoformat(x[:10])
    return date.today()

def ensure_range(start: date, end: date):
    start = _coerce_date_any(start)
    end   = _coerce_date_any(end)
    if end < start:
        start, end = end, start
    if end == start:
        end = start + timedelta(days=1)
    return start, end
