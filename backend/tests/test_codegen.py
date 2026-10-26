import io
import uuid
import zipfile
from datetime import datetime, timezone
from conftest import device, heartbeat
from services.codegen.javautil import java_str, comment_safe, gauge_text
from services.codegen.validate import check_gauge

PKG = "com.amts.sampleapp"
SERIAL = "CODEGEN-DEV-1"
AGENT = "agent-codegen"


def _el(rid=None, text=None, cls="android.widget.Button", desc=None, password=False, hint=None):
    return {"resourceId": rid, "text": text, "className": cls, "contentDesc": desc, "password": password, "hint": hint,
            "bounds": [0, 0, 100, 100], "clickable": True, "enabled": True}


def _ev(sid, seq, action, element=None, coords=None, **extra):
    return {"eventId": str(uuid.uuid4()), "sessionId": sid, "sequence": seq, "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action, "deviceId": SERIAL, "packageName": PKG, "activity": "com.amts.sampleapp.HomeActivity",
            "captureSource": "HYBRID", "confidence": 0.95, "uncertain": False, "limitations": [],
            "element": element, "coordinates": coords, **extra}


def _session(client, token, build):
    h = {"X-Agent-Token": token}
    heartbeat(client, token, [device(SERIAL)], agent_id=AGENT)
    sid = client.post("/api/sessions", json={"deviceSerial": SERIAL, "packageFilter": PKG, "name": "DENEME-3"}).json()["id"]
    heartbeat(client, token, [device(SERIAL)], agent_id=AGENT)
    client.post(f"/api/agent/sessions/{sid}/state", headers=h, json={"status": "RECORDING", "packageName": PKG})
    evs = build(sid)
    assert client.post(f"/api/agent/sessions/{sid}/events", headers=h, json={"events": evs}).json()["accepted"] == len(evs)
    client.post(f"/api/sessions/{sid}/stop")
    heartbeat(client, token, [device(SERIAL)], agent_id=AGENT)
    client.post(f"/api/agent/sessions/{sid}/state", headers=h, json={"status": "COMPLETED"})
    client.patch(f"/api/sessions/{sid}", json={"saved": True, "name": "DENEME-3"})
    return sid


def _rich(sid):
    return [
        _ev(sid, 1, "TAP", _el("com.amts.sampleapp:id/transferButton", "TRANSFER"), {"x": 10, "y": 20}),
        _ev(sid, 2, "LONG_PRESS", _el("com.amts.sampleapp:id/longPressButton", "LONG PRESS ME", desc="long_press_target"),
            {"x": 50, "y": 60}, durationMs=1200),
        _ev(sid, 3, "SCROLL", _el("com.amts.sampleapp:id/itemList", None, "android.widget.ListView"),
            {"x": 500, "y": 1500}, endCoordinates={"x": 500, "y": 600}),
        _ev(sid, 4, "INPUT_TEXT", _el("com.amts.sampleapp:id/pinInput", None, "android.widget.EditText", password=True, hint="PIN"),
            None, inputValue={"masked": True, "value": None, "length": 4, "reason": "PASSWORD_FIELD"}),
        _ev(sid, 5, "BACK", None, None),
        _ev(sid, 6, "TAP", _el("com.amts.sampleapp:id/q", 'Say "hi" \\ <now>\u00e7'), {"x": 1, "y": 2}),
    ]


def test_java_string_escaping():
    assert java_str('a"b\\c\nd\te\x01') == '"a\\"b\\\\c\\nd\\te\\001"'
    assert java_str("ç", ascii_only=True) == '"\\u00e7"'
    assert java_str("\U0001F600", ascii_only=True) == '"\\ud83d\\ude00"'
    assert "\n" not in comment_safe("x\ny") and comment_safe("\\u000a") == "\\\\u000a"
    assert gauge_text('a "b" <c>') == "a b c"


def test_gauge_matcher_detects_mismatch():
    spec = {"path": "specs/a.spec", "content": "# A\n## S\n* adım bir\n* adım \"x\" iki\n"}
    java = {"path": "src/A.java", "content": '@Step("adım bir")\npublic void a() {}\n@Step("adım <p> iki")\npublic void b(String p) {}\n'}
    g, c = check_gauge([spec, java], ["adım <q> iki"])
    assert g["status"] == "PASS" and c["status"] == "FAIL"
    g, _ = check_gauge([dict(spec, content=spec["content"] + "* yok\n"), java], [])
    assert g["status"] == "FAIL" and any("yok" in d for d in g["details"])
    g, _ = check_gauge([spec, dict(java, content=java["content"].replace("b(String p)", "b()"))], [])
    assert g["status"] == "FAIL"


def test_export_includes_action(client, token):
    sid = _session(client, token, _rich)
    steps = client.get(f"/api/sessions/{sid}/export").json()["steps"]
    assert [s["action"] for s in steps] == ["TAP", "LONG_PRESS", "SCROLL", "INPUT_TEXT", "BACK", "TAP"]


def test_plan_and_generate_default_verified(client, token):
    sid = _session(client, token, _rich)
    plan = client.post("/api/codegen/plan", json={"sessionId": sid}).json()
    st = plan["steps"]
    assert [s["status"] for s in st][:2] == ["OK", "OK"] and st[2]["direction"] == "DOWN"
    assert st[1]["selected"]["strategy"] == "ACCESSIBILITY_ID" and st[1]["holdMs"] == 1200
    assert st[3]["status"] == "UNSUPPORTED" and st[3]["params"][0]["secret"] and st[4]["status"] == "UNSUPPORTED"
    assert plan["summary"] == {"total": 6, "supported": 4, "unsupported": 2, "warnings": 0}
    res = client.post("/api/codegen/generate", json={"sessionId": sid}).json()
    assert res["validation"]["status"] == "VERIFIED", res["validation"]
    files = {f["role"]: f for f in res["files"]}
    steps_java, spec = files["steps"]["content"], files["spec"]["content"]
    assert "new AndroidDriver" not in steps_java and "AppiumDriver driver()" in steps_java
    assert "AmtsGestures.longPress(driver(), Deneme3Locators.ADIM_02_LONG_PRESS_ME, Duration.ofMillis(1200));" in steps_java
    assert 'AmtsGestures.scroll(driver(), Deneme3Locators.ADIM_03_ITEMLIST, "DOWN");' in steps_java
    assert "UnsupportedOperationException" in steps_java and "BACK" in spec and "AMTS UYARI" in spec
    assert '"AMTS_PININPUT"' in spec and "activateApp" not in steps_java and "startActivity" not in steps_java
    assert 'AppiumBy.id("com.amts.sampleapp:id/q")' in files["locators"]["content"]
    assert "// Alternatif" in files["locators"]["content"] and "AppiumBy.accessibilityId" in files["locators"]["content"]
    assert "* DENEME-3 Adım 1 - TRANSFER öğesine dokun" in spec


def test_framework_modes_compile(client, token):
    sid = _session(client, token, _rich)
    cfg = {"stepsPackage": "com.bank.mobile.steps", "baseClass": "com.bank.mobile.BaseSteps", "locatorStorage": "INLINE",
           "javaVersion": "17", "asciiOnly": True, "stepPrefix": "Havale",
           "driver": {"mode": "INHERITED_METHOD", "methodName": "currentDriver", "driverType": "AndroidDriver"},
           "helper": {"mode": "INHERITED", "passDriver": False, "methods": {"tap": "clickTo", "longPress": "holdOn"}}}
    res = client.post("/api/codegen/generate", json={"sessionId": sid, "config": cfg}).json()
    assert res["validation"]["status"] == "VERIFIED", res["validation"]
    j = [f for f in res["files"] if f["role"] == "steps"][0]["content"]
    assert "extends BaseSteps" in j and "clickTo(AppiumBy.id(" in j and "holdOn(AppiumBy.accessibilityId(" in j
    assert not any(f["role"] in ("helper", "locators") for f in res["files"]) and "\\u00e7" in j
    cfg2 = {"helper": {"mode": "STATIC", "className": "com.bank.util.Gestures"},
            "driver": {"className": "com.bank.core.Drivers", "methodName": "get", "driverType": "WebDriver"}}
    res2 = client.post("/api/codegen/generate", json={"sessionId": sid, "config": cfg2}).json()
    assert res2["validation"]["status"] == "VERIFIED"
    assert "Gestures.tap(driver(), " in [f for f in res2["files"] if f["role"] == "steps"][0]["content"]


def test_invalid_config_rejected(client, token):
    sid = _session(client, token, _rich)
    r = client.post("/api/codegen/plan", json={"sessionId": sid, "config": {"stepsPackage": "com.class.x"}})
    assert r.status_code == 422
    r = client.post("/api/codegen/plan", json={"sessionId": sid, "config": {"helper": {"mode": "INHERITED"}}})
    assert r.status_code == 422


def test_edited_files_validate_and_zip(client, token):
    sid = _session(client, token, _rich)
    res = client.post("/api/codegen/generate", json={"sessionId": sid}).json()
    files = res["files"]
    broken = [dict(f, content=f["content"].replace("public void adim01", "public void adim01 broken")) if f["role"] == "steps" else f for f in files]
    v = client.post("/api/codegen/validate", json={"sessionId": sid, "files": broken}).json()
    assert v["status"] == "FAILED" and any(c["id"] == "javac" and c["status"] == "FAIL" for c in v["checks"])
    renamed = [dict(f, content=f["content"].replace("TRANSFER öğesine dokun", "TRANSFER butonuna bas")) if f["role"] == "spec" else f for f in files]
    v = client.post("/api/codegen/validate", json={"sessionId": sid, "files": renamed}).json()
    assert v["status"] == "FAILED" and [c for c in v["checks"] if c["id"] == "gauge_match"][0]["status"] == "FAIL"
    bad = client.post("/api/codegen/validate", json={"sessionId": sid, "files": [dict(files[0], path="../x.java")]})
    assert bad.status_code == 422
    z = client.post("/api/codegen/zip", json={"sessionId": sid, "files": files})
    assert z.status_code == 200 and z.headers["x-amts-validation"] == "VERIFIED"
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert "AMTS_VALIDATION.md" in names and "specs/deneme_3.spec" in names
    z2 = client.post("/api/codegen/zip", json={"sessionId": sid, "files": broken})
    assert z2.headers["x-amts-validation"] == "FAILED"
    assert "BAŞARISIZ" in zipfile.ZipFile(io.BytesIO(z2.content)).read("AMTS_VALIDATION.md").decode()
    lst = client.get("/api/codegen/sessions").json()
    assert any(s["id"] == sid and s["actions"].get("TAP") == 2 for s in lst)
    moved = [dict(f, content=f["content"].replace("public class Deneme3Steps", "public class OtherName")) if f["role"] == "steps" else f for f in files]
    v = client.post("/api/codegen/validate", json={"sessionId": sid, "files": moved}).json()
    assert v["status"] == "FAILED" and "dosya yoluyla" in [c for c in v["checks"] if c["id"] == "javac"][0]["details"][0]
    v21 = client.post("/api/codegen/generate", json={"sessionId": sid, "config": {"javaVersion": "21"}}).json()["validation"]
    assert v21["status"] == "NOT_VERIFIED" and [c for c in v21["checks"] if c["id"] == "javac"][0]["status"] == "PARTIAL"
