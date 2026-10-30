from test_codegen import _session, _rich, _ev, _el
from services.codegen.javautil import fill_template_value
from services.codegen.pom_config import MOBILDENIZ, PomConfig

POM = "/api/codegen/pom"


def _md(client, **over):
    prof = {p["id"]: p for p in client.get(f"{POM}/profiles").json()}
    assert prof["MOBILDENIZ"]["name"] == "MobilDeniz - Cucumber POM" and prof["MOBILDENIZ"]["builtin"]
    return {**prof["MOBILDENIZ"]["config"], **over}


def test_template_value_is_quoted_once():
    assert fill_template_value('locator = "id={value}"', "com.app:id/x") == 'locator = "id=com.app:id/x"'
    assert fill_template_value('locator = "id={value}"', "id=com.app:id/x") == 'locator = "id=com.app:id/x"'
    assert fill_template_value('locator = "xpath={value}"', '//a[@text="T"]') == 'locator = "xpath=//a[@text=\\"T\\"]"'
    assert fill_template_value("id = {value}", 'a"b') == 'id = "a\\"b"'
    assert fill_template_value('locator = "xpath={value}"', "xpath=//b") == 'locator = "xpath=//b"'
    PomConfig(**MOBILDENIZ)


def test_mobildeniz_profile_matches_contract(client, token):
    sid = _session(client, token, _rich)
    res = client.post(f"{POM}/generate", json={"sessionId": sid, "config": _md(client)}).json()
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED", res["validation"]
    f = {x["role"]: x for x in res["files"]}
    st, ct, an, feat = (f[k]["content"] for k in ("steps", "contract", "android", "feature"))
    assert f["steps"]["path"] == "src/test/java/testAutomation/mobile/mobildeniz/tests/V3/Deneme3Test.java"
    assert f["android"]["path"].endswith("testAutomation/mobile/mobildeniz/pageModels/android/V3/Deneme3Page.java")
    assert "import cucumber.api.java.en.And;" in st and "import testautomation.mobile.domainlayer.pombase.Test;" in st
    assert "public class Deneme3Test extends Test {" in st and "public IDeneme3Page deneme3Page;" in st
    assert '@And("^TRANSFER öğesine tıklar$")\n    public void transferOgesineTiklar() {\n        deneme3Page.clickTransferButton();' in st
    assert "@PageModel\npublic interface IDeneme3Page {" in ct and "import testautomation.mobile.domainlayer.annotations.PageModel;" in ct
    assert "public class Deneme3Page extends Model implements IDeneme3Page {" in an
    assert '@FindBy(locator = "id=com.amts.sampleapp:id/transferButton", timeout = 2)\n    public IMobileElement transferButton;' in an
    assert 'id="' not in an and "mobileApp.longPressOnElement(longPressButton);" in an and "mobileApp.navigateToBack();" in an
    assert "swipeUp()" not in an and "swipeDown()" not in an and "MANUEL UYARLAMA GEREKLİ" in an
    rows = {r["action"]: r for r in res["plan"]["steps"]}
    assert rows["SCROLL"]["status"] == "MANUAL" and rows["LONG_PRESS"]["selected"]["strategy"] == "ACCESSIBILITY_ID"
    assert any(i["code"] == "LOCATOR_PREFIX_UNVERIFIED" for i in rows["LONG_PRESS"]["issues"])
    assert 'Ve pinInput alanına "AMTS_PIN_INPUT" anahtarlı gizli test verisini yazar' in feat
    assert '@And("^pinInput alanına \\"([^\\"]*)\\" anahtarlı gizli test verisini yazar$")' in st
    assert "Diyelim ki TRANSFER öğesine tıklar" in feat


def test_mobildeniz_regex_validation_and_class_conflicts(client, token):
    sid = _session(client, token, _rich)
    cfg = _md(client, existingClassNames=["testAutomation.mobile.mobildeniz.pageModels.android.V3.Deneme3Page", "IDeneme3Page"])
    res = client.post(f"{POM}/generate", json={"sessionId": sid, "config": cfg}).json()
    checks = {c["id"]: c for c in res["validation"]["checks"]}
    assert checks["class_collisions"]["status"] == "WARN" and len(checks["class_collisions"]["details"]) == 2
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED" and len(res["plan"]["classConflicts"]) == 2
    files = res["files"]
    bad = [dict(x, content=x["content"].replace("Diyelim ki TRANSFER öğesine tıklar", "Diyelim ki TRANSFER öğesine tıklar.")) if x["role"] == "feature" else x for x in files]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": cfg, "files": bad}).json()
    assert {c["id"]: c for c in v["checks"]}["feature_match"]["status"] == "FAIL"
    noanchor = [dict(x, content=x["content"].replace('"^TRANSFER öğesine tıklar$"', '"TRANSFER öğesine tıklar"')) if x["role"] == "steps" else x for x in files]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": cfg, "files": noanchor}).json()
    assert {c["id"]: c for c in v["checks"]}["feature_match"]["status"] == "FAIL"
    no_timeout = client.post(f"{POM}/generate", json={"sessionId": sid, "config": _md(client, findByExtraArgs="")}).json()
    assert '@FindBy(locator = "id=com.amts.sampleapp:id/transferButton")' in [x for x in no_timeout["files"] if x["role"] == "android"][0]["content"]
    assert client.post(f"{POM}/plan", json={"sessionId": sid, "config": _md(client, findByExtraArgs="timeout")}).status_code == 422
    assert client.post("/api/codegen/generate", json={"sessionId": sid}).json()["validation"]["status"] == "VERIFIED"
