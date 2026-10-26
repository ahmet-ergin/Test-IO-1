import pytest
from services.state_machine import can_transition, assert_transition
from services.masking import mask_event, mask_hierarchy_xml, MASK
from services.locators import extract_locators
from core.errors import AppError

KW = ["password", "pin", "otp", "şifre"]


@pytest.mark.parametrize("a,b,ok", [
    ("IDLE", "STARTING", True), ("STARTING", "RECORDING", True), ("RECORDING", "PAUSED", True),
    ("PAUSED", "RECORDING", True), ("RECORDING", "STOPPING", True), ("STOPPING", "COMPLETED", True),
    ("RECORDING", "FAILED", True), ("IDLE", "RECORDING", False), ("COMPLETED", "RECORDING", False),
    ("PAUSED", "PAUSED", False), ("FAILED", "STARTING", False), ("STOPPING", "RECORDING", False),
])
def test_transitions(a, b, ok):
    assert can_transition(a, b) is ok


def test_assert_transition_raises():
    with pytest.raises(AppError) as e:
        assert_transition("COMPLETED", "PAUSED")
    assert e.value.code == "INVALID_STATE_TRANSITION"


def test_password_field_masked():
    ev = {"element": {"password": True, "text": "secret"}, "inputValue": {"masked": False, "value": "1234"}}
    out = mask_event(ev, KW)
    assert out["inputValue"] == {"masked": True, "value": None, "length": 4, "reason": "SENSITIVE_FIELD"}
    assert out["element"]["text"] == MASK


def test_keyword_and_turkish_masked():
    ev = {"element": {"resourceId": "com.bank:id/sifreInput"}, "inputValue": {"masked": False, "value": "abc"}}
    assert mask_event(ev, KW)["inputValue"]["masked"] is True


def test_otp_pattern_masked_even_without_keyword():
    ev = {"element": {"resourceId": "com.bank:id/code"}, "inputValue": {"masked": False, "value": "482913"}}
    assert mask_event(ev, KW)["inputValue"]["reason"] == "OTP_PATTERN"


def test_non_sensitive_kept():
    ev = {"element": {"resourceId": "com.bank:id/name"}, "inputValue": {"masked": False, "value": "Ali"}}
    assert mask_event(ev, KW)["inputValue"]["value"] == "Ali"


def test_hierarchy_masking():
    xml = '<hierarchy><node text="hunter2" password="true"/><node text="Hello" resource-id="a:id/t"/></hierarchy>'
    out = mask_hierarchy_xml(xml, KW)
    assert "hunter2" not in out and "Hello" in out


def test_locators_uniqueness_from_snapshot():
    xml = ('<hierarchy><node resource-id="a:id/ok" text="OK" class="android.widget.Button"/>'
           '<node resource-id="a:id/ok" text="OK2"/><node content-desc="close"/></hierarchy>')
    locs = extract_locators({"resourceId": "a:id/ok", "text": "OK", "className": "android.widget.Button"}, None, xml)
    rid = next(c for c in locs if c["strategy"] == "RESOURCE_ID")
    assert rid["uniqueness"]["matchCount"] == 2 and rid["uniqueness"]["unique"] is False
    ui = next(c for c in locs if c["strategy"] == "UIAUTOMATOR")
    assert ui["uniqueness"]["unique"] is True
    assert locs[0]["strategy"] != "XPATH"


def test_locators_without_element_coordinate_fallback():
    locs = extract_locators(None, {"x": 10, "y": 20}, None)
    assert locs == [locs[0]] and locs[0]["strategy"] == "COORDINATES" and locs[0]["uniqueness"]["checked"] is False
