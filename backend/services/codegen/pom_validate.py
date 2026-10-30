"""Validation for the Cucumber + POM profile. Never claims framework compilation: internal deps are stubbed."""
import re
import zipfile
from functools import lru_cache
from services.codegen.javautil import simple, pkg_of
from services.codegen.pom_config import PomConfig
from services.codegen.validate import LIB_DIR, content_hash, path_errors, defined_classes, compile_java, _JSTR, _unescape

GHERKIN_KW = r"(?:Diyelim ki|Eğer ki|O zaman|Ve|Ama|Fakat|Given|When|Then|And|But|\*)"
STUB_PKG = "amts.stubs"


def cucumber_regex(expr: str):
    out, i = [], 0
    for m in re.finditer(r"\{(\w*)\}", expr):
        out.append(re.escape(expr[i:m.start()]))
        out.append({"string": r'"[^"]*"', "int": r"-?\d+", "float": r"-?\d+(?:\.\d+)?", "word": r"\S+"}.get(m.group(1), r".*"))
        i = m.end()
    out.append(re.escape(expr[i:]))
    return re.compile("^" + "".join(out) + "$")


def step_defs(content: str, ann: str):
    rx = re.compile(r"@" + re.escape(ann) + r'\s*\(\s*("(?:[^"\\\n]|\\.)*")\s*\)\s*public\s+void\s+(\w+)\s*\(([^)]*)\)', re.S)
    out = []
    for m in rx.finditer(content):
        text = _unescape(_JSTR.findall(m.group(1))[0])
        out.append({"text": text, "method": m.group(2), "params": len([p for p in m.group(3).split(",") if p.strip()])})
    return out


def feature_steps(content: str):
    return [(i + 1, m.group(1).strip()) for i, ln in enumerate(content.splitlines())
            if not ln.strip().startswith("#") and (m := re.match(rf"^\s*{GHERKIN_KW}\s+(.+)$", ln))]


def _matcher(text: str, style: str):
    if style != "REGEX":
        return cucumber_regex(text), len(re.findall(r"\{\w*\}", text))
    try:
        rx = re.compile(text)
    except re.error:
        return None, 0
    return rx, rx.groups


def check_feature(files, cfg: PomConfig):
    style = cfg.stepTextStyle
    defs = [d for f in files if f["path"].endswith(".java") for d in step_defs(f["content"], simple(cfg.stepAnnotation))]
    errors, seen = [], {}
    for d in defs:
        if d["text"] in seen:
            errors.append(f"Aynı Cucumber ifadesi iki metotta: '{d['text']}' ({seen[d['text']]}, {d['method']})")
        seen[d["text"]] = d["method"]
        d["rx"], groups = _matcher(d["text"], style)
        if d["rx"] is None:
            errors.append(f"{d['method']}: geçersiz regex '{d['text']}'.")
        elif d["params"] != groups:
            errors.append(f"{d['method']}: parametre sayısı ({d['params']}) step ifadesindeki parametrelerle ({groups}) eşleşmiyor.")
        if style == "REGEX" and d["rx"] is not None and not (d["text"].startswith("^") and d["text"].endswith("$")):
            errors.append(f"{d['method']}: regex ifadesi ^ ile başlamalı ve $ ile bitmeli.")
    feats = [f for f in files if f["path"].endswith(".feature")]
    used, total = set(), 0
    for f in feats:
        for line, text in feature_steps(f["content"]):
            total += 1
            hits = [d for d in defs if d["rx"] is not None and d["rx"].fullmatch(text)]
            if len(hits) != 1:
                errors.append(f"{f['path']}:{line} — '{text}' için {len(hits)} step definition eşleşti (1 olmalı).")
            used |= {h["text"] for h in hits}
    if feats:
        errors += [f"{d['method']} — '{d['text']}' feature dosyasında kullanılmıyor." for d in defs if d["text"] not in used]
    existing = [t.strip() for t in cfg.existingStepTexts if t.strip()]
    coll = [d["text"] for d in defs if d["text"] in existing]
    for f in feats:
        for _, text in feature_steps(f["content"]):
            for ex in existing:
                rx, _ = _matcher(ex, style)
                if rx is not None and rx.fullmatch(text):
                    coll.append(f"'{text}' mevcut '{ex}' ifadesiyle de eşleşir (belirsiz adım)")
    summary = f"{total} feature adımı, {len(defs)} @{simple(cfg.stepAnnotation)} tanımı" if feats else \
        f".feature üretilmedi; {len(defs)} @{simple(cfg.stepAnnotation)} tanımı yalnızca tekrar/parametre açısından kontrol edildi"
    return ({"id": "feature_match", "status": "FAIL" if errors else "PASS", "summary": summary, "details": errors[:50]},
            {"id": "step_collisions", "status": "FAIL" if coll else "PASS",
             "summary": f"{len(existing)} mevcut adım ifadesiyle karşılaştırıldı" if existing else "Mevcut adım metni girilmedi",
             "details": [f"Çakışma: {c}" for c in dict.fromkeys(coll)][:50]})


def _iface_methods(content: str):
    return re.findall(r"^\s*(?:public\s+)?(?:abstract\s+)?[\w<>\[\], ]+\s+(\w+)\s*\([^)]*\)\s*;", content, re.M)


def _code_only(content: str) -> str:
    """Drops comment-only lines (// and javadoc) so commented alternatives/notes don't affect structure checks."""
    return "\n".join(ln for ln in content.splitlines()
                     if not re.match(r"^\s*(//|/\*|\*)", ln))


def check_structure(files, cfg: PomConfig, classes: dict):
    role = {f.get("role"): _code_only(f["content"]) for f in files}
    st, ct, an = role.get("steps", ""), role.get("contract", ""), role.get("android", "")
    e = []
    pm, mdl, tst = simple(cfg.pageModelAnnotation), simple(cfg.pageBaseClass), simple(cfg.stepBaseClass)
    loc, el, iface = simple(cfg.locatorAnnotation), simple(cfg.elementType), classes["iface"]
    iface_fq = f"{cfg.contractsPackage}.{iface}"

    def imported(content, fq, own_pkg):
        return pkg_of(fq) == own_pkg or re.search(rf"^\s*import\s+{re.escape(fq)}\s*;", content, re.M)

    if not re.search(rf"@{pm}\b[^\n]*\n(?:\s*@[^\n]*\n)*\s*public\s+interface\s+{iface}\b", ct):
        e.append(f"Page Interface '{iface}' @{pm} anotasyonuna sahip olmalı.")
    if not imported(ct, cfg.pageModelAnnotation, cfg.contractsPackage):
        e.append(f"Page Interface {cfg.pageModelAnnotation} import etmeli.")
    if re.search(r"\)\s*\{|\bdefault\s+\w|\bstatic\s+\w", ct.split("interface", 1)[-1]):
        e.append("Page Interface yalnızca metot imzaları içermeli (gövde/default/static yok).")
    m = re.search(rf"public\s+class\s+{classes['android']}\s+extends\s+(\w+)\s+implements\s+([\w\s,]+)\{{", an)
    if not m or m.group(1) != mdl or iface not in [x.strip() for x in m.group(2).split(",")]:
        e.append(f"Android Page '{classes['android']}' '{mdl}' sınıfından türemeli ve '{iface}' arayüzünü uygulamalı.")
    for fq in (cfg.pageBaseClass, iface_fq):
        if not imported(an, fq, cfg.androidPackage):
            e.append(f"Android Page {fq} import etmeli.")
    for name in _iface_methods(ct):
        if not re.search(rf"public\s+[\w<>\[\]]+\s+{name}\s*\(", an):
            e.append(f"Interface metodu '{name}' Android Page'de uygulanmamış.")
    anns = len(re.findall(rf"@{loc}\s*\(", an))
    fields = len(re.findall(rf"@{loc}\s*\([^\n]*\)\s*\n\s*(?:private\s+|protected\s+|public\s+)?{el}\s+\w+\s*;", an))
    if anns != fields:
        e.append(f"Her @{loc} bir {el} alanı üzerinde olmalı ({anns} anotasyon, {fields} alan).")
    if anns and not (imported(an, cfg.locatorAnnotation, cfg.androidPackage) and imported(an, cfg.elementType, cfg.androidPackage)):
        e.append(f"Android Page {cfg.locatorAnnotation} ve {cfg.elementType} import etmeli.")
    if not re.search(rf"public\s+class\s+{classes['step']}\s+extends\s+{tst}\s*\{{", st):
        e.append(f"Step sınıfı '{classes['step']}' '{tst}' sınıfından türemeli.")
    if not re.search(rf"\b{iface}\s+{cfg.pageFieldName}\s*;", st):
        e.append(f"Step sınıfında '{iface} {cfg.pageFieldName};' alanı olmalı.")
    if not imported(st, iface_fq, cfg.stepsPackage) or not imported(st, cfg.stepBaseClass, cfg.stepsPackage):
        e.append(f"Step sınıfı {iface_fq} ve {cfg.stepBaseClass} import etmeli.")
    for txt, where in ((st, "Step sınıfı"), (an, "Android Page"), (ct, "Page Interface")):
        if re.search(r"\bnew\s+\w*(Driver|Page|Model)\w*\s*\(", txt) or re.search(rf"\bnew\s+({iface}|{classes['android']})\b", txt):
            e.append(f"{where} page/driver nesnesini new ile oluşturmamalı.")
    if re.search(rf"@{loc}\b|\b{el}\b|AppiumBy|\bdriver\b|{re.escape(cfg.appExpression)}\.", st):
        e.append("Step sınıfı locator, element veya uygulama/driver işlemi içermemeli; yalnızca Page Interface metotlarını çağırmalı.")
    names = set(_iface_methods(ct))
    for call in re.findall(rf"\b{cfg.pageFieldName}\.(\w+)\s*\(", st):
        if call not in names:
            e.append(f"Step sınıfı arayüzde olmayan '{call}' metodunu çağırıyor.")
    return {"id": "structure", "status": "FAIL" if e else "PASS",
            "summary": "Paket, import, @PageModel, extends/implements, @FindBy alanları ve katman kuralları kontrol edildi.", "details": e}


def _attrs(texts):
    d = {}
    for t in texts:
        t = (t or "").strip()
        if re.fullmatch(r'"(?:[^"\\]|\\.)*"', t):
            d["value"] = "String"
        for name, val in re.findall(r'(\w+)\s*=\s*(\{value\}|"(?:[^"\\]|\\.)*"|-?\d+|true|false)', t):
            d[name] = "String" if val[0] in '{"' else ("boolean" if val in ("true", "false") else "int")
    dv = {"String": '""', "int": "0", "boolean": "false"}
    return [f"{t} {n}() default {dv[t]};" for n, t in d.items()]


def _annotation(fq, target, attrs):
    return (f"package {pkg_of(fq)};\n\nimport java.lang.annotation.*;\n\n@Retention(RetentionPolicy.RUNTIME)\n@Target(ElementType.{target})\n"
            f"public @interface {simple(fq)} {{\n    " + "\n    ".join(attrs) + "\n}\n")


@lru_cache(maxsize=1)
def _jar_classes():
    out = set()
    for j in LIB_DIR.glob("*.jar") if LIB_DIR.exists() else []:
        with zipfile.ZipFile(j) as z:
            out |= {n[:-6].replace("/", ".") for n in z.namelist() if n.endswith(".class")}
    return out


def pom_stubs(cfg: PomConfig, defined: set) -> dict:
    tpls = [v for v in cfg.actionTemplates.model_dump().values() if v]
    el_methods = sorted({m for t in tpls for m in re.findall(r"\{element\}\.(\w+)\s*\(", t)})
    app_methods = sorted({m for t in tpls for m in re.findall(r"\{app\}\.(\w+)\s*\(", t)})
    app_cls = f"{STUB_PKG}.AmtsAppStub"
    s = {
        cfg.stepBaseClass: f"package {pkg_of(cfg.stepBaseClass)};\n\npublic class {simple(cfg.stepBaseClass)} {{\n}}\n",
        cfg.pageBaseClass: f"package {pkg_of(cfg.pageBaseClass)};\n\npublic class {simple(cfg.pageBaseClass)} {{\n    "
                           + (f"protected {app_cls} {cfg.appExpression[:-2]}() {{ return null; }}" if cfg.appExpression.endswith("()")
                              else f"protected {app_cls} {cfg.appExpression};") + "\n}\n",
        app_cls: f"package {STUB_PKG};\n\npublic class AmtsAppStub {{\n    " + "\n    ".join(f"public void {m}(Object... args) {{ }}" for m in app_methods) + "\n}\n",
        cfg.elementType: f"package {pkg_of(cfg.elementType)};\n\npublic interface {simple(cfg.elementType)} {{\n    "
                         + "\n    ".join(f"void {m}(Object... args);" for m in el_methods) + "\n}\n",
        cfg.locatorAnnotation: _annotation(cfg.locatorAnnotation, "FIELD", _attrs([*cfg.locatorTemplates.model_dump().values(), cfg.findByExtraArgs])),
        cfg.pageModelAnnotation: _annotation(cfg.pageModelAnnotation, "TYPE", _attrs([cfg.pageModelArgs])),
    }
    if cfg.pageFieldAnnotation:
        s[cfg.pageFieldAnnotation] = _annotation(cfg.pageFieldAnnotation, "FIELD", [])
    if cfg.stepAnnotation not in _jar_classes():
        s[cfg.stepAnnotation] = _annotation(cfg.stepAnnotation, "METHOD", ["String value();"])
    return {k: v for k, v in s.items() if k not in defined and k not in _jar_classes()}


async def check_syntax(files, cfg: PomConfig):
    java = [f for f in files if f["path"].endswith(".java")]
    perr = path_errors(java)
    if perr:
        return {"id": "java_syntax", "status": "FAIL", "summary": "Dosya yolu ile package/sınıf adı uyumsuz.", "details": perr}
    stubs = pom_stubs(cfg, defined_classes(java))
    r = await compile_java(java, cfg.javaVersion, stubs)
    if not r["available"]:
        return {"id": "java_syntax", "status": "SKIPPED", "summary": "Bu sunucuda javac yok; sözdizimi derlemesi yapılamadı.", "details": []}
    ok = r["code"] == 0
    return {"id": "java_syntax", "status": "PASS" if ok else "FAIL", "stubs": list(stubs),
            "summary": (f"javac --release {r['release']} ile {len(java)} dosya derlendi (Java {cfg.javaVersion} sözdizimi + dosyalar arası "
                        f"ilişkiler). Kurum içi sınıflar yerine yerel stub kullanıldı: {', '.join(stubs)}." if ok else
                        f"Derleme hatası (javac --release {r['release']}). Şablonlar stub üretilemeyen bir sembol kullanıyorsa bu beklenen bir sonuçtur.") + r["note"],
            "details": [] if ok else r["lines"][:40]}


def check_class_conflicts(files, cfg: PomConfig):
    existing = {x.strip() for x in cfg.existingClassNames if x.strip()}
    out = []
    for fq in sorted(defined_classes([f for f in files if f["path"].endswith(".java")])):
        if fq in existing:
            out.append(f"{fq} projenizde zaten var; dosyanın üzerine yazmayın — 'Üyeleri kopyala' ile mevcut sınıfa ekleyin.")
        elif simple(fq) in existing:
            out.append(f"'{simple(fq)}' adlı bir sınıf projenizde var (paket belirtilmedi); {fq} ile karıştırılmadığından emin olun.")
    return {"id": "class_collisions", "status": "WARN" if out else "PASS",
            "summary": f"{len(existing)} mevcut sınıf adıyla karşılaştırıldı" if existing else "Mevcut sınıf adı girilmedi",
            "details": out}


async def validate_pom(files, cfg: PomConfig, classes: dict) -> dict:
    feat, coll = check_feature(files, cfg)
    checks = [check_structure(files, cfg, classes), feat, coll, check_class_conflicts(files, cfg), await check_syntax(files, cfg),
              {"id": "framework_compile", "status": "NOT_VERIFIED", "details": [],
               "summary": "Kurum içi framework bağımlılıkları bu ortamda erişilebilir değil; gerçek framework'e karşı derleme doğrulanmadı. "
                          "Projenizde mvn test-compile çalıştırın."}]
    if any(c["status"] == "FAIL" for c in checks):
        status = "FAILED"
    elif any(c["status"] == "SKIPPED" for c in checks):
        status = "NOT_VERIFIED"
    else:
        status = "STRUCTURE_VERIFIED"
    return {"status": status, "contentHash": content_hash(files), "checks": checks}
