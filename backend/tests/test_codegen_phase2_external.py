# Phase 2 (sensitive data + conflicts) - external API tests against MOBILDENIZ profile (read-only: plan/generate/validate/zip only)
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
POM = f"{BASE_URL}/api/codegen/pom"
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


def _checks(v):
    return {c["id"]: c for c in v["checks"]}


def _role(res, role):
    return next(f for f in res["files"] if f.get("role") == role)


@pytest.fixture(scope="module")
def d1(md):
    return _gen(DENEME1, md)


# Sensitive data: DENEME-1
def test_d1_secret_helper(d1):
    paths = [f["path"] for f in d1["files"]]
    print(paths)
    sec = _role(d1, "secrets")
    assert sec["path"].endswith("AmtsSecureData.java")
    c = sec["content"]
    assert "System.getenv" in c and "System.getProperty" in c and "IllegalStateException" in c
    st = _role(d1, "steps")["content"]
    assert "AmtsSecureData.require(key)" in st
    assert _checks(d1["validation"])["sensitive_data"]["status"] == "PASS"
    assert _checks(d1["validation"])["framework_compile"]["status"] == "NOT_VERIFIED"
    assert d1["validation"]["status"] == "STRUCTURE_VERIFIED"


def test_d1_no_raw_sensitive_values(d1):
    sens = [r for r in d1["plan"]["steps"] if r["sensitive"]]
    print([(r["order"], r["action"], r["params"]) for r in sens])
    assert sens, "expected at least one sensitive row in DENEME-1"
    for r in sens:
        for p in r["params"]:
            assert p["secret"] and p["specValue"].startswith("AMTS_")
    feat = _role(d1, "feature")["content"]
    for ln in feat.splitlines():
        if "gizli test verisi" in ln:
            assert all(v.startswith("AMTS_") for v in re.findall(r'"([^"]*)"', ln)), ln


def test_d1_leak_validation_and_zip(d1, md):
    android = _role(d1, "android")["content"]
    m = re.search(r"(\w+)\.sendKeys\(value\);", android)
    assert m, "no sendKeys(value) in android"
    leak = [dict(f, content=f["content"].replace(m.group(0), f'{m.group(1)}.sendKeys("1234");')) if f.get("role") == "android" else f
            for f in d1["files"]]
    v = requests.post(f"{POM}/validate", json={"sessionId": DENEME1, "config": md, "files": leak}, timeout=90).json()
    assert _checks(v)["sensitive_data"]["status"] == "FAIL" and v["status"] == "FAILED"
    # a compile error with a string literal in the source line
    bad = [dict(f, content=f["content"].replace(m.group(0), f'{m.group(1)}.sendKeys("SECRET9876") +;')) if f.get("role") == "android" else f
           for f in d1["files"]]
    z = requests.post(f"{POM}/zip", json={"sessionId": DENEME1, "config": md, "files": bad}, timeout=90)
    assert z.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    report = zf.read("AMTS_VALIDATION.md").decode()
    js = zf.read("amts-validation.json").decode()
    print(report[-1500:])
    assert "SECRET9876" not in report and "SECRET9876" not in js
    assert "1234" not in report


# Existing step reuse: DENEME-3
def test_d3_step_reuse_unique(md):
    res = _gen(DENEME3, {**md, "existingStepTexts": ["^TRANSFER öğesine tıklar$"]})
    r1 = res["plan"]["steps"][0]
    assert r1["status"] == "REUSED"
    assert "transferOgesineTiklar" not in _role(res, "steps")["content"]
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED"


def test_d3_step_reuse_ambiguous(md):
    res = _gen(DENEME3, {**md, "existingStepTexts": ["^TRANSFER öğesine tıklar$", "^(.*) öğesine tıklar$"]})
    r1 = res["plan"]["steps"][0]
    assert r1["status"] != "REUSED"
    assert any(i["code"] == "AMBIGUOUS_EXISTING_STEP" for i in r1["issues"])
    assert _checks(res["validation"])["step_collisions"]["status"] == "FAIL"


# Existing page methods / class names
def test_d3_existing_page_method(md):
    res = _gen(DENEME3, {**md, "existingPageMethods": ["IDeneme3Page: void clickTransferButton()"]})
    paths = [f["path"] for f in res["files"]]
    print(paths)
    assert any(p.endswith("IDeneme3Page.amts-members.txt") for p in paths)
    assert any(p.endswith("Deneme3Page.amts-members.txt") and "android" in p for p in paths)
    assert "void clickTransferButton()" not in _role(res, "contract")["content"]
    assert "public void clickTransferButton()" not in _role(res, "android")["content"]
    assert "deneme3Page.clickTransferButton();" in _role(res, "steps")["content"]
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED"
    assert _checks(res["validation"])["class_collisions"]["status"] == "WARN"


def test_d3_existing_class_names(md):
    res = _gen(DENEME3, {**md, "existingClassNames": ["Deneme3Test"]})
    st = _role(res, "steps")
    assert st["path"].endswith("Deneme3Test.amts-members.txt")
    assert "package " not in st["content"] and "public class Deneme3Test" not in st["content"]
    assert _checks(res["validation"])["class_collisions"]["status"] == "WARN"
    assert res["validation"]["status"] == "STRUCTURE_VERIFIED"
    full = _gen(DENEME3, md)["files"]
    v = requests.post(f"{POM}/validate", json={"sessionId": DENEME3, "config": {**md, "existingClassNames": ["Deneme3Test"]},
                                              "files": full}, timeout=90).json()
    assert _checks(v)["class_collisions"]["status"] == "FAIL"
