"""Validation of generated/edited files: Gauge step <-> @Step 1:1 matching, collisions, and javac compilation."""
import asyncio
import hashlib
import re
import shutil
import tempfile
from pathlib import Path
from services.codegen.javautil import simple, pkg_of

LIB_DIR = Path(__file__).resolve().parents[2] / "codegen_lib"
TOOLCHAIN = "io.appium:java-client 9.5.0, selenium 4.34.0, gauge-java 0.11.1"
_STEP_ANN = re.compile(r'@Step\s*\(\s*(\{.*?\}|"(?:[^"\\\n]|\\.)*")\s*\)\s*public\s+void\s+(\w+)\s*\(([^)]*)\)', re.S)
_JSTR = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
_PKG = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)
_CLS = re.compile(r"^\s*public\s+(?:final\s+|abstract\s+)*(?:class|interface|enum)\s+(\w+)", re.M)


def content_hash(files) -> str:
    h = hashlib.sha256()
    for f in sorted(files, key=lambda x: x["path"]):
        h.update(f["path"].encode() + b"\0" + f["content"].encode() + b"\0")
    return h.hexdigest()


def _unescape(s: str) -> str:
    s = re.sub(r"\\u+([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\\([0-7]{1,3})", lambda m: chr(int(m.group(1), 8)), s)
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}.get(m.group(1), m.group(1)), s)


def norm_impl(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "{}", text)).strip()


def norm_spec(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'"[^"]*"|<[^>]*>', "{}", text)).strip()


def spec_steps(content: str):
    return [(i + 1, m.group(1).strip()) for i, line in enumerate(content.splitlines())
            if (m := re.match(r"^\s*\*\s+(.+)$", line))]


def java_steps(content: str):
    out = []
    for m in _STEP_ANN.finditer(content):
        params = [p for p in m.group(3).split(",") if p.strip()]
        for t in _JSTR.findall(m.group(1)):
            out.append({"text": _unescape(t), "method": m.group(2), "paramCount": len(params)})
    return out


def check_gauge(files, existing):
    specs = [f for f in files if f["path"].endswith(".spec")]
    impls = [dict(s, file=f["path"]) for f in files if f["path"].endswith(".java") for s in java_steps(f["content"])]
    errors, by_norm = [], {}
    for s in impls:
        by_norm.setdefault(norm_impl(s["text"]), []).append(s)
    for k, v in by_norm.items():
        if len(v) > 1:
            errors.append(f"Aynı step metni birden fazla metotta tanımlı: '{v[0]['text']}' ({', '.join(x['method'] for x in v)})")
        if v[0]["paramCount"] != k.count("{}"):
            errors.append(f"{v[0]['method']}: parametre sayısı ({v[0]['paramCount']}) step metnindeki parametrelerle ({k.count('{}')}) eşleşmiyor.")
    used = set()
    total = 0
    for f in specs:
        for line, text in spec_steps(f["content"]):
            total += 1
            n = norm_spec(text)
            if n not in by_norm:
                errors.append(f"{f['path']}:{line} — '{text}' için step implementation bulunamadı.")
            used.add(n)
    for k, v in by_norm.items():
        if k not in used:
            errors.append(f"{v[0]['method']} — '{v[0]['text']}' spec dosyasında kullanılmıyor (birebir eşleşme yok).")
    ex = {norm_impl(norm_spec(t)) for t in existing if t.strip()}
    collisions = [v[0]["text"] for k, v in by_norm.items() if k in ex]
    if not specs:
        errors.append("Hiç .spec dosyası yok.")
    return {"id": "gauge_match", "status": "PASS" if not errors else "FAIL",
            "summary": f"{total} spec adımı, {len(impls)} @Step implementasyonu", "details": errors[:50]}, \
           {"id": "step_collisions", "status": "FAIL" if collisions else "PASS",
            "summary": f"{len(ex)} mevcut step metni ile karşılaştırıldı" if ex else "Mevcut step metni girilmedi; yalnızca üretilen dosyalar içinde kontrol edildi",
            "details": [f"Mevcut projede zaten var: '{c}'" for c in collisions]}


def _stubs(cfg, defined: set) -> dict:
    """Minimal stand-ins for the user's framework classes, only for compile validation (never exported)."""
    t = {"AppiumDriver": "io.appium.java_client.AppiumDriver", "AndroidDriver": "io.appium.java_client.android.AndroidDriver",
         "WebDriver": "org.openqa.selenium.WebDriver"}[cfg.driver.driverType]
    members = {}
    if cfg.driver.mode == "STATIC_METHOD":
        members.setdefault(cfg.driver.className, []).append(f"public static {t} {cfg.driver.methodName}() {{ return null; }}")
    else:
        members.setdefault(cfg.baseClass, []).append(f"protected {t} {cfg.driver.methodName}() {{ return null; }}")
    h = cfg.helper
    if h.mode in ("STATIC", "INHERITED"):
        owner, mod = (h.className, "public static") if h.mode == "STATIC" else (cfg.baseClass, "protected")
        d = "org.openqa.selenium.WebDriver driver, " if h.passDriver else ""
        m = h.methods
        sigs = [(m.tap, "org.openqa.selenium.By l"), (m.longPress, "org.openqa.selenium.By l, java.time.Duration h"),
                (m.scroll, "org.openqa.selenium.By l, String dir"), (m.tapAt, "int x, int y"),
                (m.longPressAt, "int x, int y, java.time.Duration h"), (m.swipe, "int a, int b, int c, int e, java.time.Duration h")]
        members.setdefault(owner, []).extend(f"{mod} void {n}({d}{a}) {{ }}" for n, a in sigs)
    if cfg.baseClass and cfg.baseClass not in members and (cfg.driver.mode == "INHERITED_METHOD" or h.mode == "INHERITED"):
        members[cfg.baseClass] = []
    out = {}
    for fq, ms in members.items():
        if fq in defined:
            continue
        uniq = list(dict.fromkeys(ms))
        out[fq] = f"package {pkg_of(fq)};\n\npublic class {simple(fq)} {{\n    " + "\n    ".join(uniq) + "\n}\n"
    return out


_javac_version = None
_javac_slots = asyncio.Semaphore(2)


async def _run(*args, timeout=90):
    p = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
    except asyncio.TimeoutError:
        p.kill()
        return -1, "javac zaman aşımı"
    return p.returncode, out.decode(errors="replace")


async def check_javac(files, cfg):
    global _javac_version
    javac = shutil.which("javac")
    jars = sorted(LIB_DIR.glob("*.jar")) if LIB_DIR.exists() else []
    if not javac or not jars:
        return {"id": "javac", "status": "SKIPPED", "summary": "Bu sunucuda javac veya doğrulama kütüphaneleri yok; derleme doğrulanmadı.", "details": []}
    if _javac_version is None:
        _, v = await _run(javac, "-version", timeout=20)
        m = re.search(r"(\d+)", v)
        _javac_version = int(m.group(1)) if m else 11
    release = cfg.javaVersion if int(cfg.javaVersion) <= _javac_version else str(_javac_version)
    note = "" if release == cfg.javaVersion else f" (Java {cfg.javaVersion} seçildi; sunucudaki javac en fazla --release {release} destekliyor)"
    java_files = [f for f in files if f["path"].endswith(".java")]
    path_errors = []
    for f in java_files:
        pkg = (_PKG.search(f["content"]) or [None, ""])[1]
        cls = (_CLS.search(f["content"]) or [None, None])[1]
        expected = "/".join([*pkg.split("."), f"{cls}.java"]) if pkg else f"{cls}.java"
        if not cls or not f["path"].endswith("/" + expected) and f["path"] != expected:
            path_errors.append(f"{f['path']}: package/sınıf adı ({pkg or '-'}.{cls or '?'}) dosya yoluyla eşleşmiyor; beklenen yol sonu '{expected}'.")
    if path_errors:
        return {"id": "javac", "status": "FAIL", "summary": "Dosya yolu ile package/sınıf adı uyumsuz; gerçek projede derlenmez.", "details": path_errors}
    defined = set()
    with tempfile.TemporaryDirectory(prefix="amts-codegen-") as tmp:
        root = Path(tmp)
        srcs = []
        for i, f in enumerate(java_files):
            pkg = (_PKG.search(f["content"]) or [None, ""])[1]
            cls = (_CLS.search(f["content"]) or [None, Path(f["path"]).stem])[1]
            defined.add(f"{pkg}.{cls}" if pkg else cls)
            p = root / "src" / f["path"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f["content"], encoding="utf-8")
            srcs.append((p, f["path"]))
        stubs = _stubs(cfg, defined)
        for fq, code in stubs.items():
            p = root / "stubs" / (fq.replace(".", "/") + ".java")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(code, encoding="utf-8")
        all_src = [str(p) for p, _ in srcs] + [str(root / "stubs" / (fq.replace(".", "/") + ".java")) for fq in stubs]
        if not all_src:
            return {"id": "javac", "status": "FAIL", "summary": "Derlenecek Java dosyası yok.", "details": []}
        cp = ":".join(str(j) for j in jars)
        async with _javac_slots:
            code, out = await _run(javac, "--release", release, "-encoding", "UTF-8", "-proc:none", "-nowarn",
                                   "-d", str(root / "out"), "-cp", cp, *all_src)
        for p, orig in srcs:
            out = out.replace(str(p), orig)
        out = out.replace(str(root) + "/", "")
    stub_note = f" Framework sınıfları için derleme amaçlı stub kullanıldı: {', '.join(stubs)}." if stubs else ""
    lines = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith("Note:")]
    status = ("PASS" if release == cfg.javaVersion else "PARTIAL") if code == 0 else "FAIL"
    return {"id": "javac", "status": status,
            "summary": f"javac --release {release} ile {len(java_files)} dosya derlendi ({TOOLCHAIN}).{note}{stub_note}"
            if code == 0 else f"Derleme hatası (javac --release {release}).{stub_note}",
            "details": lines[:40] if code != 0 else [], "stubs": list(stubs)}


async def validate_files(files, cfg) -> dict:
    gauge, coll = check_gauge(files, cfg.existingStepTexts)
    javac = await check_javac(files, cfg)
    checks = [gauge, coll, javac]
    if any(c["status"] == "FAIL" for c in checks):
        status = "FAILED"
    elif javac["status"] != "PASS":  # SKIPPED or PARTIAL (compiled only for a lower --release)
        status = "NOT_VERIFIED"
    else:
        status = "VERIFIED"
    return {"status": status, "contentHash": content_hash(files), "checks": checks}
