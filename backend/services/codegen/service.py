import io
import json
import re
import zipfile
from core.errors import AppError
from services.codegen.config import CodegenConfig
from services.codegen.planner import build_plan
from services.codegen import render
from services.codegen.validate import validate_files

MAX_FILES, MAX_BYTES = 20, 1_000_000
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-.]+)*\.(java|spec|md|feature|txt)$")


async def generate(session_id: str, cfg: CodegenConfig) -> dict:
    plan = await build_plan(session_id, cfg)
    rc = CodegenConfig(**plan["config"])
    files = [{"path": f"{rc.specDir}/{rc.specFileName}", "language": "gauge", "role": "spec", "content": render.render_spec(plan, rc)},
             {"path": render._path(rc, rc.stepsPackage, rc.stepClassName), "language": "java", "role": "steps",
              "content": render.render_steps(plan, rc)}]
    loc = render.render_locators(plan, rc)
    if loc:
        files.append({"path": render._path(rc, rc.stepsPackage, rc.locatorClassName), "language": "java", "role": "locators", "content": loc})
    if rc.helper.mode == "GENERATED" and plan["summary"]["supported"]:
        files.append({"path": render._path(rc, rc.helperPackage, rc.helper.className), "language": "java", "role": "helper",
                      "content": render.render_helper(rc)})
    files.append({"path": "AMTS_INTEGRATION.md", "language": "markdown", "role": "readme",
                  "content": render.render_readme(plan, rc, files)})
    return {"plan": plan, "files": files, "validation": await validate_files(files, rc)}


def check_files(files: list):
    if not files or len(files) > MAX_FILES:
        raise AppError("CODEGEN_FILES_INVALID", f"1-{MAX_FILES} dosya gönderilmeli.", 422)
    if sum(len(f["content"].encode()) for f in files) > MAX_BYTES:
        raise AppError("CODEGEN_FILES_TOO_LARGE", "Dosyaların toplam boyutu 1 MB'ı aşamaz.", 422)
    paths = [f["path"] for f in files]
    bad = [p for p in paths if not _SAFE_PATH.match(p) or ".." in p]
    if bad or len(set(paths)) != len(paths):
        raise AppError("CODEGEN_PATH_INVALID", f"Geçersiz veya tekrar eden dosya yolu: {', '.join(bad) or 'tekrar'}", 422)


def report_safe(validation: dict) -> dict:
    """Compiler output echoes source lines; reports keep only 'file:line: message' with string literals masked."""
    checks = []
    for c in validation["checks"]:
        details = c["details"]
        if c["id"] in ("javac", "java_syntax"):
            details = [d for d in details if re.match(r"^[\w/.\-]+:\d+: ", d)]
        details = [re.sub(r'"(?:[^"\\\n]|\\.)*"', '"…"', d) for d in details]
        if c["id"] in ("feature_match", "step_collisions", "sensitive_data"):
            details = [re.sub(r"'.*'", "'…'", d) for d in details]
        checks.append({**c, "details": details})
    return {**validation, "checks": checks}


def build_zip(files: list, validation: dict, session_name: str) -> bytes:
    buf = io.BytesIO()
    validation = report_safe(validation)
    status_tr = {"VERIFIED": "DOĞRULANDI", "FAILED": "BAŞARISIZ", "NOT_VERIFIED": "DOĞRULANMADI",
                 "STRUCTURE_VERIFIED": "YAPISAL OLARAK DOĞRULANDI (framework derlemesi doğrulanmadı)"}[validation["status"]]
    report_note = "Hassas veriler (şifre/PIN/OTP) bu rapora ve dosyalara yazılmaz; derleyici çıktısında kaynak satırları ve metin sabitleri gizlenir."
    report = [f"# AMTS doğrulama raporu — {session_name}", "", f"Durum: **{status_tr}** ({validation['status']})",
              f"İçerik özeti (sha256): `{validation['contentHash']}`", "",
              "Bu rapor ZIP içindeki dosyaların tam olarak bu hâli için sunucuda üretildi.", report_note, ""]
    for c in validation["checks"]:
        report += [f"## {c['id']}: {c['status']}", c["summary"], *[f"- {d}" for d in c["details"]], ""]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.writestr(f["path"], f["content"])
        z.writestr("AMTS_VALIDATION.md", "\n".join(report))
        z.writestr("amts-validation.json", json.dumps(validation, ensure_ascii=False, indent=2))
    return buf.getvalue()
