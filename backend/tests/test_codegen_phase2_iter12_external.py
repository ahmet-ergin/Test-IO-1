# Iteration 12 retest - external, read-only (generate/validate/zip only) MOBILDENIZ profile
import io
import re
import zipfile
import pytest
import requests
from test_codegen_phase2_fixes_external import POM, API, DENEME1, DENEME3, _gen, _val, _checks, _role, _edit


@pytest.fixture(scope="module")
def md():
    r = requests.get(f"{POM}/profiles", timeout=30)
    return {p["id"]: p for p in r.json()}["MOBILDENIZ"]["config"]


@pytest.fixture(scope="module")
def d1(md):
    return _gen(DENEME1, md)


@pytest.fixture(scope="module")
def d3full(md):
    return _gen(DENEME3, md)


# check_class_conflicts: full iface/android .java + existingPageMethods -> FAIL
@pytest.mark.parametrize("keep", ["contract", "android", "both"])
def test_full_class_with_methods_fails(md, d3full, keep):
    roles = {"contract", "android"} if keep == "both" else {keep}
    files = [f for f in d3full["files"] if f.get("role") not in ({"contract", "android"} - roles)]
    v = _val(DENEME3, {**md, "existingPageMethods": ["IDeneme3Page: void somethingElse()"]}, files)
    cc = _checks(v)["class_collisions"]
    print(keep, cc)
    assert cc["status"] == "FAIL" and v["status"] == "FAILED"
    assert "Page Interface" in cc["summary"]
    if keep in ("contract", "both"):
        assert any("IDeneme3Page" in d for d in cc["details"])
    if keep in ("android", "both"):
        assert any("Deneme3Page" in d and "IDeneme3Page" not in d for d in cc["details"])


def test_full_class_with_fq_methods_fails(md, d3full):
    v = _val(DENEME3, {**md, "existingPageMethods": [
        "testAutomation.mobile.mobildeniz.pageModels.contracts.V3.IDeneme3Page: boolean clickTransferButton()"]}, d3full["files"])
    assert _checks(v)["class_collisions"]["status"] == "FAIL"


def test_full_class_unrelated_methods_pass(md, d3full):
    v = _val(DENEME3, {**md, "existingPageMethods": ["IOtherPage: void x()"]}, d3full["files"])
    assert _checks(v)["class_collisions"]["status"] == "PASS"


def test_zip_full_class_with_methods_fails(md, d3full):
    z = requests.post(f"{POM}/zip", json={"sessionId": DENEME3, "files": d3full["files"],
                                          "config": {**md, "existingPageMethods": ["IDeneme3Page: void somethingElse()"]}}, timeout=90)
    assert z.status_code == 200
    rep = zipfile.ZipFile(io.BytesIO(z.content)).read("AMTS_VALIDATION.md").decode()
    assert "class_collisions: FAIL" in rep


def test_parts_path_still_warn(md):
    res = _gen(DENEME3, {**md, "existingPageMethods": ["IDeneme3Page: void somethingElse()"]})
    cc = _checks(res["validation"])["class_collisions"]
    print(cc["summary"])
    assert cc["status"] == "WARN" and res["validation"]["status"] == "STRUCTURE_VERIFIED"
    assert "Page Interface" in cc["summary"]
    # re-validate the parts -> still WARN
    v = _val(DENEME3, {**md, "existingPageMethods": ["IDeneme3Page: void somethingElse()"]}, res["files"])
    assert _checks(v)["class_collisions"]["status"] == "WARN" and v["status"] == "STRUCTURE_VERIFIED"


# check_sensitive: indirect constants
def test_android_const_fails(d1, md):
    android = _role(d1, "android")["content"]
    m = re.search(r"pinInput\.sendKeys\((\w+)\);", android)
    assert m
    v = _val(DENEME1, md, _edit(d1, "android", m.group(0), "pinInput.sendKeys(PIN_CONST);"))
    print(_checks(v)["sensitive_data"])
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"


def test_android_nested_brace_literal_fails(d1, md):
    android = _role(d1, "android")["content"]
    m = re.search(r"pinInput\.sendKeys\((\w+)\);", android)
    v = _val(DENEME1, md, _edit(d1, "android", m.group(0),
                                "if (true) { int z = 0; } pinInput.sendKeys(\"9999\");"))
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"


def test_step_require_plus_const_fails(d1, md):
    v = _val(DENEME1, md, _edit(d1, "steps", "deneme1Page.typePinInput(AmtsSecureData.require(key));",
                                "AmtsSecureData.require(key); deneme1Page.typePinInput(PIN);"))
    print(_checks(v)["sensitive_data"])
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"


def test_step_intermediate_var_fails(d1, md):
    v = _val(DENEME1, md, _edit(d1, "steps", "deneme1Page.typePinInput(AmtsSecureData.require(key));",
                                "String p = AmtsSecureData.require(key); deneme1Page.typePinInput(p);"))
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"


def test_unedited_pass(d1, md):
    assert _checks(d1["validation"])["sensitive_data"]["status"] == "PASS"
    assert d1["validation"]["status"] == "STRUCTURE_VERIFIED"
    v = _val(DENEME1, md, d1["files"])
    assert v["status"] == "STRUCTURE_VERIFIED"
    d3 = _gen(DENEME3, md)
    assert _checks(d3["validation"])["sensitive_data"]["status"] == "PASS"
    assert d3["validation"]["status"] == "STRUCTURE_VERIFIED"


# report_safe: unquoted / single-quoted feature values not echoed
@pytest.mark.parametrize("val", ["LEAK6666", "'LEAK7777'", "LEAK 8888 x", "`LEAK9999`"])
def test_zip_no_leak(d1, md, val):
    feat = _role(d1, "feature")["content"]
    m = re.search(r'pinInput alanına "AMTS_[A-Z_]+" anahtarlı gizli test verisini yazar', feat)
    assert m
    files = _edit(d1, "feature", m.group(0), f"pinInput alanına {val} yazar")
    token = re.sub(r"\W", "", val).replace("LEAK", "LEAK")
    needle = "LEAK" + re.sub(r"\D", "", val)
    z = requests.post(f"{POM}/zip", json={"sessionId": DENEME1, "config": md, "files": files}, timeout=90)
    assert z.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    rep, js = zf.read("AMTS_VALIDATION.md").decode(), zf.read("amts-validation.json").decode()
    digits = re.sub(r"\D", "", val)
    assert digits not in rep and digits not in js, rep[-1500:]
    assert "FAILED" in rep or "BAŞARISIZ" in rep


def test_validate_response_leak(d1, md):
    feat = _role(d1, "feature")["content"]
    m = re.search(r'pinInput alanına "AMTS_[A-Z_]+" anahtarlı gizli test verisini yazar', feat)
    v = _val(DENEME1, md, _edit(d1, "feature", m.group(0), "pinInput alanına LEAK6666 yazar"))
    s = str(v)
    print("validate response contains value:", "6666" in s)
