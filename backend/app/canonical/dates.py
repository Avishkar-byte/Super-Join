"""Date and Period Normalization Module.

Resolves strings like FY24, Q3 FY24, year ended March 31, 2024, as at 31.03.2024
into ISO interval objects {start, end}.
Includes set-operation overlap checking for reconciliation.
"""

import re
from typing import Dict, Any, Optional


def parse_date_interval(raw_str: str) -> Dict[str, Any]:
    """Parse date or fiscal year expression into ISO interval {start, end}.

    Returns:
    {
        "start": "YYYY-MM-DD",
        "end": "YYYY-MM-DD",
        "label": raw_str,
        "fy_convention_assumed": bool
    }
    """
    if not raw_str:
        return {"start": None, "end": None, "label": "", "fy_convention_assumed": False}

    text = str(raw_str).strip()
    text_lower = text.lower()

    # 1. Check Quarters FIRST (e.g., Q1, Q2, Q3, Q4 with year like Q3 FY24, Q3 2024)
    q_match = re.search(r"q([1-4])\s*(?:fy)?\s*(\d{2,4})", text_lower)
    if q_match:
        q_num = int(q_match.group(1))
        y = int(q_match.group(2))
        end_year = 2000 + y if y < 100 else y
        if q_num == 1:
            start, end = f"{end_year-1}-04-01", f"{end_year-1}-06-30"
        elif q_num == 2:
            start, end = f"{end_year-1}-07-01", f"{end_year-1}-09-30"
        elif q_num == 3:
            start, end = f"{end_year-1}-10-01", f"{end_year-1}-12-31"
        else:
            start, end = f"{end_year}-01-01", f"{end_year}-03-31"
        return {
            "start": start,
            "end": end,
            "label": text,
            "fy_convention_assumed": True,
        }

    # 2. FY24 / FY2024 / FY2023-24 / FY 2023-2024
    fy_match = re.search(r"fy\s*(\d{2,4})(?:[-/](\d{2,4}))?", text_lower)
    if fy_match:
        g1 = int(fy_match.group(1))
        g2 = fy_match.group(2)

        if g2:
            y2 = int(g2)
            end_year = 2000 + y2 if y2 < 100 else y2
        else:
            end_year = 2000 + g1 if g1 < 100 else g1

        start_year = end_year - 1
        return {
            "start": f"{start_year}-04-01",
            "end": f"{end_year}-03-31",
            "label": text,
            "fy_convention_assumed": True,
        }

    # 3. Year ended March 31, 2024 / Year ended 31.03.2024
    if "year ended" in text_lower or "ended march 31" in text_lower or "ended 31.03" in text_lower:
        year_match = re.search(r"20\d{2}", text)
        if year_match:
            end_year = int(year_match.group())
            return {
                "start": f"{end_year-1}-04-01",
                "end": f"{end_year}-03-31",
                "label": text,
                "fy_convention_assumed": True,
            }

    # 4. Point-in-time date (e.g. as at 31.03.2024, March 31, 2024, 2024-03-31)
    iso_match = re.search(r"(20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])", text)
    if iso_match:
        y, m, d = iso_match.groups()
        date_str = f"{y}-{m}-{d}"
        return {
            "start": date_str,
            "end": date_str,
            "label": text,
            "fy_convention_assumed": False,
        }

    dmy_match = re.search(r"(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](20\d{2})", text)
    if dmy_match:
        d, m, y = dmy_match.groups()
        date_str = f"{y}-{m}-{d}"
        return {
            "start": date_str,
            "end": date_str,
            "label": text,
            "fy_convention_assumed": False,
        }

    return {"start": None, "end": None, "label": text, "fy_convention_assumed": False}


def are_intervals_disjoint(int_a: Dict[str, Any], int_b: Dict[str, Any]) -> bool:
    """Check if two ISO interval dicts are strictly disjoint (no date overlap)."""
    s_a, e_a = int_a.get("start"), int_a.get("end")
    s_b, e_b = int_b.get("start"), int_b.get("end")

    if not (s_a and e_a and s_b and e_b):
        return False  # Cannot prove disjointness if bounds are missing

    return (e_a < s_b) or (e_b < s_a)
