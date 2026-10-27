"""Plan for the Cucumber + POM profile: element fields, page methods and Turkish step texts (deduplicated)."""
from services.export_service import build_export
from services.codegen.javautil import java_str, jcamel as camel, jpascal as pascal, jconst as const, is_ident, comment_safe
from services.codegen.planner import _sensitive, _label, _scroll_direction, _issue, MASK
from services.codegen.pom_config import PomConfig, resolve_pom, LOCATOR_STRATEGIES, cucumber_text

ELEMENT_ACTIONS = {"TAP", "INPUT_TEXT", "LONG_PRESS"}
DIR_TR = {"DOWN": "aşağı", "UP": "yukarı", "LEFT": "sola", "RIGHT": "sağa"}


def annotation_for(loc: dict, cfg: PomConfig):
    tpl = getattr(cfg.locatorTemplates, loc["strategy"], "") if loc["strategy"] in LOCATOR_STRATEGIES else ""
    if not tpl:
        return None
    v = loc["value"]
    if loc["strategy"] == "RESOURCE_ID" and cfg.resourceIdFormat == "SHORT":
        v = v.split(":id/")[-1]
    return f"@{cfg.locatorAnnotation.rsplit('.', 1)[-1]}({tpl.replace('{value}', java_str(v, cfg.asciiOnly))})"


def _loc(loc: dict, cfg) -> dict:
    u = loc.get("uniqueness") or {}
    ann = annotation_for(loc, cfg)
    return {"strategy": loc["strategy"], "value": loc["value"], "confidence": loc.get("confidence"), "unique": u.get("unique"),
            "matchCount": u.get("matchCount"), "javaExpr": ann, "usable": ann is not None}


def _choose(st: dict, cfg, issues: list):
    raw = ([st["selectedLocator"]] if st.get("selectedLocator") else []) + (st.get("alternativeLocators") or [])
    locs = []
    for loc in raw:
        if MASK in str(loc.get("value")):
            issues.append(_issue("info", "MASKED_LOCATOR_REMOVED", f"{loc.get('strategy')} locator'ı maskelenmiş veri içerdiği için kullanılmadı."))
        else:
            locs.append(_loc(loc, cfg))
    sel_strategy = (st.get("selectedLocator") or {}).get("strategy")
    if locs and locs[0]["strategy"] == sel_strategy and locs[0]["usable"]:
        return locs[0], locs[1:]
    order = {s: i for i, s in enumerate(LOCATOR_STRATEGIES)}
    usable = sorted([x for x in locs if x["usable"]], key=lambda x: order.get(x["strategy"], 99))
    if not usable:
        return None, locs
    chosen = usable[0]
    issues.append(_issue("warning", "SELECTED_LOCATOR_UNSUPPORTED",
                         f"Seçili locator ({sel_strategy or 'yok'}) yapılandırılan @{cfg.locatorAnnotation.rsplit('.', 1)[-1]} şablonlarıyla "
                         f"ifade edilemiyor; ilk desteklenen alternatif ({chosen['strategy']}) kullanıldı."))
    return chosen, [x for x in locs if x is not chosen]


def _field_name(ev: dict, label: str, taken: set) -> str:
    rid = ((ev.get("element") or {}).get("resourceId") or "").split("/")[-1]
    base = camel(rid) if rid else camel(label)
    base = base if base and is_ident(base) and not base[0].isdigit() else "element" + pascal(label or "x")
    name, i = base, 2
    while name in taken:
        name, i = f"{base}{i}", i + 1
    return name


def build_steps(doc: dict, cfg: PomConfig):
    events = {e["eventId"]: e for e in doc["events"]}
    elements, by_loc, methods, by_key, rows = [], {}, [], {}, []
    texts = {}
    for n, st in enumerate(doc["steps"], start=1):
        ev = events.get(st["eventId"]) or {}
        action = st.get("action") or ev.get("action") or "UNKNOWN"
        sensitive = _sensitive(ev)
        label = _label(ev, sensitive, n)
        issues, selected, alternatives, element, direction = [], None, [], None, None
        template_key = action
        if action not in ("SCROLL", "BACK"):
            selected, alternatives = _choose(st, cfg, issues)
        if action == "SCROLL":
            direction = _scroll_direction(ev)
            if not direction:
                direction = "DOWN"
                issues.append(_issue("warning", "SCROLL_DIRECTION_ASSUMED", "Kaydırma yönü kaydedilmedi; varsayılan AŞAĞI kullanıldı."))
            template_key = f"SCROLL_{direction}"
            issues.append(_issue("info", "SCREEN_LEVEL_SCROLL", "Kaydırma ekran seviyesinde şablonla üretildi; kaydedilen kap öğe kullanılmadı."))
        template = getattr(cfg.actionTemplates, template_key, None) if template_key in cfg.actionTemplates.model_fields else None
        supported = bool(template)
        if action in ELEMENT_ACTIONS and not selected:
            supported = False
            issues.append(_issue("error", "NO_SUPPORTED_LOCATOR", "Yapılandırılan locator şablonlarıyla ifade edilebilen locator yok; rastgele locator üretilmedi."))
        if template is None:
            issues.append(_issue("error", "UNSUPPORTED_ACTION", f"{action} için bu profilde aksiyon şablonu yok. Metot üretildi ancak "
                                 "UnsupportedOperationException fırlatır."))
        elif not template and supported is False and not any(i["code"] == "NO_SUPPORTED_LOCATOR" for i in issues):
            issues.append(_issue("error", "ACTION_TEMPLATE_MISSING", f"{template_key} aksiyon şablonu boş; framework metodu uydurulmadı. "
                                 "Ayarlardan şablon tanımlayın."))
        if selected and selected.get("unique") is False:
            issues.append(_issue("warning", "AMBIGUOUS_LOCATOR", f"Seçili locator kayıt anında {selected.get('matchCount')} öğe ile eşleşti."))
        if selected and action in ELEMENT_ACTIONS:
            key = (selected["strategy"], selected["value"])
            if key not in by_loc:
                by_loc[key] = {"name": _field_name(ev, label, {e["name"] for e in elements}), "annotation": selected["javaExpr"],
                               "selected": selected, "alternatives": alternatives, "label": label}
                elements.append(by_loc[key])
            element = by_loc[key]["name"]
        param = None
        if action == "INPUT_TEXT":
            iv = ev.get("inputValue") or {}
            if sensitive or iv.get("value") is None:
                key_name = f"{cfg.secretKeyPrefix}{const(label) or 'VALUE'}"
                param = {"name": "key", "specValue": key_name, "secret": True}
                issues.append(_issue("info", "SENSITIVE_VALUE", f"Hassas değer koda/feature'a yazılmadı; '{key_name}' anahtarı kullanıldı."))
            else:
                param = {"name": "value", "specValue": cucumber_text(iv["value"], 80), "secret": False}
        verb = getattr(cfg.verbs, "SCROLL" if action == "SCROLL" else action, None) if action in ("TAP", "INPUT_TEXT", "LONG_PRESS", "SCROLL", "BACK") else camel(action) or "perform"
        target = pascal(element) if element else (pascal(direction.lower()) if direction else "")
        if not element and action not in ("SCROLL", "BACK"):
            target = pascal(label)
        mkey = (action, element, direction, supported)
        pre = cfg.stepPrefix + " " if cfg.stepPrefix else ""
        lbl = cucumber_text(label)
        text = {"TAP": f"{pre}{lbl} öğesine tıklar", "LONG_PRESS": f"{pre}{lbl} öğesine uzun basar",
                "SCROLL": f"{pre}ekranı {DIR_TR.get(direction or 'DOWN')} kaydırır", "BACK": f"{pre}geri tuşuna basar",
                "INPUT_TEXT": f"{pre}{lbl} alanına {{string}} " + ("anahtarlı gizli test verisini yazar" if param and param["secret"] else "yazar")
                }.get(action, f"{pre}{lbl} için {cucumber_text(action)} işlemini yapar")
        if not supported:
            text += " - desteklenmiyor"
        if mkey not in by_key:
            mname, i = (verb + target) or "perform", 2
            while any(m["name"] == mname for m in methods):
                mname, i = f"{verb}{target}{i}", i + 1
            t, j = text, 2
            while t in texts:
                t, j = f"{text} - {j}", j + 1
            texts[t] = mkey
            by_key[mkey] = {"name": mname, "stepText": t, "action": action, "element": element, "template": template if supported else None,
                            "param": param, "direction": direction, "supported": supported, "order": n,
                            "comment": comment_safe(f"{action} · {label}")}
            methods.append(by_key[mkey])
        m = by_key[mkey]
        status = "UNSUPPORTED" if not supported else ("WARNING" if any(i["level"] == "warning" for i in issues) else "OK")
        rows.append({"order": n, "stepId": st["stepId"], "name": st.get("name"), "action": action, "label": label, "sensitive": sensitive,
                     "selected": selected, "alternatives": alternatives, "supported": supported, "issues": issues, "status": status,
                     "stepText": m["stepText"], "methodName": m["name"], "element": element, "params": [param] if param else []})
    return rows, elements, methods


async def build_pom_plan(session_id: str, cfg: PomConfig) -> dict:
    doc = await build_export(session_id)
    rc = resolve_pom(cfg, doc.get("name") or "Recorded")
    rows, elements, methods = build_steps(doc, rc)
    summary = {"total": len(rows), "supported": sum(r["supported"] for r in rows), "unsupported": sum(not r["supported"] for r in rows),
               "warnings": sum(1 for r in rows for i in r["issues"] if i["level"] == "warning")}
    return {"session": {"id": doc["sessionId"], "name": doc.get("name"), "packageName": doc["application"]["packageName"],
                        "demo": doc["demo"], "status": doc["status"]},
            "config": rc.model_dump(), "steps": rows, "elements": elements, "methods": methods, "summary": summary,
            "classes": rc.names()}
