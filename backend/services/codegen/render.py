"""Renders Gauge .spec, Java step implementations, locator class and (optional) gesture helper."""
from datetime import datetime, timezone
from services.codegen.javautil import java_str, comment_safe, simple, pkg_of

DRIVER_IMPORT = {"AppiumDriver": "io.appium.java_client.AppiumDriver",
                 "AndroidDriver": "io.appium.java_client.android.AndroidDriver",
                 "WebDriver": "org.openqa.selenium.WebDriver"}
IND = "    "


def _path(cfg, pkg, cls):
    return f"{cfg.sourceRoot}/{pkg.replace('.', '/')}/{cls}.java"


def _loc_comment(loc) -> str:
    conf = f"{loc['confidence']:.2f}" if isinstance(loc.get("confidence"), (int, float)) else "?"
    uniq = {True: "tekil", False: f"{loc.get('matchCount')} eşleşme", None: "doğrulanmadı"}[loc.get("unique")]
    if loc["strategy"] == "COORDINATES":
        expr = f"koordinat ({loc['javaExpr']}) — W3C Actions, çözünürlüğe bağlı"
    elif loc["javaExpr"]:
        expr = loc["javaExpr"]
    else:
        expr = f"{loc['strategy']} desteklenmiyor"
    return comment_safe(f"{loc['strategy']} ({conf}, {uniq}): ") + " " + expr if loc["javaExpr"] and loc["strategy"] != "COORDINATES" \
        else comment_safe(f"{loc['strategy']} ({conf}, {uniq}): {expr}")


def _alt_lines(step, indent) -> list:
    if not step["alternatives"]:
        return []
    return [f"{indent}// Alternatif locator'lar (değiştirmek için seçili ifadeyle yer değiştirin):"] + \
           [f"{indent}//   {_loc_comment(a)}" for a in step["alternatives"]]


def _locator_ref(step, cfg):
    if cfg.locatorStorage == "LOCATOR_CLASS":
        return f"{cfg.locatorClassName}.{step['constName']}"
    return step["selected"]["javaExpr"]


def _call(cfg, kind, args):
    h = cfg.helper
    name = getattr(h.methods, kind) if h.mode != "GENERATED" else kind
    a = (["driver()"] if h.mode == "GENERATED" or h.passDriver else []) + args
    target = "" if h.mode == "INHERITED" else (h.className if h.mode == "GENERATED" else simple(h.className)) + "."
    return f"{target}{name}({', '.join(a)});"


def _body(step, cfg):
    if not step["supported"]:
        msg = f"AMTS: Adım {step['order']} ({step['action']}) kod üreteci tarafından desteklenmiyor; mevcut framework yardımcılarınızla elle uygulayın."
        return [f"throw new UnsupportedOperationException({java_str(msg, cfg.asciiOnly)});"], set()
    sel, a, imports = step["selected"], step["action"], set()
    coords = sel["strategy"] == "COORDINATES"
    if a in ("LONG_PRESS",) or (a == "SCROLL" and coords):
        imports.add("java.time.Duration")
    if not coords and cfg.locatorStorage == "INLINE":
        imports.add("io.appium.java_client.AppiumBy")
    if a == "TAP":
        line = _call(cfg, "tapAt", [str(sel["point"]["x"]), str(sel["point"]["y"])]) if coords else _call(cfg, "tap", [_locator_ref(step, cfg)])
    elif a == "LONG_PRESS":
        d = f"Duration.ofMillis({step['holdMs']})"
        line = _call(cfg, "longPressAt", [str(sel["point"]["x"]), str(sel["point"]["y"]), d]) if coords else _call(cfg, "longPress", [_locator_ref(step, cfg), d])
    else:
        if coords:
            f, t = step["swipe"]["from"], step["swipe"]["to"]
            line = _call(cfg, "swipe", [str(f["x"]), str(f["y"]), str(t["x"]), str(t["y"]), "Duration.ofMillis(600)"])
        else:
            line = _call(cfg, "scroll", [_locator_ref(step, cfg), java_str(step["direction"])])
    return [line], imports


def _uses_driver(plan, cfg):
    return any(s["supported"] for s in plan["steps"]) and (cfg.helper.mode == "GENERATED" or cfg.helper.passDriver)


def _imports_block(pkg, imports):
    out = sorted(i for i in imports if pkg_of(i) not in (pkg, "java.lang"))
    return "\n".join(f"import {i};" for i in out)


def render_steps(plan, cfg) -> str:
    pkg, cls = cfg.stepsPackage, cfg.stepClassName
    imports = {"com.thoughtworks.gauge.Step"}
    methods = []
    for s in plan["steps"]:
        body, imp = _body(s, cfg)
        imports |= imp
        sel = s["selected"]
        head = [f"{IND}// Adım {s['order']} — {s['action']}" + (f" · seçili {_loc_comment(sel)}" if sel else "")]
        for i in s["issues"]:
            if i["level"] != "info" or i["code"] == "SENSITIVE_VALUE":
                head.append(f"{IND}// AMTS {i['level'].upper()} [{i['code']}]: {comment_safe(i['message'])}")
        if cfg.locatorStorage == "INLINE" or not sel:
            head += _alt_lines(s, IND)
        params = ", ".join(f"String {p['name']}" for p in s["params"])
        methods.append("\n".join(head + [
            f"{IND}@Step({java_str(s['stepText'], cfg.asciiOnly)})",
            f"{IND}public void {s['methodName']}({params}) {{"] + [f"{IND}{IND}{b}" for b in body] + [f"{IND}}}"]))
    extends = ""
    if cfg.baseClass and (cfg.driver.mode == "INHERITED_METHOD" or cfg.helper.mode == "INHERITED"):
        extends = f" extends {simple(cfg.baseClass)}"
        imports.add(cfg.baseClass)
    accessor = []
    if _uses_driver(plan, cfg):
        t = cfg.driver.driverType
        imports.add(DRIVER_IMPORT[t])
        if cfg.driver.mode == "STATIC_METHOD":
            imports.add(cfg.driver.className)
            expr = f"{simple(cfg.driver.className)}.{cfg.driver.methodName}()"
        else:
            expr = f"{cfg.driver.methodName}()"
        accessor = [f"{IND}/** Mevcut framework'ün driver'ı kullanılır; yeni Appium oturumu açılmaz. */",
                    f"{IND}private {t} driver() {{", f"{IND}{IND}return {expr};", f"{IND}}}", ""]
    if cfg.helper.mode == "GENERATED" and any(s["supported"] for s in plan["steps"]):
        imports.add(f"{cfg.helperPackage}.{cfg.helper.className}")
    elif cfg.helper.mode == "STATIC" and any(s["supported"] for s in plan["steps"]):
        imports.add(cfg.helper.className)
    sess = plan["session"]
    doc = [
        "/**",
        f" * AMTS tarafından üretildi — oturum: {comment_safe(sess['name'])} ({sess['id'][:8]}), "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC.",
        f" * Uygulama: {comment_safe(sess['packageName'] or '?')}. Uygulama cihazda zaten açık olmalıdır;",
        " * bu sınıf yeni bir Appium oturumu başlatmaz ve uygulamayı yeniden başlatmaz.",
        " */",
    ]
    return "\n".join([f"package {pkg};", "", _imports_block(pkg, imports), ""] + doc +
                     [f"public class {cls}{extends} {{", ""] + accessor + ["\n\n".join(methods), "}", ""])


def render_locators(plan, cfg):
    steps = [s for s in plan["steps"] if s["selected"] and s["selected"]["strategy"] != "COORDINATES" and s["supported"]]
    if cfg.locatorStorage != "LOCATOR_CLASS" or not steps:
        return None
    body = []
    for s in steps:
        body += [f"{IND}// Adım {s['order']} — {s['action']} · seçili {_loc_comment(s['selected'])}"] + _alt_lines(s, IND)
        body += [f"{IND}public static final By {s['constName']} = {s['selected']['javaExpr']};", ""]
    pkg, cls = cfg.stepsPackage, cfg.locatorClassName
    return "\n".join([f"package {pkg};", "", "import io.appium.java_client.AppiumBy;", "import org.openqa.selenium.By;", "",
                      f"/** AMTS locator'ları — oturum: {comment_safe(plan['session']['name'])}. Gerekirse alternatiflerle değiştirin. */",
                      f"public final class {cls} {{", "", f"{IND}private {cls}() {{", f"{IND}}}", ""] + body + ["}", ""])


HELPER_TEMPLATE = '''package {pkg};

import org.openqa.selenium.By;
import org.openqa.selenium.Rectangle;
import org.openqa.selenium.WebDriver;
import org.openqa.selenium.WebElement;
import org.openqa.selenium.interactions.Interactive;
import org.openqa.selenium.interactions.Pause;
import org.openqa.selenium.interactions.PointerInput;
import org.openqa.selenium.interactions.Sequence;
import org.openqa.selenium.support.ui.WebDriverWait;

import java.time.Duration;
import java.util.Collections;
import java.util.List;

/**
 * AMTS ortak hareket yardımcıları (Appium 2 / W3C Actions). Kendi framework yardımcılarınız varsa
 * Kod Üreteci ayarlarında "Mevcut yardımcı sınıf" seçeneğini kullanın; bu sınıf gerekmez.
 * SCROLL yönü içeriğin hareket yönüdür: DOWN = listenin aşağısını göster (parmak yukarı kayar).
 */
public final class {cls} {{

    public static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds({timeout});

    private {cls}() {{
    }}

    /** Tek bir öğe bulur; birden fazla eşleşmede belirsiz hedefe dokunmamak için hata verir. */
    public static WebElement findUnique(WebDriver driver, By locator) {{
        List<WebElement> found = new WebDriverWait(driver, DEFAULT_TIMEOUT)
                .until(d -> {{
                    List<WebElement> list = d.findElements(locator);
                    return list.isEmpty() ? null : list;
                }});
        if (found.size() > 1) {{
            throw new IllegalStateException("AMTS: " + locator + " " + found.size()
                    + " öğe ile eşleşti; belirsiz hedef kullanılmadı.");
        }}
        return found.get(0);
    }}

    public static void tap(WebDriver driver, By locator) {{
        findUnique(driver, locator).click();
    }}

    public static void longPress(WebDriver driver, By locator, Duration hold) {{
        Rectangle r = findUnique(driver, locator).getRect();
        press(driver, r.getX() + r.getWidth() / 2, r.getY() + r.getHeight() / 2, hold);
    }}

    public static void scroll(WebDriver driver, By container, String direction) {{
        Rectangle r = findUnique(driver, container).getRect();
        int cx = r.getX() + r.getWidth() / 2;
        int cy = r.getY() + r.getHeight() / 2;
        int dx = (int) (r.getWidth() * 0.3);
        int dy = (int) (r.getHeight() * 0.3);
        Duration d = Duration.ofMillis(600);
        switch (direction) {{
            case "DOWN":
                swipe(driver, cx, cy + dy, cx, cy - dy, d);
                break;
            case "UP":
                swipe(driver, cx, cy - dy, cx, cy + dy, d);
                break;
            case "RIGHT":
                swipe(driver, cx + dx, cy, cx - dx, cy, d);
                break;
            case "LEFT":
                swipe(driver, cx - dx, cy, cx + dx, cy, d);
                break;
            default:
                throw new IllegalArgumentException("AMTS: bilinmeyen kaydırma yönü " + direction);
        }}
    }}

    public static void tapAt(WebDriver driver, int x, int y) {{
        press(driver, x, y, Duration.ofMillis(80));
    }}

    public static void longPressAt(WebDriver driver, int x, int y, Duration hold) {{
        press(driver, x, y, hold);
    }}

    public static void swipe(WebDriver driver, int x1, int y1, int x2, int y2, Duration duration) {{
        PointerInput finger = new PointerInput(PointerInput.Kind.TOUCH, "finger");
        Sequence s = new Sequence(finger, 0);
        s.addAction(finger.createPointerMove(Duration.ZERO, PointerInput.Origin.viewport(), x1, y1));
        s.addAction(finger.createPointerDown(PointerInput.MouseButton.LEFT.asArg()));
        s.addAction(finger.createPointerMove(duration, PointerInput.Origin.viewport(), x2, y2));
        s.addAction(finger.createPointerUp(PointerInput.MouseButton.LEFT.asArg()));
        ((Interactive) driver).perform(Collections.singletonList(s));
    }}

    private static void press(WebDriver driver, int x, int y, Duration hold) {{
        PointerInput finger = new PointerInput(PointerInput.Kind.TOUCH, "finger");
        Sequence s = new Sequence(finger, 0);
        s.addAction(finger.createPointerMove(Duration.ZERO, PointerInput.Origin.viewport(), x, y));
        s.addAction(finger.createPointerDown(PointerInput.MouseButton.LEFT.asArg()));
        s.addAction(new Pause(finger, hold));
        s.addAction(finger.createPointerUp(PointerInput.MouseButton.LEFT.asArg()));
        ((Interactive) driver).perform(Collections.singletonList(s));
    }}
}}
'''


def render_helper(cfg):
    return HELPER_TEMPLATE.format(pkg=cfg.helperPackage, cls=cfg.helper.className, timeout=cfg.waitTimeoutSeconds)


def render_spec(plan, cfg) -> str:
    sess = plan["session"]
    lines = [f"# {comment_safe(sess['name']).lstrip('#').strip() or 'AMTS'}", "",
             f"AMTS tarafından üretildi. Oturum: {sess['id']}. Uygulama: {sess['packageName']}.",
             "Ön koşul: Uygulama cihazda açık ve kaydın başladığı ekranda olmalı; senaryo uygulamayı yeniden başlatmaz.", "",
             f"## {cfg.scenarioName}", ""]
    if cfg.tags:
        lines += [f"Tags: {cfg.tags}", ""]
    for s in plan["steps"]:
        text = s["stepText"]
        for p in s["params"]:
            text = text.replace(f"<{p['name']}>", f'"{p["specValue"]}"')
        if not s["supported"]:
            lines.append(f"AMTS UYARI: Adım {s['order']} ({s['action']}) desteklenmiyor; implementasyonu UnsupportedOperationException fırlatır.")
        lines.append(f"* {text}")
    return "\n".join(lines) + "\n"


def render_readme(plan, cfg, files) -> str:
    c, h, d = cfg, cfg.helper, cfg.driver
    sig = "" if h.mode == "GENERATED" else (
        f"\nBeklenen yardımcı metot imzaları ({'static, ' if h.mode == 'STATIC' else 'miras alınan, '}"
        f"{'ilk parametre WebDriver' if h.passDriver else 'driver parametresiz'}):\n"
        f"- `{h.methods.tap}(By)`, `{h.methods.longPress}(By, Duration)`, `{h.methods.scroll}(By, String yön)`\n"
        f"- `{h.methods.tapAt}(int x, int y)`, `{h.methods.longPressAt}(int x, int y, Duration)`, "
        f"`{h.methods.swipe}(int x1, int y1, int x2, int y2, Duration)`\n")
    issues = [f"- Adım {s['order']} [{i['code']}] {i['message']}" for s in plan["steps"] for i in s["issues"] if i["level"] != "info"]
    return "\n".join([
        f"# AMTS Kod Üreteci — {plan['session']['name']}", "",
        "Bu dosyalar mevcut Java + Appium 2 + Gauge projenize eklenmek içindir. Yeni Maven/Gauge projesi,",
        "yeni bağımlılık veya ikinci bir Appium driver'ı oluşturulmaz.", "",
        "## Dosyalar", *[f"- `{f['path']}`" for f in files], "",
        "## Yapılandırma",
        f"- Java {c.javaVersion}, Appium java-client {c.appiumClientVersion} (mevcut bağımlılıklarınız: io.appium:java-client, com.thoughtworks.gauge:gauge-java)",
        f"- Driver: " + (f"`{d.className}.{d.methodName}()`" if d.mode == "STATIC_METHOD" else f"`{c.baseClass}` sınıfından miras alınan `{d.methodName}()`") + f" → `{d.driverType}`",
        f"- Yardımcılar: " + {"GENERATED": f"üretilen `{c.helperPackage}.{h.className}`", "STATIC": f"mevcut `{h.className}` (static)",
                              "INHERITED": f"`{c.baseClass}` içindeki metotlar"}[h.mode],
        f"- Locator saklama: {'ayrı sınıf `' + c.locatorClassName + '`' if c.locatorStorage == 'LOCATOR_CLASS' else 'step metodu içinde'}",
        f"- Gauge adım ön eki: `{c.stepPrefix}` (step metinlerinin projenizdeki diğer adımlarla çakışmaması için)", sig,
        "## Uyarılar ve desteklenmeyen adımlar", *(issues or ["- Yok"]), "",
        "## Hassas veriler",
        "Şifre/OTP gibi maskeli değerler koda yazılmaz. Bu adımlar test verisi anahtarı (ör. `AMTS_PIN`) ile üretilir;",
        "anahtarı kendi güvenli test verisi mekanizmanızla çözün.", ""])
