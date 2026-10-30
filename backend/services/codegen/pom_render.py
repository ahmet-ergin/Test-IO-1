"""Renders Step Definition, Page Interface, Android Page and Turkish .feature for the Cucumber + POM profile."""
from services.codegen.javautil import java_str, comment_safe, simple, pkg_of
from services.codegen.pom_config import PomConfig, feature_file_name

IND = "    "
BEGIN, END = "// <amts:members>", "// </amts:members>"


def _imports(pkg, fqcns):
    return "\n".join(f"import {i};" for i in sorted({f for f in fqcns if f and pkg_of(f) not in (pkg, "java.lang")}))


def _path(cfg, pkg, cls):
    return f"{cfg.sourceRoot}/{pkg.replace('.', '/')}/{cls}.java"


def _header(plan, what):
    s = plan["session"]
    return [f"/**", f" * AMTS tarafından üretildi ({what}) — oturum: {comment_safe(s['name'])} ({s['id'][:8]}).",
            " * Framework sınıf adları Kod Üreteci ayarlarından gelir; yeni driver veya framework sınıfı oluşturulmaz.", " */"]


def _sig(m):
    return f"void {m['name']}({'String value' if m['param'] else ''})"


def _page_methods(plan):
    return [m for m in plan["methods"] if not m.get("stepReused") and not m.get("pageReused")]


def _step_methods(plan):
    return [m for m in plan["methods"] if not m.get("stepReused")]


def render_interface(plan, cfg: PomConfig):
    n = plan["classes"]
    ann = simple(cfg.pageModelAnnotation) + (f"({cfg.pageModelArgs})" if cfg.pageModelArgs.strip() else "")
    body = []
    for m in _page_methods(plan):
        body += [f"{IND}// {m['comment']}" + ("" if m["supported"] else (" — MANUEL UYARLAMA GEREKLİ" if m.get("manual") else " — DESTEKLENMİYOR")), f"{IND}{_sig(m)};", ""]
    return "\n".join([f"package {cfg.contractsPackage};", "", _imports(cfg.contractsPackage, [cfg.pageModelAnnotation]), ""] +
                     _header(plan, "Page Interface") + [f"@{ann}", f"public interface {n['iface']} {{", "", f"{IND}{BEGIN}"] +
                     body + [f"{IND}{END}", "}", ""])


def _alt_comment(a):
    conf = f"{a['confidence']:.2f}" if isinstance(a.get("confidence"), (int, float)) else "?"
    if a["javaExpr"]:
        return f"{IND}//   {a['strategy']} ({conf}): {a['javaExpr']}"
    return f"{IND}//   " + comment_safe(f"{a['strategy']} ({conf}): yapılandırılan @FindBy şablonuyla desteklenmiyor — {a['value']}")


def _action_body(m, cfg):
    if m.get("manual"):
        msg = f"AMTS: MANUEL UYARLAMA GEREKLİ — {m['action']} ({m['direction']}). {cfg.scrollManualHint or 'Kaydırma şablonu tanımlı değil.'}"
        return [f"throw new UnsupportedOperationException({java_str(msg, cfg.asciiOnly)});"]
    if not m["supported"]:
        msg = f"AMTS: {m['action']} işlemi bu profilde desteklenmiyor veya şablonu tanımlı değil; mevcut framework metodunuzla elle uygulayın."
        return [f"throw new UnsupportedOperationException({java_str(msg, cfg.asciiOnly)});"]
    code = m["template"].replace("{element}", m["element"] or "").replace("{app}", cfg.appExpression)
    code = code.replace("{value}", "value" if m["param"] else "")
    return [ln.strip() for ln in code.split("\n") if ln.strip()]


def render_android(plan, cfg: PomConfig):
    n = plan["classes"]
    body = []
    mod = "" if cfg.elementFieldModifier == "package" else cfg.elementFieldModifier + " "
    elements = [e for e in plan["elements"] if e.get("generated", True)]
    for e in elements:
        conf = e["selected"].get("confidence")
        body.append(f"{IND}// {comment_safe(e['label'])} · seçili {e['selected']['strategy']}" + (f" ({conf:.2f})" if isinstance(conf, (int, float)) else ""))
        if e["alternatives"]:
            body.append(f"{IND}// Alternatif locator'lar (bilgi amaçlı):")
            body += [_alt_comment(a) for a in e["alternatives"]]
        body += [f"{IND}{e['annotation']}", f"{IND}{mod}{simple(cfg.elementType)} {e['name']};", ""]
    for m in _page_methods(plan):
        body += [f"{IND}@Override", f"{IND}public {_sig(m)} {{"] + [f"{IND}{IND}{ln}" for ln in _action_body(m, cfg)] + [f"{IND}}}", ""]
    imports = [cfg.pageBaseClass, f"{cfg.contractsPackage}.{n['iface']}"]
    if elements:
        imports += [cfg.locatorAnnotation, cfg.elementType]
    return "\n".join([f"package {cfg.androidPackage};", "", _imports(cfg.androidPackage, imports), ""] + _header(plan, "Android Page") +
                     [f"public class {n['android']} extends {simple(cfg.pageBaseClass)} implements {n['iface']} {{", "", f"{IND}{BEGIN}"] +
                     body + [f"{IND}{END}", "}", ""])


def render_steps(plan, cfg: PomConfig):
    n, f = plan["classes"], cfg.pageFieldName
    mod = "" if cfg.pageFieldModifier == "package" else cfg.pageFieldModifier + " "
    body = [f"{IND}// Page nesnesi framework'ün bağlama mekanizmasıyla atanır; new ile oluşturulmaz."]
    if cfg.pageFieldAnnotation:
        body.append(f"{IND}@{simple(cfg.pageFieldAnnotation)}")
    body += [f"{IND}{mod}{n['iface']} {f};", ""]
    step_ann = simple(cfg.stepAnnotation)
    secret = False
    for m in _step_methods(plan):
        p = m["param"]
        if p and p["secret"]:
            secret = True
            call = f"{f}.{m['name']}({cfg.secret_call(p['name'])});"
        else:
            call = f"{f}.{m['name']}({p['name'] if p else ''});"
        body += [f"{IND}// {m['comment']}" + ("" if m["supported"] else (" — MANUEL UYARLAMA GEREKLİ" if m.get("manual") else " — DESTEKLENMİYOR") + " (page metodu hata fırlatır)"),
                 f"{IND}@{step_ann}({java_str(m['stepText'], cfg.asciiOnly)})",
                 f"{IND}public void {m['stepMethod']}({'String ' + p['name'] if p else ''}) {{", f"{IND}{IND}{call}", f"{IND}}}", ""]
    imports = [cfg.stepAnnotation, cfg.stepBaseClass, cfg.pageFieldAnnotation, f"{cfg.contractsPackage}.{n['iface']}"]
    if secret and cfg.secretProvider == "HELPER":
        imports.append(cfg.helper_fqcn())
    return "\n".join([f"package {cfg.stepsPackage};", "", _imports(cfg.stepsPackage, imports), ""] + _header(plan, "Step Definition") +
                     [f"public class {n['step']} extends {simple(cfg.stepBaseClass)} {{", "", f"{IND}{BEGIN}"] + body + [f"{IND}{END}", "}", ""])


def render_feature(plan, cfg: PomConfig):
    s = plan["session"]
    by_name = {m["name"]: m for m in plan["methods"]}
    lines = ["# language: tr"] + ([cfg.tags] if cfg.tags else []) + [f"Özellik: {cfg.featureName}",
             f"  AMTS tarafından üretildi. Oturum: {s['id']}. Uygulama: {s['packageName']}.",
             "  Ön koşul: Uygulama cihazda açık ve kaydın başladığı ekranda olmalı.", "", f"  Senaryo: {cfg.scenarioName}"]
    for i, r in enumerate(plan["steps"]):
        m = by_name[r["methodName"]]
        text = r["featureLine"]
        if r.get("reusedStep"):
            lines.append(f"    # AMTS: mevcut adım yeniden kullanıldı: {r['reusedStep']}")
        if m.get("manual"):
            lines.append(f"    # AMTS UYARI: Adım {r['order']} ({r['action']}) MANUEL UYARLAMA GEREKLİ; page metodu UnsupportedOperationException fırlatır.")
        elif not r["supported"]:
            lines.append(f"    # AMTS UYARI: Adım {r['order']} ({r['action']}) desteklenmiyor; page metodu UnsupportedOperationException fırlatır.")
        lines.append(f"    {'Diyelim ki' if i == 0 else 'Ve'} {text}")
    return "\n".join(lines) + "\n"


def render_readme(plan, cfg: PomConfig, files):
    issues = [f"- Adım {s['order']} [{i['code']}] {i['message']}" for s in plan["steps"] for i in s["issues"] if i["level"] != "info"]
    return "\n".join([
        f"# AMTS — Cucumber + POM çıktısı: {plan['session']['name']}", "",
        "Mevcut projenize eklenmek içindir: yeni driver, temel test sınıfı, Model, PageFactory veya framework sınıfı üretilmez.",
        "Mevcut sınıflara ekleme yapacaksanız her dosyada `// <amts:members>` ve `// </amts:members>` arasını kopyalayın", "(Kod Üreteci ekranında 'Üyeleri kopyala').", "",
        "## Dosyalar", *[f"- `{f['path']}`" for f in files], "",
        "## Kullanılan yapılandırma (yerel ayarlarınızdan)",
        f"- Java {cfg.javaVersion}; Step temel sınıfı `{cfg.stepBaseClass}`; Page temel sınıfı `{cfg.pageBaseClass}`",
        f"- @PageModel: `{cfg.pageModelAnnotation}`; locator anotasyonu: `{cfg.locatorAnnotation}`; element tipi: `{cfg.elementType}`",
        f"- Cucumber: `{cfg.stepAnnotation}`; uygulama nesnesi: `{cfg.appExpression}`",
        "- Aksiyon şablonları: " + ", ".join(f"{k}=`{v.replace(chr(10), ' ')}`" if v else f"{k}=(tanımsız)" for k, v in cfg.actionTemplates.model_dump().items()), "",
        "## Uyarılar / desteklenmeyen adımlar", *(issues or ["- Yok"]), "",
        "## Hassas veriler",
        f"Şifre/PIN/OTP değerleri hiçbir dosyaya yazılmaz; feature'da `{cfg.secretKeyPrefix}…` anahtarı geçer ve değer test anında "
        + (f"`{cfg.secretHelperClass}.require(key)` ile ortam değişkeninden veya -D sistem özelliğinden çözülür; eksikse açık hata fırlatılır."
           if cfg.secretProvider == "HELPER" else f"özel sağlayıcı `{cfg.secretValueTemplate}` ile çözülür."), "",
        "## Mevcut sınıflar",
        *([f"- `{fq}` mevcut: yalnızca eklenecek parça (`.amts-members.txt`) üretildi; otomatik birleştirme yapılmaz." for fq in plan.get("classConflicts") or []]
          or ["- Çakışma bildirilmedi."]), "",
        "## Doğrulama kapsamı",
        "Paket/import/sınıf ilişkileri ve Java sözdizimi AMTS'de yerel stub'larla derlenerek kontrol edilir.",
        "Kurum içi framework bağımlılıkları erişilebilir olmadığından gerçek framework'e karşı derleme DOĞRULANMADI;", "projenizde `mvn test-compile` çalıştırın.", ""])


def render_helper(cfg: PomConfig):
    pkg, cls, pre = cfg.secretHelperPackage or cfg.stepsPackage, cfg.secretHelperClass, cfg.secretKeyPrefix
    return "\n".join([
        f"package {pkg};", "", "/**", " * AMTS tarafından üretildi — hassas test verisi (şifre/PIN/OTP) çözümleyici.",
        " * Sıra: ortam değişkeni, ardından -D sistem özelliği. Değerler hiçbir zaman loglanmaz veya mesajlara yazılmaz.",
        " * Kurumsal güvenli veri sağlayıcınızı kullanmak için Kod Üreteci ayarlarından 'Özel sağlayıcı' seçin.", " */",
        f"public final class {cls} {{", "", f'{IND}private static final String PREFIX = "{pre}";', "", f"{IND}private {cls}() {{", f"{IND}}}", "",
        f"{IND}public static String require(String key) {{",
        f"{IND}{IND}if (key == null || !key.startsWith(PREFIX)) {{",
        f'{IND}{IND}{IND}throw new IllegalArgumentException("AMTS: Gizli veri anahtarı " + PREFIX + " ile başlamalı: " + key);', f"{IND}{IND}}}",
        f"{IND}{IND}String value = System.getenv(key);",
        f"{IND}{IND}if (value == null || value.isEmpty()) {{", f"{IND}{IND}{IND}value = System.getProperty(key);", f"{IND}{IND}}}",
        f"{IND}{IND}if (value == null || value.isEmpty()) {{",
        f'{IND}{IND}{IND}throw new IllegalStateException("AMTS: \'" + key + "\' gizli test verisi tanımlı değil. "',
        f'{IND}{IND}{IND}{IND}+ "Ortam değişkeni olarak veya -D" + key + "=... sistem özelliğiyle sağlayın.");', f"{IND}{IND}}}",
        f"{IND}{IND}return value;", f"{IND}}}", "}", ""])


SNIP_IMP, SNIP_IMP_END = "// <amts:imports>", "// </amts:imports>"


def to_snippet(f, fq):
    c = f["content"]
    imports = [ln for ln in c.split("\n") if ln.startswith("import ")]
    a, b = c.find(BEGIN), c.find(END)
    members = c[a + len(BEGIN):b].strip("\n").rstrip() if a >= 0 < b else c
    head = [f"// AMTS: {fq} projenizde zaten mevcut. Bu dosya tam sınıf DEĞİLDİR ve otomatik birleştirme yapılmaz.",
            "// Aşağıdaki import'ları ve üyeleri mevcut sınıfa elle ekleyin; mevcut dosyanın üzerine yazmayın."]
    body = "\n".join(head + [SNIP_IMP, *imports, SNIP_IMP_END, f"{IND}{BEGIN}", members, f"{IND}{END}", ""])
    return {**f, "path": f["path"][:-5] + ".amts-members.txt", "language": "java-snippet", "snippetOf": fq, "content": body}


def generate_files(plan, cfg: PomConfig):
    n = plan["classes"]
    files = [{"path": _path(cfg, cfg.stepsPackage, n["step"]), "language": "java", "role": "steps", "content": render_steps(plan, cfg)},
             {"path": _path(cfg, cfg.contractsPackage, n["iface"]), "language": "java", "role": "contract", "content": render_interface(plan, cfg)},
             {"path": _path(cfg, cfg.androidPackage, n["android"]), "language": "java", "role": "android", "content": render_android(plan, cfg)}]
    if cfg.secretProvider == "HELPER" and any(m["param"] and m["param"]["secret"] for m in _step_methods(plan)):
        files.append({"path": _path(cfg, cfg.secretHelperPackage or cfg.stepsPackage, cfg.secretHelperClass), "language": "java",
                      "role": "secrets", "content": render_helper(cfg)})
    conflicts = set(plan.get("classConflicts") or [])
    files = [f for f in files if not (f["role"] == "secrets" and cfg.helper_fqcn() in conflicts)]
    files = [to_snippet(f, fq) if (fq := f["path"][len(cfg.sourceRoot) + 1:-5].replace("/", ".")) in conflicts else f for f in files]
    if cfg.generateFeature:
        files.insert(0, {"path": f"{cfg.featureDir}/{feature_file_name(plan['session']['name'] or '')}", "language": "gherkin",
                         "role": "feature", "content": render_feature(plan, cfg)})
    files.append({"path": "AMTS_INTEGRATION.md", "language": "markdown", "role": "readme", "content": render_readme(plan, cfg, files)})
    return files
