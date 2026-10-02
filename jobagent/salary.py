"""Best-effort AED salary parsing (monthly). Anything else is reported as unknown."""
import re

_NUM = r"(\d[\d,]*(?:\.\d+)?)\s*(k)?"


def _val(num: str, k: str | None) -> float:
    v = float(num.replace(",", ""))
    return v * 1000 if k else v


def parse_aed_monthly(text: str):
    """Return (low, high) in AED/month, or None if not parseable / not AED / not monthly."""
    t = (text or "").lower()
    if not t or "aed" not in t and "dhs" not in t and "dirham" not in t:
        return None
    if re.search(r"per (year|annum)|annual|/\s*(yr|year)|\bpa\b", t):
        m = re.findall(_NUM, t)
        vals = [_val(a, b) / 12 for a, b in m if _val(a, b) >= 50000]
        return (min(vals), max(vals)) if vals else None
    m = re.findall(_NUM, t)
    vals = [_val(a, b) for a, b in m if 2000 <= _val(a, b) <= 200000]
    if not vals:
        return None
    return (min(vals), max(vals))
