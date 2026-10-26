import re
import xml.etree.ElementTree as ET

MASK = "[MASKED]"


def _norm(s: str) -> str:
    return (s or "").lower().replace("ş", "s").replace("ı", "i")


def is_sensitive_element(element: dict, keywords) -> bool:
    if not element:
        return False
    if element.get("password"):
        return True
    hay = " ".join(_norm(element.get(k) or "") for k in ("resourceId", "contentDesc", "hint", "accessibilityId"))
    return any(_norm(k) and _norm(k) in hay for k in keywords)


def looks_like_otp(value: str) -> bool:
    return bool(value) and bool(re.fullmatch(r"\d{4,8}", value.strip()))


def mask_event(event: dict, keywords) -> dict:
    """Defence-in-depth: the agent/companion masks first; the backend re-applies masking."""
    element = event.get("element") or None
    sensitive = is_sensitive_element(element, keywords)
    inp = event.get("inputValue")
    if inp and inp.get("value") is not None:
        val = inp["value"]
        if sensitive or looks_like_otp(val):
            event["inputValue"] = {"masked": True, "value": None, "length": len(val),
                                   "reason": "SENSITIVE_FIELD" if sensitive else "OTP_PATTERN"}
    if element and sensitive and element.get("text"):
        element["text"] = MASK
    return event


def mask_hierarchy_xml(xml_text: str, keywords) -> str:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return xml_text
    for node in root.iter("node"):
        el = {"password": node.get("password") == "true", "resourceId": node.get("resource-id"),
              "contentDesc": node.get("content-desc"), "hint": node.get("hint")}
        if is_sensitive_element(el, keywords) and node.get("text"):
            node.set("text", MASK)
    return ET.tostring(root, encoding="unicode")
