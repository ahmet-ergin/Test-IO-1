# Read-only external tests for the Cucumber + POM codegen profile (/api/codegen/pom/*) against the public preview URL.
# Safe: codegen endpoints never mutate session data. No replays/heartbeats. Only fictional names (org.acme/com.example).
import io
import os
import re
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/codegen"
D3 = "976206fa-7e7d-4da1-b8c8-399f2d24f955"
INPUT = "251832fb-ff5a-4a3e-bdea-c5c8b6f997cf"
MIX = "fa049f6e-4d45-47a3-a87e-5c29140ffbf5"
T = 120


def post(path, body):
    return requests.post(f"{API}{path}", json=body, timeout=T)


def gen(sid, config=None):
    r = post("/pom/generate", {"sessionId": sid, "config": config or {}})
    assert r.status_code == 200, r.text
    return r.json()


def role(res, name):
    return next((f for f in res["files"] if f["role"] == name), None)


def check(v, cid):
    return next(c for c in v["checks"] if c["id"] == cid)


@pytest.fixture(scope="module")
def d3():
    return gen(D3)


# --- defaults
def test_pom_defaults_fictional():
    r = requests.get(f"{API}/pom/defaults", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["javaVersion"] == "8" and d["stepAnnotation"] == "io.cucumber.java.en.And"
    assert d["stepBaseClass"].startswith("com.example.") and d["locatorAnnotation"].startswith("com.example.")
    assert d["actionTemplates"]["TAP"] == "{element}.click();"
    assert d["actionTemplates"]["SCROLL_DOWN"] == "{app}.swipeUp();" and d["actionTemplates"]["BACK"] == "{app}.navigateToBack();"
    assert d["secretValueTemplate"] == "System.getenv({key})"


# --- plan
@pytest.mark.parametrize("sid", [D3, INPUT, MIX])
def test_pom_plan(sid):
    r = post("/pom/plan", {"sessionId": sid, "config": {}})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["summary"]["total"] == len(p["steps"]) > 0
    for e in p["elements"]:
        assert e["annotation"].startswith("@FindBy(")
    assert set(p["classes"]) == {"step", "iface", "android"}


# --- generate: three layers + feature, STRUCTURE_VERIFIED, framework_compile NOT_VERIFIED
@pytest.mark.parametrize("sid", [D3, INPUT, MIX])
def test_pom_generate_structure_verified(sid):
    res = gen(sid)
    v = res["validation"]
    assert v["status"] == "STRUCTURE_VERIFIED", v
    assert check(v, "framework_compile")["status"] == "NOT_VERIFIED"
    assert check(v, "java_syntax")["status"] == "PASS"
    roles = [f["role"] for f in res["files"]]
    assert [r for r in roles if r != "secrets"] == ["feature", "steps", "contract", "android", "readme"]
    for f in res["files"]:
        if f["language"] == "java" and f["role"] != "secrets":
            assert f["path"].startswith("src/test/java/")
            assert "// <amts:members>" in f["content"] and "// </amts:members>" in f["content"]
    assert role(res, "feature")["path"].startswith("src/test/resources/features/")


def test_pom_d3_layers(d3):
    st, ct, an = role(d3, "steps")["content"], role(d3, "contract")["content"], role(d3, "android")["content"]
    cls = d3["plan"]["classes"]
    assert "extends BaseTest" in st and "import io.cucumber.java.en.And;" in st and "@And(" in st
    assert not re.search(r"\bnew\s+\w+\s*\(", st) and "@FindBy" not in st and "mobileApp." not in st
    assert "@PageModel" in ct and f"public interface {cls['iface']}" in ct and "{\n        " not in ct.split("interface", 1)[1]
    assert f"extends BaseModel implements {cls['iface']}" in an and "@FindBy(" in an and "IMobileElement" in an
    assert ".click();" in an
    feat = role(d3, "feature")["content"]
    assert feat.startswith("# language: tr") and "Diyelim ki" in feat


def test_pom_input_secret(tmp_path):
    res = gen(INPUT)
    st, an, feat = role(res, "steps")["content"], role(res, "android")["content"], role(res, "feature")["content"]
    assert "AmtsSecureData.require(key)" in st
    assert ".sendKeys(" in an and ".clear();" in an
    assert "AMTS_" in feat
    assert "•" not in st + an + feat  # mask char must not leak


def test_pom_mix_scroll_longpress():
    res = gen(MIX)
    an = role(res, "android")["content"]
    actions = {s["action"] for s in res["plan"]["steps"]}
    if "SCROLL" in actions:
        assert "mobileApp.swipeUp();" in an or "mobileApp.swipeDown();" in an or "UnsupportedOperationException" in an
    if "LONG_PRESS" in actions:
        assert "mobileApp.longPressOnElement(" in an


# --- custom config: empty TAP template -> UNSUPPORTED + throw, still STRUCTURE_VERIFIED
def test_pom_tap_unsupported_and_custom_base():
    res = gen(D3, {"stepBaseClass": "org.acme.fw.StepBase", "actionTemplates": {"TAP": ""}})
    v = res["validation"]
    assert v["status"] == "STRUCTURE_VERIFIED", v
    assert res["plan"]["steps"][0]["status"] == "UNSUPPORTED"
    an, st = role(res, "android")["content"], role(res, "steps")["content"]
    assert "throw new UnsupportedOperationException(" in an and ".click()" not in an
    assert "import org.acme.fw.StepBase;" in st and "extends StepBase" in st
    assert "desteklenmiyor" in role(res, "feature")["content"]


# --- validate: broken implements -> FAILED; original -> STRUCTURE_VERIFIED
def test_pom_validate_broken_and_ok(d3):
    files = d3["files"]
    ok = post("/pom/validate", {"sessionId": D3, "config": {}, "files": files})
    assert ok.status_code == 200 and ok.json()["status"] == "STRUCTURE_VERIFIED"
    assert ok.json()["contentHash"] == d3["validation"]["contentHash"]
    iface = d3["plan"]["classes"]["iface"]
    broken = [dict(f, content=f["content"].replace(f" implements {iface}", "")) if f["role"] == "android" else f for f in files]
    r = post("/pom/validate", {"sessionId": D3, "config": {}, "files": broken})
    v = r.json()
    assert v["status"] == "FAILED"
    assert check(v, "structure")["status"] == "FAIL" and check(v, "structure")["details"]


def test_pom_collision_with_existing(d3):
    text = d3["plan"]["methods"][0]["stepText"]
    r = post("/pom/validate", {"sessionId": D3, "config": {"existingStepTexts": [text]}, "files": d3["files"]})
    v = r.json()
    assert check(v, "step_collisions")["status"] == "FAIL" and v["status"] == "FAILED"


# --- zip
def test_pom_zip(d3):
    r = post("/pom/zip", {"sessionId": D3, "config": {}, "files": d3["files"]})
    assert r.status_code == 200
    assert r.headers["X-AMTS-Validation"] == "STRUCTURE_VERIFIED"
    assert "cucumber-pom.zip" in r.headers["Content-Disposition"]
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert any(re.search(r"src/test/java/.+\.java$", n) for n in names)
    assert any(re.search(r"src/test/resources/features/.+\.feature$", n) for n in names)
    assert any(n.endswith("AMTS_VALIDATION.md") for n in names)


# --- invalid config -> 422
@pytest.mark.parametrize("cfg", [
    {"stepClassPattern": "Steps"},
    {"stepBaseClass": "BaseTest"},
    {"actionTemplates": {"TAP": "{element}.click({foo});"}},
    {"appExpression": "a.b()"},
])
def test_pom_invalid_config_422(cfg):
    r = post("/pom/plan", {"sessionId": D3, "config": cfg})
    assert r.status_code == 422, r.text


# --- Gauge regression
def test_gauge_still_verified():
    r = post("/generate", {"sessionId": D3, "config": {}})
    assert r.status_code == 200
    v = r.json()["validation"]
    assert v["status"] == "VERIFIED"
