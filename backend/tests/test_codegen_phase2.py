import io
import zipfile
from test_codegen import _session, _rich, _ev, _el
from test_codegen_mobildeniz import _md
from services.codegen.pom_config import parse_page_method
from services.codegen.pom_planner import pom_sensitive

POM = "/api/codegen/pom"


def _gen(client, sid, cfg):
    r = client.post(f"{POM}/generate", json={"sessionId": sid, "config": cfg})
    assert r.status_code == 200, r.text
    return r.json()


def _by(res):
    return {f["role"]: f for f in res["files"]}


def _checks(v):
    return {c["id"]: c for c in v["checks"]}


def test_parse_page_method_and_sensitive_heuristics():
    pm = parse_page_method("IDeneme3Page: void typePinInput(final String value);")
    assert pm == {"iface": "IDeneme3Page", "ifaceFq": "IDeneme3Page", "ret": "void", "name": "typePinInput", "params": ["String"]}
    assert parse_page_method("a.b.IX# boolean isOk()")["ret"] == "boolean" and parse_page_method("clickX()") is None
    assert pom_sensitive({"element": {"resourceId": "app:id/otpInput"}})
    assert pom_sensitive({"element": {"hint": "SMS doğrulama kodu"}})
    assert pom_sensitive({"element": {"resourceId": "app:id/sifreAlani"}})
    assert not pom_sensitive({"element": {"resourceId": "app:id/spinnerList"}})


def test_secret_helper_and_no_values(client, token):
    sid = _session(client, token, _rich)
    res = _gen(client, sid, _md(client))
    f = _by(res)
    st, helper, feat = f["steps"]["content"], f["secrets"]["content"], f["feature"]["content"]
    assert f["secrets"]["path"].endswith("tests/V3/AmtsSecureData.java")
    assert "deneme3Page.typePinInput(AmtsSecureData.require(key));" in st
    assert "System.getenv(key)" in helper and "System.getProperty(key)" in helper and "IllegalStateException" in helper
    assert '"AMTS_PIN_INPUT"' in feat and "4321" not in "".join(x["content"] for x in res["files"])
    assert _checks(res["validation"])["sensitive_data"]["status"] == "PASS"
    leak = [dict(x, content=x["content"].replace("pinInput.sendKeys(value);", 'pinInput.sendKeys("4321");')) if x["role"] == "android" else x
            for x in res["files"]]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": _md(client), "files": leak}).json()
    assert _checks(v)["sensitive_data"]["status"] == "FAIL" and v["status"] == "FAILED"
    feat_leak = [dict(x, content=x["content"].replace('"AMTS_PIN_INPUT"', '"1234"')) if x["role"] == "feature" else x for x in res["files"]]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": _md(client), "files": feat_leak}).json()
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"
    z = client.post(f"{POM}/zip", json={"sessionId": sid, "config": _md(client), "files": leak})
    report = zipfile.ZipFile(io.BytesIO(z.content)).read("AMTS_VALIDATION.md").decode()
    assert "Hassas veriler" in report
    custom = _gen(client, sid, _md(client, secretProvider="CUSTOM", secretValueTemplate="org.acme.Vault.get({key})"))
    assert "secrets" not in _by(custom) and "org.acme.Vault.get(key)" in _by(custom)["steps"]["content"]


def test_existing_step_reuse_unique_and_ambiguous(client, token):
    sid = _session(client, token, _rich)
    res = _gen(client, sid, _md(client, existingStepTexts=["^TRANSFER öğesine tıklar$"]))
    tap = res["plan"]["steps"][0]
    assert tap["status"] == "REUSED" and tap["reusedStep"] == "^TRANSFER öğesine tıklar$"
    f = _by(res)
    assert "transferOgesineTiklar" not in f["steps"]["content"] and "clickTransferButton" not in f["contract"]["content"]
    assert "transferButton" not in f["android"]["content"].split("<amts:members>")[1]
    assert "Diyelim ki TRANSFER öğesine tıklar" in f["feature"]["content"] and res["validation"]["status"] == "STRUCTURE_VERIFIED"
    amb = _gen(client, sid, _md(client, existingStepTexts=["^TRANSFER öğesine tıklar$", "^(.*) öğesine tıklar$"]))
    tap = amb["plan"]["steps"][0]
    assert tap["status"] == "WARNING" and any(i["code"] == "AMBIGUOUS_EXISTING_STEP" for i in tap["issues"])
    assert _checks(amb["validation"])["step_collisions"]["status"] == "FAIL"


def test_existing_page_method_reuse_and_snippets(client, token):
    sid = _session(client, token, _rich)
    cfg = _md(client, existingPageMethods=["IDeneme3Page: void clickTransferButton()", "IOther: void longPressLongPressButton()",
                                           "IDeneme3Page: boolean navigateBack()"],
              existingClassNames=["Deneme3Test"])
    res = _gen(client, sid, cfg)
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED", res["validation"]
    paths = [f["path"] for f in res["files"]]
    assert any(p.endswith("tests/V3/Deneme3Test.amts-members.txt") for p in paths)
    assert any(p.endswith("contracts/V3/IDeneme3Page.amts-members.txt") for p in paths)
    assert any(p.endswith("android/V3/Deneme3Page.amts-members.txt") for p in paths)
    assert not any(p.endswith("Deneme3Test.java") or p.endswith("IDeneme3Page.java") for p in paths)
    f = _by(res)
    assert "void clickTransferButton();" not in f["contract"]["content"] and "deneme3Page.clickTransferButton();" in f["steps"]["content"]
    assert "void longPressLongPressButton();" in f["contract"]["content"]
    assert "navigateBackAmts" in f["contract"]["content"]
    assert "otomatik birleştirme yapılmaz" in f["contract"]["content"] and "package " not in f["contract"]["content"]
    rows = res["plan"]["steps"]
    assert any(i["code"] == "EXISTING_PAGE_METHOD_REUSED" for i in rows[0]["issues"])
    assert any(i["code"] == "PAGE_METHOD_SIGNATURE_CONFLICT" for i in rows[4]["issues"])
    assert _checks(res["validation"])["class_collisions"]["status"] == "WARN"
    full = _gen(client, sid, _md(client))["files"]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": cfg, "files": full}).json()
    assert _checks(v)["class_collisions"]["status"] == "FAIL"
    broken = [dict(x, content=x["content"].replace("deneme3Page.clickTransferButton();", "deneme3Page.clickNothing();"))
              if x["role"] == "steps" else x for x in res["files"]]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": cfg, "files": broken}).json()
    assert v["status"] == "FAILED"
    assert client.post(f"{POM}/plan", json={"sessionId": sid, "config": _md(client, existingPageMethods=["clickX()"])}).status_code == 422


def test_declared_interface_is_never_regenerated_in_full(client, token):
    sid = _session(client, token, _rich)
    for methods, extra in ((["IDeneme3Page: boolean clickTransferButton()"], {}), (["IDeneme3Page: void somethingElse()"], {}),
                           (["IDeneme3Page: void clickTransferButton()"], {"existingStepTexts": ["^TRANSFER öğesine tıklar$"]})):
        res = _gen(client, sid, _md(client, existingPageMethods=methods, **extra))
        paths = [f["path"] for f in res["files"]]
        assert not any(p.endswith("IDeneme3Page.java") or p.endswith("V3/Deneme3Page.java") for p in paths), (methods, paths)
        assert res["validation"]["status"] == "STRUCTURE_VERIFIED", (methods, res["validation"])
        assert _checks(res["validation"])["class_collisions"]["status"] == "WARN"
    conflict = _gen(client, sid, _md(client, existingPageMethods=["IDeneme3Page: boolean clickTransferButton()"]))
    assert "void clickTransferButtonAmts();" in _by(conflict)["contract"]["content"]


def test_sensitive_check_ignores_comments_and_report_masks_literals(client, token):
    sid = _session(client, token, _rich)
    res = _gen(client, sid, _md(client))
    sneaky = [dict(x, content=x["content"].replace("deneme3Page.typePinInput(AmtsSecureData.require(key));",
                                                   'deneme3Page.typePinInput("8888" /* AmtsSecureData.require( */);'))
              if x["role"] == "steps" else x for x in res["files"]]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": _md(client), "files": sneaky}).json()
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"
    indirect = [dict(x, content=x["content"].replace("pinInput.sendKeys(value);", 'String p = "7777";\n        pinInput.sendKeys(p);'))
                if x["role"] == "android" else x for x in res["files"]]
    v = client.post(f"{POM}/validate", json={"sessionId": sid, "config": _md(client), "files": indirect}).json()
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"
    leak = [dict(x, content=x["content"].replace('"AMTS_PIN_INPUT" anahtarlı gizli test verisini yazar', '"LEAK5555" yazar'))
            if x["role"] == "feature" else x for x in res["files"]]
    z = client.post(f"{POM}/zip", json={"sessionId": sid, "config": _md(client), "files": leak})
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    assert "LEAK5555" not in zf.read("AMTS_VALIDATION.md").decode() and "LEAK5555" not in zf.read("amts-validation.json").decode()
