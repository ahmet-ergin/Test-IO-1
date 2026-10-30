"""Plan for the Cucumber + POM profile: element fields, page methods and Turkish step texts (deduplicated)."""
import re
from services.export_service import build_export
from services.codegen.javautil import java_str, jcamel as camel, jpascal as pascal, jconst as const, is_ident, comment_safe, \
    fill_template_value, ascii_fold
from services.codegen.planner import _sensitive, _label, _scroll_direction, _issue, MASK
from services.codegen.pom_config import PomConfig, resolve_pom, LOCATOR_STRATEGIES, cucumber_text, parse_page_method
from services.codegen.javautil import jwords

ELEMENT_ACTIONS = {"TAP", "INPUT_TEXT", "LONG_PRESS"}
DIR_TR = {"DOWN": "aşağı", "UP": "yukarı", "LEFT": "sola", "RIGHT": "sağa"}


def annotation_for(loc: dict, cfg: PomConfig):
    tpl = getattr(cfg.locatorTemplates, loc["strategy"], "") if loc["strategy"] in LOCATOR_STRATEGIES else ""
    if not tpl:
        return None
    v = loc["value"]
    if loc["strategy"] == "RESOURCE_ID" and cfg.resourceIdFormat == "SHORT":
        v = v.split(":id/")[-1]
    args = fill_template_value(tpl, v, cfg.asciiOnly)
    if cfg.findByExtraArgs.strip():
        args += ", " + cfg.findByExtraArgs.strip()
    return f"@{cfg.locatorAnnotation.rsplit('.', 1)[-1]}({args})"


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


SENSITIVE_TOKENS = {"pin", "otp", "password", "passwd", "pass", "passcode", "pwd", "sifre", "parola", "cvv", "cvc", "tckn", "secret"}
SENSITIVE_JOINED = ("smscode", "smskod", "dogrulamakod", "verificationcode", "onaykod", "guvenlikkod", "securitycode")


def pom_sensitive(ev: dict) -> bool:
    """Masked/password fields, plus PIN/OTP/şifre-like ids, hints or descriptions (values are never written for these)."""
    if _sensitive(ev):
        return True
    el = ev.get("element") or {}
    for src in ((el.get("resourceId") or "").split("/")[-1], el.get("hint"), el.get("contentDesc")):
        toks = [w.lower() for w in jwords(ascii_fold(src or ""))]
        if SENSITIVE_TOKENS & set(toks) or any(j in "".join(toks) for j in SENSITIVE_JOINED):
            return True
    return False


def existing_matchers(cfg: PomConfig):
    from services.codegen.pom_validate import _matcher
    out = []
    for ex in (t.strip() for t in cfg.existingStepTexts if t.strip()):
        rx, _ = _matcher(ex, cfg.stepTextStyle)
        if rx is not None:
            out.append((ex, rx))
    return out


def step_expression(text: str, cfg: PomConfig) -> str:
    """Cucumber annotation text; REGEX style anchors and escapes literal parts, {string} becomes a quoted capture group."""
    if cfg.stepTextStyle != "REGEX":
        return text
    parts = [re.sub(r"([\\.\[\]{}()*+?^$|])", r"\\\1", p) for p in text.split("{string}")]
    return "^" + '"([^"]*)"'.join(parts) + "$"


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
    texts, step_names = {}, set()
    for n, st in enumerate(doc["steps"], start=1):
        ev = events.get(st["eventId"]) or {}
        action = st.get("action") or ev.get("action") or "UNKNOWN"
        sensitive = pom_sensitive(ev)
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
        manual = action == "SCROLL" and template == ""
        if manual:
            issues.append(_issue("error", "MANUAL_ADAPTATION_REQUIRED", "MANUEL UYARLAMA GEREKLİ: " + (cfg.scrollManualHint or
                                 f"{template_key} şablonu tanımlı değil; kaydırma için gereken hedef element/parametreler kayıtta yok, uydurulmadı.")))
        if action in ELEMENT_ACTIONS and not selected:
            supported = False
            issues.append(_issue("error", "NO_SUPPORTED_LOCATOR", "Yapılandırılan locator şablonlarıyla ifade edilebilen locator yok; rastgele locator üretilmedi."))
        if template is None:
            issues.append(_issue("error", "UNSUPPORTED_ACTION", f"{action} için bu profilde aksiyon şablonu yok. Metot üretildi ancak "
                                 "UnsupportedOperationException fırlatır."))
        elif not template and not manual and supported is False and not any(i["code"] == "NO_SUPPORTED_LOCATOR" for i in issues):
            issues.append(_issue("error", "ACTION_TEMPLATE_MISSING", f"{template_key} aksiyon şablonu boş; framework metodu uydurulmadı. "
                                 "Ayarlardan şablon tanımlayın."))
        if selected and selected["strategy"] in cfg.unverifiedLocatorStrategies:
            issues.append(_issue("warning", "LOCATOR_PREFIX_UNVERIFIED", f"{selected['strategy']} locator biçimi ({selected['javaExpr']}) "
                                 "framework tarafından desteklendiği doğrulanmadı; projenizde kontrol edin."))
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
        elif sensitive:
            issues.append(_issue("info", "SENSITIVE_FIELD", "Alan hassas (şifre/PIN/OTP) olarak algılandı; değer hiçbir çıktıya yazılmaz."))
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
            text += " - manuel uyarlama gerekli" if manual else " - desteklenmiyor"
        if mkey not in by_key:
            mname, i = (verb + target) or "perform", 2
            while any(m["name"] == mname for m in methods):
                mname, i = f"{verb}{target}{i}", i + 1
            t, j = text, 2
            while t in texts:
                t, j = f"{text} - {j}", j + 1
            texts[t] = mkey
            smname = mname
            if cfg.stepMethodNaming == "STEP_TEXT":
                base = camel(ascii_fold(t.replace("{string}", " "))) or mname
                base = base if not base[0].isdigit() else "adim" + base[:1].upper() + base[1:]
                smname, k = base[:80], 2
                while smname in step_names:
                    smname, k = f"{base[:76]}{k}", k + 1
            step_names.add(smname)
            by_key[mkey] = {"name": mname, "stepMethod": smname, "featureText": t, "stepText": step_expression(t, cfg), "action": action, "element": element, "template": template if supported else None,
                            "param": param, "direction": direction, "supported": supported, "manual": manual, "order": n,
                            "comment": comment_safe(f"{action} · {label}")}
            methods.append(by_key[mkey])
        m = by_key[mkey]
        if m["order"] != n:
            issues.append(_issue("info", "SAME_LOCATOR_ACTION", f"Adım {m['order']} ile aynı locator ve işlem; aynı step ve page metodu yeniden kullanıldı."))
        status = "MANUAL" if manual else "UNSUPPORTED" if not supported else ("WARNING" if any(i["level"] == "warning" for i in issues) else "OK")
        rows.append({"order": n, "stepId": st["stepId"], "name": st.get("name"), "action": action, "label": label, "sensitive": sensitive,
                     "selected": selected, "alternatives": alternatives, "supported": supported, "issues": issues, "status": status,
                     "stepText": m["stepText"], "featureText": m["featureText"], "methodName": m["name"], "stepMethod": m["stepMethod"], "element": element, "params": [param] if param else []})
    _apply_existing(rows, methods, elements, cfg)
    return rows, elements, methods


def _feature_line(row, m):
    t = m["featureText"]
    return t.replace("{string}", f'"{row["params"][0]["specValue"]}"', 1) if m["param"] and row["params"] else t


def _apply_existing(rows, methods, elements, cfg: PomConfig):
    """Reuse pasted Cucumber steps (only exact, unique matches) and pasted Page Interface methods (interface + signature)."""
    by_name = {m["name"]: m for m in methods}
    matchers = existing_matchers(cfg)
    for r in rows:
        m = by_name[r["methodName"]]
        line = _feature_line(r, m)
        r["featureLine"] = line
        hits = [ex for ex, rx in matchers if rx.fullmatch(line)]
        if len(hits) == 1:
            r["reusedStep"] = hits[0]
            r["status"] = "REUSED"
            r["issues"].append(_issue("info", "EXISTING_STEP_REUSED", f"Mevcut adım tekil ve kesin eşleşti, yeniden kullanıldı: '{hits[0]}'. Yeni step tanımı üretilmedi."))
        elif len(hits) > 1:
            r["issues"].append(_issue("warning", "AMBIGUOUS_EXISTING_STEP", f"Feature adımı birden fazla mevcut ifadeyle eşleşiyor ({'; '.join(hits[:3])}); "
                                      "yeniden kullanılmadı. Mevcut adımları netleştirin."))
            if r["status"] == "OK":
                r["status"] = "WARNING"
    for m in methods:
        mrows = [r for r in rows if r["methodName"] == m["name"]]
        m["stepReused"] = bool(mrows) and all(r.get("reusedStep") for r in mrows)
    iface = cfg.names()["iface"]
    existing = [pm for pm in (parse_page_method(x) for x in cfg.existingPageMethods if x.strip()) if pm and pm["iface"] == iface
                and (pm["ifaceFq"] == iface or pm["ifaceFq"] == f"{cfg.contractsPackage}.{iface}")]
    names = {m["name"] for m in methods}
    for m in methods:
        if m["stepReused"]:
            continue
        params = ["String"] if m["param"] else []
        same = [pm for pm in existing if pm["name"] == m["name"] and pm["params"] == params]
        note = None
        if same and same[0]["ret"] == "void":
            m["pageReused"] = True
            note = _issue("info", "EXISTING_PAGE_METHOD_REUSED", f"Mevcut {iface}.{m['name']}({', '.join(params)}) imzası birebir eşleşti; "
                          "page metodu yeniden üretilmedi, step bu metodu çağırır.")
        elif same:
            new, i = m["name"] + "Amts", 2
            while new in names:
                new, i = f"{m['name']}Amts{i}", i + 1
            note = _issue("warning", "PAGE_METHOD_SIGNATURE_CONFLICT", f"Mevcut {iface}.{m['name']} aynı parametrelerle farklı dönüş tipine "
                          f"({same[0]['ret']}) sahip; çakışmayı önlemek için yeni metot '{new}' olarak adlandırıldı.")
            for r in rows:
                if r["methodName"] == m["name"]:
                    r["methodName"] = new
            names.add(new)
            m["name"] = new
        elif any(pm["name"] == m["name"] for pm in existing):
            note = _issue("info", "PAGE_METHOD_OVERLOAD", f"Mevcut {iface}.{m['name']} farklı parametrelerle var; yeni metot aşırı yükleme (overload) olarak eklenir.")
        if note:
            for r in rows:
                if r["methodName"] == m["name"]:
                    r["issues"].append(note)
    used = {m["element"] for m in methods if not m["stepReused"] and not m.get("pageReused") and m["element"]}
    for e in elements:
        e["generated"] = e["name"] in used


async def build_pom_plan(session_id: str, cfg: PomConfig) -> dict:
    doc = await build_export(session_id)
    rc = resolve_pom(cfg, doc.get("name") or "Recorded")
    rows, elements, methods = build_steps(doc, rc)
    summary = {"total": len(rows), "supported": sum(r["supported"] for r in rows), "unsupported": sum(not r["supported"] for r in rows),
               "warnings": sum(1 for r in rows for i in r["issues"] if i["level"] == "warning")}
    return {"session": {"id": doc["sessionId"], "name": doc.get("name"), "packageName": doc["application"]["packageName"],
                        "demo": doc["demo"], "status": doc["status"]},
            "config": rc.model_dump(), "steps": rows, "elements": elements, "methods": methods, "summary": summary,
            "classes": rc.names(), "classConflicts": class_conflicts(rc, methods, rows)}


def class_conflicts(rc: PomConfig, methods=None, rows=None) -> list:
    """FQCNs that already exist in the user's project: listed names, plus interface/android page when existing page methods are reused."""
    n = rc.names()
    fqs = [f"{rc.stepsPackage}.{n['step']}", f"{rc.contractsPackage}.{n['iface']}", f"{rc.androidPackage}.{n['android']}", rc.helper_fqcn()]
    existing = {x.strip() for x in rc.existingClassNames if x.strip()}
    out = [fq for fq in fqs if fq in existing or fq.rsplit(".", 1)[-1] in existing]
    if any(m.get("pageReused") for m in methods or []):
        out += [fq for fq in fqs[1:3] if fq not in out]
    return out
