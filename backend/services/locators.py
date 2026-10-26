"""Phase 1 basic locator extraction. Phase 2 Locator Engine will add scoring/validation on device."""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional


def _count(root, attr: str, value: str) -> Optional[int]:
    if root is None:
        return None
    return sum(1 for n in root.iter("node") if n.get(attr) == value)


def _candidate(strategy, value, confidence, root, attr=None, attr_value=None):
    count = _count(root, attr, attr_value) if attr else None
    unique = None if count is None else count == 1
    if unique is False:
        confidence = round(confidence * 0.5, 2)
    return {"strategy": strategy, "value": value, "confidence": confidence,
            "uniqueness": {"checked": count is not None, "matchCount": count, "unique": unique},
            "validatedAt": datetime.now(timezone.utc).isoformat() if count is not None else None,
            "validationSource": "HIERARCHY_SNAPSHOT" if count is not None else None}


def extract_locators(element: Optional[dict], coordinates: Optional[dict], xml_text: Optional[str]) -> List[dict]:
    root = None
    if xml_text:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            root = None
    out = []
    el = element or {}
    if el.get("contentDesc") and el.get("contentDesc") != "[MASKED]":
        out.append(_candidate("ACCESSIBILITY_ID", el["contentDesc"], 0.9, root, "content-desc", el["contentDesc"]))
    if el.get("resourceId"):
        out.append(_candidate("RESOURCE_ID", el["resourceId"], 0.85, root, "resource-id", el["resourceId"]))
    if el.get("text") and el.get("text") != "[MASKED]":
        sel = f'new UiSelector().text("{el["text"]}")'
        if el.get("className"):
            sel = f'new UiSelector().className("{el["className"]}").text("{el["text"]}")'
        out.append(_candidate("UIAUTOMATOR", sel, 0.6, root, "text", el["text"]))
        if el.get("className"):
            out.append(_candidate("XPATH", f'//{el["className"]}[@text="{el["text"]}"]', 0.4, root, "text", el["text"]))
    if coordinates and coordinates.get("x") is not None:
        out.append({"strategy": "COORDINATES", "value": f'{coordinates["x"]},{coordinates["y"]}', "confidence": 0.1,
                    "uniqueness": {"checked": False, "matchCount": None, "unique": None},
                    "validatedAt": None, "validationSource": None})
    out.sort(key=lambda c: c["confidence"], reverse=True)
    return out
