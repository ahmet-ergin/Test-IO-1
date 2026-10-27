import io
import zipfile
from test_codegen import _session, _rich, _ev, _el
from services.codegen.pom_validate import cucumber_regex

POM = "/api/codegen/pom"


def _gen(client, sid, cfg=None):
    return client.post(f"{POM}/generate", json={"sessionId": sid, "config": cfg or {}}).json()


def _files(res):
    return {f["role"]: f for f in res["files"]}


def test_cucumber_expression_matching():
    rx = cucumber_regex("Ad alanına {string} yazar")
    assert rx.match('Ad alanına "ali" yazar') and not rx.match("Ad alanına ali yazar")


def test_pom_three_layers_structure_verified(client, token):
    sid = _session(client, token, _rich)
    res = _gen(client, sid)
    v = res["validation"]
    assert v["status"] == "STRUCTURE_VERIFIED", v
    assert {c["id"]: c["status"] for c in v["checks"]}["framework_compile"] == "NOT_VERIFIED"
    f = _files(res)
    assert set(f) == {"feature", "steps", "contract", "android", "readme"}
    st, ct, an, feat = f["steps"]["content"], f["contract"]["content"], f["android"]["content"], f["feature"]["content"]
    assert f["steps"]["path"] == "src/test/java/com/example/mobile/tests/Deneme3Steps.java"
    assert "public class Deneme3Steps extends BaseTest" in st and "private IDeneme3Page deneme3Page;" in st
    assert '@And("TRANSFER öğesine tıklar")' in st and "deneme3Page.clickTransferButton();" in st
    code = "\n".join(ln for ln in st.splitlines() if not ln.strip().startswith(("//", "*", "/*")))
    assert "FindBy" not in code and "new " not in code
    assert "@PageModel\npublic interface IDeneme3Page" in ct and "void clickTransferButton();" in ct and "{\n        " not in ct
    assert "public class Deneme3AndroidPage extends BaseModel implements IDeneme3Page" in an
    assert '@FindBy(id = "com.amts.sampleapp:id/transferButton")\n    private IMobileElement transferButton;' in an
    assert "mobileApp.longPressOnElement(longPressButton);" in an and "mobileApp.swipeUp();" in an
    assert "pinInput.clear();" in an and "pinInput.sendKeys(value);" in an and "mobileApp.navigateToBack();" in an
    assert 'deneme3Page.typePinInput(System.getenv(key));' in st
    assert "# language: tr" in feat and 'Ve pinInput alanına "AMTS_PIN_INPUT" anahtarlı gizli test verisini yazar' in feat
    assert "Ve geri tuşuna basar" in feat and "Ve ekranı aşağı kaydırır" in feat
    assert "// Alternatif locator'lar (bilgi amaçlı):" in an and "// <amts:members>" in an


def test_pom_unsupported_and_locator_fallback(client, token):
    def build(sid):
        return [_ev(sid, 1, "SWIPE", _el("com.amts.sampleapp:id/a", "A"), {"x": 1, "y": 1}),
                _ev(sid, 2, "TAP", _el(None, "Only text", desc=None), {"x": 5, "y": 5})]
    sid = _session(client, token, build)
    cfg = {"actionTemplates": {"BACK": ""}, "locatorTemplates": {"RESOURCE_ID": "id = {value}", "XPATH": ""}}
    res = _gen(client, sid, cfg)
    rows = res["plan"]["steps"]
    assert rows[0]["status"] == "UNSUPPORTED" and any(i["code"] == "UNSUPPORTED_ACTION" for i in rows[0]["issues"])
    assert rows[1]["status"] == "UNSUPPORTED" and any(i["code"] == "NO_SUPPORTED_LOCATOR" for i in rows[1]["issues"])
    an = _files(res)["android"]["content"]
    assert "UnsupportedOperationException" in an and res["validation"]["status"] == "STRUCTURE_VERIFIED"
    cfg2 = {"locatorTemplates": {"UIAUTOMATOR": "uiAutomator = {value}"}}
    rows2 = _gen(client, sid, cfg2)["plan"]["steps"]
    assert rows2[1]["selected"]["strategy"] in ("UIAUTOMATOR", "XPATH")


def test_pom_custom_framework_names(client, token):
    sid = _session(client, token, _rich)
    cfg = {"javaVersion": "11", "stepsPackage": "org.acme.app.steps", "contractsPackage": "org.acme.app.pages.api",
           "androidPackage": "org.acme.app.pages.droid", "stepBaseClass": "org.acme.fw.StepBase", "pageBaseClass": "org.acme.fw.PageBase",
           "pageModelAnnotation": "org.acme.fw.Screen", "pageModelArgs": 'name = "Demo"', "locatorAnnotation": "org.acme.fw.Locate",
           "elementType": "org.acme.fw.UiElement", "appExpression": "app()", "pageFieldAnnotation": "org.acme.fw.Bind",
           "stepAnnotation": "org.acme.fw.Ve", "interfacePattern": "{name}Screen", "androidClassPattern": "{name}ScreenAndroid",
           "locatorTemplates": {"RESOURCE_ID": 'androidId = {value}, timeout = 5', "ACCESSIBILITY_ID": "", "XPATH": "path = {value}"},
           "actionTemplates": {"LONG_PRESS": "{app}.hold({element});"}, "generateFeature": False}
    res = _gen(client, sid, cfg)
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED", res["validation"]
    f = _files(res)
    assert "feature" not in f and "@Screen(name = \"Demo\")" in f["contract"]["content"]
    assert "@Bind\n    private Deneme3Screen deneme3Screen;" in f["steps"]["content"] and "@Ve(" in f["steps"]["content"]
    assert "app().hold(longPressButton);" in f["android"]["content"]


def test_pom_validation_catches_broken_layers(client, token):
    sid = _session(client, token, _rich)
    res = _gen(client, sid)
    files = res["files"]

    def edit(role, a, b):
        return [dict(x, content=x["content"].replace(a, b)) if x["role"] == role else x for x in files]

    def check(fs, cid):
        v = client.post(f"{POM}/validate", json={"sessionId": sid, "files": fs}).json()
        return v["status"], {c["id"]: c for c in v["checks"]}[cid]

    s, c = check(edit("android", "implements IDeneme3Page", ""), "structure")
    assert s == "FAILED" and c["status"] == "FAIL"
    s, c = check(edit("steps", "deneme3Page.clickTransferButton();", "new IDeneme3Page();"), "structure")
    assert s == "FAILED" and any("new" in d for d in c["details"])
    s, c = check(edit("feature", "TRANSFER öğesine tıklar", "TRANSFER butonuna basar"), "feature_match")
    assert c["status"] == "FAIL"
    s, c = check(edit("android", "transferButton.click();", "transferButton.click()"), "java_syntax")
    assert c["status"] == "FAIL"
    s, c = check(edit("contract", "void clickTransferButton();", "default void clickTransferButton() { }"), "structure")
    assert c["status"] == "FAIL"
    coll = client.post(f"{POM}/validate", json={"sessionId": sid, "files": files,
                                                 "config": {"existingStepTexts": ["{word} öğesine tıklar"]}}).json()
    assert {c["id"]: c for c in coll["checks"]}["step_collisions"]["status"] == "FAIL"
    z = client.post(f"{POM}/zip", json={"sessionId": sid, "files": files})
    assert z.headers["x-amts-validation"] == "STRUCTURE_VERIFIED"
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert "src/test/java/com/example/mobile/pages/android/Deneme3AndroidPage.java" in names
    assert "src/test/resources/features/deneme_3.feature" in names
    report = zipfile.ZipFile(io.BytesIO(z.content)).read("AMTS_VALIDATION.md").decode()
    assert "framework derlemesi doğrulanmadı" in report


def test_pom_invalid_config(client, token):
    sid = _session(client, token, _rich)
    for bad in ({"stepClassPattern": "Steps"}, {"pageBaseClass": "Model"}, {"actionTemplates": {"TAP": "{foo}.click();"}},
                {"appExpression": "a.b()"}, {"locatorTemplates": {"XPATH": "xpath = x"}},
                {"pageModelArgs": ") public class X {"}, {"actionTemplates": {"TAP": "{element}.click()"}},
                {"interfacePattern": "{name}", "stepClassPattern": "{name}"}, {"elementType": "com.example.framework.BaseModel"}):
        assert client.post(f"{POM}/plan", json={"sessionId": sid, "config": bad}).status_code == 422, bad
    gauge = client.post("/api/codegen/generate", json={"sessionId": sid}).json()
    assert gauge["validation"]["status"] == "VERIFIED"
