"""Unit and Quantity Normalization Module.

Parses raw quantity strings into normalized numeric values and base units.
Handles Indian numbering (lakh = 1e5, crore = 1e7), Western numbering (thousand, million, billion),
currency symbols (₹, Rs., $, €), percentages, and unit conversions.
"""

import re
from typing import Dict, Any, Optional


def parse_quantity(raw_str: str, default_unit: Optional[str] = None) -> Dict[str, Any]:
    """Parse raw string into normalized quantity object.

    Example inputs & outputs:
    - "Rs. 1,234.5 crore" -> {"value": 12345000000.0, "unit": "INR", "raw": "Rs. 1,234.5 crore"}
    - "15 lakh" -> {"value": 1500000.0, "unit": "count", "raw": "15 lakh"}
    - "USD 2.3 million" -> {"value": 2300000.0, "unit": "USD", "raw": "USD 2.3 million"}
    - "12.5%" -> {"value": 12.5, "unit": "percent", "raw": "12.5%"}
    """
    if not raw_str:
        return {"value": None, "unit": default_unit or "unknown", "raw": str(raw_str)}

    text = str(raw_str).strip()

    # 1. Check percentage
    if "%" in text or "percent" in text.lower():
        num_match = re.search(r"[-+]?\d[\d,]*\.?\d*", text)
        if num_match:
            val_str = num_match.group().replace(",", "")
            try:
                return {"value": float(val_str), "unit": "percent", "raw": text}
            except ValueError:
                pass

    # 2. Identify currency/unit
    unit = default_unit
    text_lower = text.lower()

    if "inr" in text_lower or "rs" in text_lower or "₹" in text or "rupee" in text_lower:
        unit = "INR"
    elif "usd" in text_lower or "$" in text or "dollar" in text_lower:
        unit = "USD"
    elif "eur" in text_lower or "€" in text or "euro" in text_lower:
        unit = "EUR"
    elif "gbp" in text_lower or "£" in text or "pound" in text_lower:
        unit = "GBP"

    # 3. Extract multiplier
    multiplier = 1.0
    if "crore" in text_lower or " cr" in text_lower or text_lower.endswith("cr"):
        multiplier = 1e7
    elif "lakh" in text_lower or " lac" in text_lower or text_lower.endswith("l"):
        multiplier = 1e5
    elif "trillion" in text_lower:
        multiplier = 1e12
    elif "billion" in text_lower or text_lower.endswith("b"):
        multiplier = 1e9
    elif "million" in text_lower or text_lower.endswith("m"):
        multiplier = 1e6
    elif "thousand" in text_lower or text_lower.endswith("k"):
        multiplier = 1e3

    # 4. Extract numeric substring
    num_match = re.search(r"[-+]?\d[\d,]*\.?\d*", text)
    if not num_match:
        return {"value": None, "unit": unit or "unknown", "raw": text}

    cleaned_num_str = num_match.group().replace(",", "")

    try:
        base_val = float(cleaned_num_str)
        final_val = base_val * multiplier
        return {
            "value": round(final_val, 4),
            "unit": unit or "count",
            "raw": text,
        }
    except ValueError:
        return {"value": None, "unit": unit or "unknown", "raw": text}
