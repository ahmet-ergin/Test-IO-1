"""Turns a session export (build_export) into a reviewable code-generation plan."""
from services.export_service import build_export
from services.codegen.config import CodegenConfig, resolve
from services.codegen.javautil import gauge_text, pascal, const, java_str

SUPPORTED_ACTIONS = {"TAP", "LONG_PRESS", "SCROLL"}
BY_METHOD = {"RESOURCE_ID": "id", "ACCESSIBILITY_ID": "accessibilityId", "UIAUTOMATOR": "androidUIAutomator",
             "XPATH": "xpath"}
DIR_TR = {"DOWN": "aşağı", "UP": "yukarı", "LEFT": "sola", "RIGHT": "sağa"}
MASK = "[MASKED]"


def by_expr(loc: dict, ascii_only: bool) -> str:
    return f'AppiumBy.{BY_METHOD[loc["strategy"]]}({java_str(loc["value"], ascii_only)})'


def _point(value: str):
    try:
        x, y = (int(float(p)) for p in str(value).split(","))
        return {"x": x, "y": y}
    except (ValueError, TypeError):
        return None


def _sensitive(ev: dict) -> bool:
    el = ev.get("element") or {}
    iv = ev.get("inputValue") or {}
    return bool(el.get("password") or el.get("text") == MASK or iv.get("masked"))


def _label(ev: dict, sensitive: bool, order: int) -> str:
    el = ev.get("element") or {}
    rid = (el.get("resourceId") or "").split("/")[-1]
    cls = (el.get("className") or "").split(".")[-1]
    typed = ev.get("action") == "INPUT_TEXT"
    cands = [rid, cls] if sensitive else [None if typed else el.get("text"), el.get("contentDesc"), el.get("hint"), rid, cls]
    for c in cands:
        t = gauge_text(c or "", 40)
        if t and t != "MASKED":
            return t
    return f"öğe {order}"


def _loc_view(loc: dict, cfg) -> dict:
    s = loc.get("strategy")
    u = (loc.get("uniqueness") or {})
    v = {"strategy": s, "value": loc.get("value"), "confidence": loc.get("confidence"),
         "unique": u.get("unique"), "matchCount": u.get("matchCount"), "javaExpr": None, "usable": False}
    if s in BY_METHOD:
        v.update(javaExpr=by_expr(loc, cfg.asciiOnly), usable=True)
    elif s == "COORDINATES" and _point(loc.get("value")):
        p = _point(loc["value"])
        v.update(javaExpr=f'{p["x"]}, {p["y"]}', usable=True, point=p)
    return v


def _scroll_direction(ev: dict):
    a, b = ev.get("coordinates") or {}, ev.get("endCoordinates") or {}
    if None in (a.get("x"), a.get("y"), b.get("x"), b.get("y")):
        return None
    dx, dy = b["x"] - a["x"], b["y"] - a["y"]
    if abs(dy) >= abs(dx):
        return "DOWN" if dy < 0 else "UP"
    return "RIGHT" if dx < 0 else "LEFT"


def _issue(level, code, message):
    return {"level": level, "code": code, "message": message}


def plan_step(st: dict, ev: dict, n: int, cfg) -> dict:
    action = st.get("action") or ev.get("action") or "UNKNOWN"
    sensitive = _sensitive(ev)
    label = _label(ev, sensitive, n)
    issues = []
    raw = ([st["selectedLocator"]] if st.get("selectedLocator") else []) + (st.get("alternativeLocators") or [])
    locs = []
    for loc in raw:
        if MASK in str(loc.get("value")):
            issues.append(_issue("info", "MASKED_LOCATOR_REMOVED", f"{loc.get('strategy')} locator'ı maskelenmiş veri içerdiği için kullanılmadı."))
            continue
        locs.append(_loc_view(loc, cfg))
    selected = None
    if st.get("selectedLocator") and locs and locs[0]["strategy"] == st["selectedLocator"].get("strategy") and locs[0]["usable"]:
        selected = locs[0]
    elif action in SUPPORTED_ACTIONS:
        fallback = sorted([x for x in locs if x["usable"] and x["strategy"] != "COORDINATES"],
                          key=lambda x: -(x["confidence"] or 0)) or [x for x in locs if x["usable"]]
        if fallback:
            selected = fallback[0]
            issues.append(_issue("warning", "SELECTED_LOCATOR_UNUSABLE",
                                 f"Seçili locator kullanılamadı; en yüksek güvenli alternatif ({selected['strategy']}) kullanıldı."))
    alternatives = [x for x in locs if x is not selected]
    p = {"order": n, "stepId": st["stepId"], "name": st.get("name"), "action": action, "label": label,
         "sensitive": sensitive, "selected": selected, "alternatives": alternatives, "supported": action in SUPPORTED_ACTIONS,
         "params": [], "holdMs": None, "direction": None}
    if p["supported"] and not selected:
        p["supported"] = False
        issues.append(_issue("error", "NO_LOCATOR", "Kullanılabilir locator yok; adım elle uygulanmalı."))
    if not p["supported"] and action not in SUPPORTED_ACTIONS:
        issues.append(_issue("error", "UNSUPPORTED_ACTION",
                             f"{action} aksiyonu kod üreteci tarafından desteklenmiyor (desteklenen: TAP, SCROLL, LONG_PRESS). "
                             "Adım üretildi ancak çalıştığında UnsupportedOperationException fırlatır."))
    if selected and selected["strategy"] == "COORDINATES":
        issues.append(_issue("warning", "COORDINATE_LOCATOR", "Koordinat tabanlı (W3C Actions); ekran çözünürlüğüne ve yerleşime bağlıdır."))
    if selected and selected.get("unique") is False:
        issues.append(_issue("warning", "AMBIGUOUS_LOCATOR", f"Seçili locator kayıt anında {selected.get('matchCount')} öğe ile eşleşti; "
                             "çalışma anında birden fazla eşleşme olursa yardımcı metot hata verir."))
    if p["supported"] and action == "LONG_PRESS":
        p["holdMs"] = max(600, min(5000, int(ev.get("durationMs") or 1000)))
    if p["supported"] and action == "SCROLL":
        p["direction"] = _scroll_direction(ev)
        if selected["strategy"] == "COORDINATES":
            end = ev.get("endCoordinates") or {}
            if p["direction"] and end.get("x") is not None:
                p["swipe"] = {"from": selected["point"], "to": {"x": end["x"], "y": end["y"]}}
            else:
                p["supported"] = False
                issues.append(_issue("error", "SCROLL_NO_END", "Koordinat ile kaydırma için bitiş noktası kaydedilmemiş."))
        if not p["direction"]:
            p["direction"] = "DOWN"
            issues.append(_issue("warning", "SCROLL_DIRECTION_ASSUMED", "Kaydırma yönü kaydedilmedi; varsayılan AŞAĞI (içerik aşağı) kullanıldı."))
    if action == "INPUT_TEXT":
        iv = ev.get("inputValue") or {}
        if sensitive or iv.get("value") is None:
            key = f"{cfg.secretKeyPrefix}{const(label) or 'VALUE'}"
            p["params"] = [{"name": "veriAnahtari", "specValue": key, "secret": True}]
            issues.append(_issue("info", "SENSITIVE_VALUE", f"Hassas değer koda yazılmadı; test verisi anahtarı '{key}' kullanıldı."))
        else:
            p["params"] = [{"name": "deger", "specValue": gauge_text(iv["value"], 80).replace('"', ""), "secret": False}]
    p["issues"] = issues
    p["status"] = "UNSUPPORTED" if not p["supported"] else ("WARNING" if any(i["level"] == "warning" for i in issues) else "OK")
    p["stepText"], p["methodName"], p["constName"] = _names(p, n, cfg)
    return p


def _names(p: dict, n: int, cfg):
    lbl, pre = p["label"], (cfg.stepPrefix + " " if cfg.stepPrefix else "")
    verb = {"TAP": ("öğesine dokun", "Dokun"), "LONG_PRESS": ("öğesine uzun bas", "UzunBas"),
            "SCROLL": (f"alanında {DIR_TR.get(p['direction'] or 'DOWN')} kaydır", "Kaydir")}
    if p["action"] == "INPUT_TEXT":
        ptxt = "alanına <veriAnahtari> anahtarlı test verisini yaz" if p["params"][0]["secret"] else "alanına <deger> yaz"
        text, mverb = f"{pre}Adım {n} - {lbl} {ptxt}", "Yaz"
    elif p["action"] in verb and p["supported"]:
        text, mverb = f"{pre}Adım {n} - {lbl} {verb[p['action']][0]}", verb[p["action"]][1]
    else:
        text, mverb = f"{pre}Adım {n} - {lbl} {gauge_text(p['action'])} işlemi (desteklenmiyor)", "Desteklenmiyor"
    method = (f"adim{n:02d}" + pascal(lbl) + mverb)[:80]
    cname = (f"ADIM_{n:02d}_" + (const(lbl) or "OGE"))[:80]
    return text, method, cname


async def build_plan(session_id: str, cfg: CodegenConfig) -> dict:
    doc = await build_export(session_id)
    rc = resolve(cfg, doc.get("name") or "Recorded")
    events = {e["eventId"]: e for e in doc["events"]}
    steps = [plan_step(st, events.get(st["eventId"]) or {}, i, rc) for i, st in enumerate(doc["steps"], start=1)]
    summary = {"total": len(steps), "supported": sum(s["supported"] for s in steps),
               "unsupported": sum(not s["supported"] for s in steps),
               "warnings": sum(1 for s in steps for i in s["issues"] if i["level"] == "warning")}
    return {"session": {"id": doc["sessionId"], "name": doc.get("name"), "packageName": doc["application"]["packageName"],
                        "demo": doc["demo"], "status": doc["status"]},
            "config": rc.model_dump(), "steps": steps, "summary": summary}
