# Read-only external tests for the Code Generator (Kod Üreteci) API against the public preview URL.
# Safe: codegen endpoints never mutate session data. No replays/heartbeats.
import io
import os
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/codegen"
D3 = "976206fa-7e7d-4da1-b8c8-399f2d24f955"
MIX = "fa049f6e-4d45-47a3-a87e-5c29140ffbf5"
INPUT = "251832fb-ff5a-4a3e-bdea-c5c8b6f997cf"
T = 120


def gen(sid, config=None):
    r = requests.post(f"{API}/generate", json={"sessionId": sid, "config": config or {}}, timeout=T)
    assert r.status_code == 200, r.text
    return r.json()


def by_role(res, role):
    return next((f for f in res["files"] if f["role"] == role), None)


@pytest.fixture(scope="module")
def d3():
    return gen(D3)


# --- listing / defaults
def test_sessions_list():
    r = requests.get(f"{API}/sessions", timeout=30)
    assert r.status_code == 200
    rows = {s["id"]: s for s in r.json()}
    assert rows[D3]["name"] == "DENEME-3" and rows[D3]["actions"] == {"TAP": 1} and rows[D3]["stepCount"] == 1
    assert "INPUT_TEXT" in rows[INPUT]["actions"]
    assert all("_id" not in s for s in r.json())


def test_defaults():
    d = requests.get(f"{API}/defaults", timeout=30).json()
    assert d["stepsPackage"] == "com.example.steps" and d["locatorStorage"] == "LOCATOR_CLASS"
    assert d["driver"]["mode"] == "STATIC_METHOD" and d["helper"]["mode"] == "GENERATED"


# --- generate DENEME-3 (acceptance)
def test_generate_d3_verified(d3):
    assert d3["validation"]["status"] == "VERIFIED"
    assert {c["id"]: c["status"] for c in d3["validation"]["checks"]} == {"gauge_match": "PASS", "step_collisions": "PASS", "javac": "PASS"}
    paths = [f["path"] for f in d3["files"]]
    assert "specs/deneme_3.spec" in paths
    assert "src/test/java/com/example/steps/Deneme3Steps.java" in paths
    assert "src/test/java/com/example/steps/Deneme3Locators.java" in paths
    assert "src/test/java/com/example/steps/amts/AmtsGestures.java" in paths
    assert "AMTS_INTEGRATION.md" in paths


def test_d3_content(d3):
    spec, steps, loc = by_role(d3, "spec")["content"], by_role(d3, "steps")["content"], by_role(d3, "locators")["content"]
    assert "* DENEME-3 Adım 1 - TRANSFER öğesine dokun" in spec
    assert '@Step("DENEME-3 Adım 1 - TRANSFER öğesine dokun")' in steps
    assert 'AppiumBy.id("com.amts.sampleapp:id/transferButton")' in loc
    allc = "\n".join(f["content"] for f in d3["files"])
    assert "new AndroidDriver" not in allc and "activateApp" not in allc
    assert "DriverManager.getDriver()" in steps


# --- mixed TAP/SCROLL/LONG_PRESS and INPUT_TEXT session
def test_generate_mixed_verified():
    res = gen(MIX)
    assert res["validation"]["status"] == "VERIFIED"
    acts = {s["action"] for s in res["plan"]["steps"]}
    assert {"TAP", "SCROLL", "LONG_PRESS"} <= acts
    steps = by_role(res, "steps")["content"]
    assert "Duration.ofMillis" in steps and "scroll(" in steps


def test_generate_input_text_masked():
    res = gen(INPUT)
    assert res["validation"]["status"] == "VERIFIED"
    uns = [s for s in res["plan"]["steps"] if not s["supported"]]
    assert uns and all(s["status"] == "UNSUPPORTED" for s in uns)
    spec, steps = by_role(res, "spec")["content"], by_role(res, "steps")["content"]
    assert '"AMTS_PININPUT"' in spec
    assert "UnsupportedOperationException" in steps
    assert "AMTS UYARI" in spec
    assert "[MASKED]" not in "\n".join(f["content"] for f in res["files"])


# --- validate edits
def test_validate_broken_java(d3):
    files = [dict(f) for f in d3["files"]]
    s = next(f for f in files if f["role"] == "steps")
    idx = s["content"].rfind("}")
    s["content"] = s["content"][:idx] + s["content"][idx + 1:]
    r = requests.post(f"{API}/validate", json={"sessionId": D3, "config": {}, "files": files}, timeout=T)
    assert r.status_code == 200
    v = r.json()
    assert v["status"] == "FAILED"
    jc = next(c for c in v["checks"] if c["id"] == "javac")
    assert jc["status"] == "FAIL" and jc["details"]


def test_validate_renamed_spec_step(d3):
    files = [dict(f) for f in d3["files"]]
    sp = next(f for f in files if f["role"] == "spec")
    sp["content"] = sp["content"].replace("öğesine dokun", "öğesine tıkla")
    v = requests.post(f"{API}/validate", json={"sessionId": D3, "config": {}, "files": files}, timeout=T).json()
    assert v["status"] == "FAILED"
    assert next(c for c in v["checks"] if c["id"] == "gauge_match")["status"] == "FAIL"


def test_validate_bad_path(d3):
    files = [dict(f) for f in d3["files"]] + [{"path": "../x.java", "content": "class X{}"}]
    r = requests.post(f"{API}/validate", json={"sessionId": D3, "config": {}, "files": files}, timeout=T)
    assert r.status_code == 422


def test_invalid_config_422():
    r = requests.post(f"{API}/generate", json={"sessionId": D3, "config": {"stepsPackage": "com.class.x"}}, timeout=T)
    assert r.status_code == 422


def test_inherited_without_base_422():
    r = requests.post(f"{API}/generate", json={"sessionId": D3, "config": {"driver": {"mode": "INHERITED_METHOD"}}}, timeout=T)
    assert r.status_code == 422


def test_inherited_inline_config():
    cfg = {"baseClass": "com.bank.steps.BaseSteps", "locatorStorage": "INLINE",
           "driver": {"mode": "INHERITED_METHOD"}, "helper": {"mode": "INHERITED"}}
    res = gen(D3, cfg)
    assert res["validation"]["status"] == "VERIFIED"
    roles = {f["role"] for f in res["files"]}
    assert "helper" not in roles and "locators" not in roles
    steps = by_role(res, "steps")["content"]
    assert "extends BaseSteps" in steps and "AppiumBy.id(" in steps


def test_unknown_session_404():
    r = requests.post(f"{API}/generate", json={"sessionId": "does-not-exist", "config": {}}, timeout=T)
    assert r.status_code == 404


# --- zip
def test_zip(d3):
    r = requests.post(f"{API}/zip", json={"sessionId": D3, "config": {}, "files": d3["files"]}, timeout=T)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/zip")
    assert r.headers["X-AMTS-Validation"] == "VERIFIED"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "AMTS_VALIDATION.md" in names and "specs/deneme_3.spec" in names
    assert "VERIFIED" in z.read("AMTS_VALIDATION.md").decode()


# --- regression: JSON export includes action
def test_export_has_action():
    r = requests.get(f"{BASE_URL}/api/sessions/{D3}/export", timeout=30)
    assert r.status_code == 200
    st = r.json()["steps"]
    assert st and st[0]["action"] == "TAP"


# --- iteration 7: javac path/package/class match + Java 21 partial
def _validate(files, config=None):
    r = requests.post(f"{API}/validate", json={"sessionId": D3, "config": config or {}, "files": files}, timeout=T)
    assert r.status_code == 200, r.text
    return r.json()


def test_validate_renamed_class_fails(d3):
    files = [dict(f) for f in d3["files"]]
    s = next(f for f in files if f["role"] == "steps")
    assert "public class Deneme3Steps" in s["content"]
    s["content"] = s["content"].replace("public class Deneme3Steps", "public class OtherName")
    v = _validate(files)
    assert v["status"] == "FAILED"
    jc = next(c for c in v["checks"] if c["id"] == "javac")
    assert jc["status"] == "FAIL"
    assert any("dosya yoluyla eşleşmiyor" in d for d in jc["details"]), jc


def test_validate_changed_package_fails(d3):
    files = [dict(f) for f in d3["files"]]
    s = next(f for f in files if f["role"] == "steps")
    s["content"] = s["content"].replace("package com.example.steps;", "package com.other;", 1)
    v = _validate(files)
    assert v["status"] == "FAILED"
    jc = next(c for c in v["checks"] if c["id"] == "javac")
    assert jc["status"] == "FAIL" and any("dosya yoluyla eşleşmiyor" in d for d in jc["details"]), jc


def test_validate_unchanged_still_verified(d3):
    assert _validate([dict(f) for f in d3["files"]])["status"] == "VERIFIED"


def test_java21_partial_not_verified():
    res = gen(D3, {"javaVersion": "21"})
    jc = next(c for c in res["validation"]["checks"] if c["id"] == "javac")
    assert jc["status"] == "PARTIAL", jc
    assert res["validation"]["status"] == "NOT_VERIFIED"
    v = _validate(res["files"], {"javaVersion": "21"})
    assert v["status"] == "NOT_VERIFIED"
    z = requests.post(f"{API}/zip", json={"sessionId": D3, "config": {"javaVersion": "21"}, "files": res["files"]}, timeout=T)
    assert z.status_code == 200 and z.headers["X-AMTS-Validation"] == "NOT_VERIFIED"


def test_422_message_has_value_error_prefix_in_raw():
    # The frontend strips 'Value error, '; record the raw backend message shape
    r = requests.post(f"{API}/generate", json={"sessionId": D3, "config": {"driver": {"mode": "INHERITED_METHOD"}}}, timeout=T)
    assert r.status_code == 422
    body = r.json()
    print("422 body:", body)
