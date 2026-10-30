# Phase 2 fixes retest (iteration 11) - external, read-only (plan/generate/validate/zip only) against MOBILDENIZ profile
import io
import os
import re
import zipfile
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api/codegen"
POM = f"{API}/pom"
DENEME1 = "251832fb-ff5a-4a3e-bdea-c5c8b6f997cf"
DENEME3 = "976206fa-7e7d-4da1-b8c8-399f2d24f955"


@pytest.fixture(scope="module")
def md():
    r = requests.get(f"{POM}/profiles", timeout=30)
    assert r.status_code == 200
    return {p["id"]: p for p in r.json()}["MOBILDENIZ"]["config"]


def _gen(sid, cfg):
    r = requests.post(f"{POM}/generate", json={"sessionId": sid, "config": cfg}, timeout=90)
    assert r.status_code == 200, r.text
    return r.json()


def _val(sid, cfg, files):
    r = requests.post(f"{POM}/validate", json={"sessionId": sid, "config": cfg, "files": files}, timeout=90)
    assert r.status_code == 200, r.text
    return r.json()


def _checks(v):
    return {c["id"]: c for c in v["checks"]}


def _role(res, role):
    return next(f for f in res["files"] if f.get("role") == role)


# HIGH fix: any existingPageMethods entry for the interface -> contract + android only as .amts-members.txt parts
CASES = {
    "boolean_conflict": ({"existingPageMethods": ["IDeneme3Page: boolean clickTransferButton()"]}),
    "other_method": ({"existingPageMethods": ["IDeneme3Page: void somethingElse()"]}),
    "step_reused_plus_method": ({"existingStepTexts": ["^TRANSFER öğesine tıklar$"],
                                 "existingPageMethods": ["IDeneme3Page: void clickTransferButton()"]}),
    "fq_iface": ({"existingPageMethods": ["testAutomation.mobile.mobildeniz.pageModels.contracts.V3.IDeneme3Page: void somethingElse()"]}),
}


@pytest.mark.parametrize("case", list(CASES))
def test_existing_iface_only_parts(md, case):
    res = _gen(DENEME3, {**md, **CASES[case]})
    paths = [f["path"] for f in res["files"]]
    print(case, paths)
    assert any(p.endswith("contracts/V3/IDeneme3Page.amts-members.txt") for p in paths)
    assert any(p.endswith("android/V3/Deneme3Page.amts-members.txt") for p in paths)
    assert not any(p.endswith("IDeneme3Page.java") or p.endswith("/Deneme3Page.java") for p in paths)
    for role in ("contract", "android"):
        c = _role(res, role)["content"]
        assert "package " not in c and "public interface IDeneme3Page" not in c and "public class Deneme3Page" not in c
    ch = _checks(res["validation"])
    print({k: v["status"] for k, v in ch.items()})
    assert ch["class_collisions"]["status"] == "WARN"
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED"
    if case == "boolean_conflict":
        assert "clickTransferButtonAmts" in _role(res, "contract")["content"]
        assert "clickTransferButtonAmts" in _role(res, "android")["content"]
        assert "deneme3Page.clickTransferButtonAmts();" in _role(res, "steps")["content"]


def test_unrelated_iface_keeps_full_files(md):
    res = _gen(DENEME3, {**md, "existingPageMethods": ["IOtherPage: void somethingElse()"]})
    paths = [f["path"] for f in res["files"]]
    assert any(p.endswith("IDeneme3Page.java") for p in paths)
    assert _checks(res["validation"])["class_collisions"]["status"] == "PASS"


def test_full_iface_sent_with_methods_fails(md):
    full = _gen(DENEME3, md)["files"]
    v = _val(DENEME3, {**md, "existingPageMethods": ["IDeneme3Page: void somethingElse()"]}, full)
    print(_checks(v)["class_collisions"])
    assert _checks(v)["class_collisions"]["status"] == "FAIL"


# Minor fix: check_sensitive strips comments / detects literals
@pytest.fixture(scope="module")
def d1(md):
    return _gen(DENEME1, md)


def _edit(res, role, old, new):
    out = []
    for f in res["files"]:
        if f.get("role") == role:
            assert old in f["content"], f"{old} not in {role}"
            f = dict(f, content=f["content"].replace(old, new))
        out.append(f)
    return out


def test_secret_step_comment_trick_fails(d1, md):
    files = _edit(d1, "steps", "deneme1Page.typePinInput(AmtsSecureData.require(key));",
                  'deneme1Page.typePinInput("8888" /* AmtsSecureData.require( */);')
    v = _val(DENEME1, md, files)
    print(_checks(v)["sensitive_data"])
    assert _checks(v)["sensitive_data"]["status"] == "FAIL" and v["status"] == "FAILED"


def test_secret_step_line_comment_trick_fails(d1, md):
    files = _edit(d1, "steps", "deneme1Page.typePinInput(AmtsSecureData.require(key));",
                  'deneme1Page.typePinInput(key); // AmtsSecureData.require(')
    v = _val(DENEME1, md, files)
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"


def test_android_indirect_literal_fails(d1, md):
    android = _role(d1, "android")["content"]
    m = re.search(r"pinInput\.sendKeys\((\w+)\);", android)
    assert m, "no pinInput.sendKeys(x)"
    files = _edit(d1, "android", m.group(0), 'String p = "7777"; pinInput.sendKeys(p);')
    v = _val(DENEME1, md, files)
    print(_checks(v)["sensitive_data"])
    assert _checks(v)["sensitive_data"]["status"] == "FAIL"


def test_unmodified_d1_sensitive_pass(d1):
    assert _checks(d1["validation"])["sensitive_data"]["status"] == "PASS"
    assert d1["validation"]["status"] == "STRUCTURE_VERIFIED"


# Minor fix: ZIP report masks quoted literals in all checks
def test_zip_masks_feature_literal(d1, md):
    feat = _role(d1, "feature")["content"]
    m = re.search(r'pinInput alanına "AMTS_[A-Z_]+" anahtarlı gizli test verisini yazar', feat)
    assert m
    files = _edit(d1, "feature", m.group(0), 'pinInput alanına "LEAK5555" yazar')
    z = requests.post(f"{POM}/zip", json={"sessionId": DENEME1, "config": md, "files": files}, timeout=90)
    assert z.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    report = zf.read("AMTS_VALIDATION.md").decode()
    js = zf.read("amts-validation.json").decode()
    print(report[-1200:])
    assert "LEAK5555" not in report and "LEAK5555" not in js
    assert "BAŞARISIZ" in report or "FAILED" in report


# Regression: Gauge profile
def test_gauge_d3_verified():
    r = requests.post(f"{API}/generate", json={"sessionId": DENEME3, "config": {}}, timeout=90)
    assert r.status_code == 200
    assert r.json()["validation"]["status"] == "VERIFIED"
