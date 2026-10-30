# MobilDeniz Cucumber POM profile - external API tests (read-only, no replays/heartbeats/mutations)
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"
DENEME3 = "976206fa-7e7d-4da1-b8c8-399f2d24f955"
SCROLL_SESSION = "fa049f6e-4d45-47a3-a87e-5c29140ffbf5"


@pytest.fixture(scope="module")
def profiles():
    r = requests.get(f"{API}/codegen/pom/profiles", timeout=30)
    assert r.status_code == 200
    return {p["id"]: p for p in r.json()}


def _file(files, role_or_sub):
    for f in files:
        if f.get("role") == role_or_sub or role_or_sub in f["path"]:
            return f
    raise AssertionError(f"{role_or_sub} not in {[x['path'] for x in files]}")


@pytest.fixture(scope="module")
def gen_deneme3(profiles):
    r = requests.post(f"{API}/codegen/pom/generate", json={"sessionId": DENEME3, "config": profiles["MOBILDENIZ"]["config"]}, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


# Profiles listing
def test_profiles_builtin(profiles):
    assert {"GENERIC", "MOBILDENIZ"} <= set(profiles)
    md = profiles["MOBILDENIZ"]
    assert md["name"] == "MobilDeniz - Cucumber POM"
    s = str(md["config"])
    for needle in ["testAutomation.mobile.mobildeniz.tests.V3", "{name}Test", "I{name}Page", "cucumber.api.java.en.And",
                   "testautomation.mobile.domainlayer.annotations.FindBy", "IMobileElement", "timeout = 2"]:
        assert needle in s, needle


# DENEME-3 generation
def test_deneme3_status(gen_deneme3):
    assert gen_deneme3["validation"]["status"] == "STRUCTURE_VERIFIED"
    print([f["path"] for f in gen_deneme3["files"]])


def test_deneme3_steps(gen_deneme3):
    steps = next(f for f in gen_deneme3["files"] if f["path"].endswith("Deneme3Test.java"))
    c = steps["content"]
    assert "public IDeneme3Page deneme3Page;" in c
    assert '@And("^TRANSFER öğesine tıklar$")' in c
    assert "public void transferOgesineTiklar()" in c


def test_deneme3_android(gen_deneme3):
    andr = next(f for f in gen_deneme3["files"] if f["path"].endswith("/Deneme3Page.java") and "android" in f["path"])
    c = andr["content"]
    assert '@FindBy(locator = "id=com.amts.sampleapp:id/transferButton", timeout = 2)' in c
    assert "public IMobileElement transferButton;" in c
    assert 'id="' not in c


# Scroll / long press session
def test_scroll_session_manual(profiles):
    r = requests.post(f"{API}/codegen/pom/generate", json={"sessionId": SCROLL_SESSION, "config": profiles["MOBILDENIZ"]["config"]}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    rows = d["plan"]["rows"] if "rows" in d["plan"] else d["plan"]["steps"]
    scroll = [x for x in rows if "SCROLL" in str(x.get("action", x.get("type", ""))).upper()]
    assert scroll, rows[:2]
    assert all(x["status"] == "MANUAL" for x in scroll), scroll
    andr = [f for f in d["files"] if "android" in f["path"] and f["path"].endswith(".java")]
    txt = "\n".join(f["content"] for f in andr)
    assert "MANUEL UYARLAMA GEREKLİ" in txt
    assert "swipeUp()" not in txt and "swipeDown()" not in txt
    lp = [x for x in rows if "LONG" in str(x.get("action", x.get("type", ""))).upper()]
    assert lp
    s = str(lp)
    assert "ACCESSIBILITY_ID" in s and "LOCATOR_PREFIX_UNVERIFIED" in s, s
    assert 'accessibilityId=' in txt


# Class collision is WARN not FAIL
def test_class_collision_warn(profiles):
    cfg = dict(profiles["MOBILDENIZ"]["config"])
    cfg["existingClassNames"] = ["Deneme3Page"]
    r = requests.post(f"{API}/codegen/pom/generate", json={"sessionId": DENEME3, "config": cfg}, timeout=60)
    assert r.status_code == 200, r.text
    v = r.json()["validation"]
    assert v["status"] == "STRUCTURE_VERIFIED"
    checks = {c.get("id", c.get("name")): c for c in v["checks"]}
    assert checks["class_collisions"]["status"] == "WARN"


# Generic unchanged
def test_generic_still_structure_verified(profiles):
    r = requests.post(f"{API}/codegen/pom/generate", json={"sessionId": DENEME3, "config": profiles["GENERIC"]["config"]}, timeout=60)
    assert r.status_code == 200
    assert r.json()["validation"]["status"] == "STRUCTURE_VERIFIED"
