"""Configuration of the generic Cucumber + Page Object Model profile. All framework names are user-configurable;
defaults are fictional (com.example.*) and must be replaced with the real project's names locally."""
import re
from typing import List, Literal
from pydantic import BaseModel, Field, model_validator
from services.codegen.javautil import is_ident, is_package, is_fqcn, jpascal as pascal, words, gauge_text

_PATH_RE = re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-.]+)*$")
_PLACEHOLDER = re.compile(r"\{(\w+)\}")
LOCATOR_STRATEGIES = ["RESOURCE_ID", "ACCESSIBILITY_ID", "XPATH", "UIAUTOMATOR"]
ACTION_KEYS = ["TAP", "INPUT_TEXT", "LONG_PRESS", "SCROLL_DOWN", "SCROLL_UP", "SCROLL_LEFT", "SCROLL_RIGHT", "BACK"]
_PM_RE = re.compile(r"^\s*([A-Za-z_][\w.]*)\s*[:#]\s*(?:public\s+)?(?:abstract\s+)?([\w.<>\[\], ]+?)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*;?\s*$")


def parse_page_method(line: str):
    """'IDeneme3Page: void typePin(String value)' -> {iface, ret, name, params:[types]} (param names are ignored)."""
    m = _PM_RE.match(line or "")
    if not m:
        return None
    params = []
    for p in (x.strip() for x in m.group(4).split(",") if x.strip()):
        parts = re.sub(r"\bfinal\s+", "", p).split()
        params.append(parts[0] if parts else p)
    return {"iface": m.group(1).rsplit(".", 1)[-1], "ifaceFq": m.group(1), "ret": m.group(2).replace(" ", ""), "name": m.group(3),
            "params": params}


class LocatorTemplates(BaseModel):
    RESOURCE_ID: str = "id = {value}"
    ACCESSIBILITY_ID: str = "accessibilityId = {value}"
    XPATH: str = "xpath = {value}"
    UIAUTOMATOR: str = ""


class ActionTemplates(BaseModel):
    TAP: str = "{element}.click();"
    INPUT_TEXT: str = "{element}.clear();\n{element}.sendKeys({value});"
    LONG_PRESS: str = "{app}.longPressOnElement({element});"
    SCROLL_DOWN: str = "{app}.swipeUp();"
    SCROLL_UP: str = "{app}.swipeDown();"
    SCROLL_LEFT: str = ""
    SCROLL_RIGHT: str = ""
    BACK: str = "{app}.navigateToBack();"


class MethodVerbs(BaseModel):
    TAP: str = "click"
    INPUT_TEXT: str = "type"
    LONG_PRESS: str = "longPress"
    SCROLL: str = "scroll"
    BACK: str = "navigateBack"


class PomConfig(BaseModel):
    javaVersion: Literal["8", "11"] = "8"
    sourceRoot: str = "src/test/java"
    featureDir: str = "src/test/resources/features"
    generateFeature: bool = True
    stepsPackage: str = "com.example.mobile.tests"
    contractsPackage: str = "com.example.mobile.pages.contracts"
    androidPackage: str = "com.example.mobile.pages.android"
    pageName: str = ""
    stepClassPattern: str = "{name}Steps"
    interfacePattern: str = "I{name}Page"
    androidClassPattern: str = "{name}AndroidPage"
    stepBaseClass: str = "com.example.framework.BaseTest"
    pageBaseClass: str = "com.example.framework.BaseModel"
    pageModelAnnotation: str = "com.example.framework.annotations.PageModel"
    pageModelArgs: str = ""
    stepAnnotation: str = "io.cucumber.java.en.And"
    pageFieldAnnotation: str = ""
    pageFieldModifier: Literal["private", "protected", "public", "package"] = "private"
    pageFieldName: str = ""
    locatorAnnotation: str = "com.example.framework.annotations.FindBy"
    elementType: str = "com.example.framework.elements.IMobileElement"
    elementFieldModifier: Literal["private", "protected", "public", "package"] = "private"
    appExpression: str = "mobileApp"
    resourceIdFormat: Literal["FULL", "SHORT"] = "FULL"
    locatorTemplates: LocatorTemplates = Field(default_factory=LocatorTemplates)
    actionTemplates: ActionTemplates = Field(default_factory=ActionTemplates)
    verbs: MethodVerbs = Field(default_factory=MethodVerbs)
    stepPrefix: str = ""
    featureName: str = ""
    scenarioName: str = ""
    tags: str = "@amts @android"
    secretValueTemplate: str = "System.getenv({key})"
    secretKeyPrefix: str = "AMTS_"
    asciiOnly: bool = False
    existingStepTexts: List[str] = Field(default_factory=list, max_length=5000)
    findByExtraArgs: str = ""
    unverifiedLocatorStrategies: List[str] = Field(default_factory=list)
    stepTextStyle: Literal["EXPRESSION", "REGEX"] = "EXPRESSION"
    stepMethodNaming: Literal["PAGE_METHOD", "STEP_TEXT"] = "PAGE_METHOD"
    existingClassNames: List[str] = Field(default_factory=list, max_length=5000)
    scrollManualHint: str = ""
    secretProvider: Literal["HELPER", "CUSTOM"] = "HELPER"
    secretHelperClass: str = "AmtsSecureData"
    secretHelperPackage: str = ""
    existingPageMethods: List[str] = Field(default_factory=list, max_length=5000)

    def helper_fqcn(self) -> str:
        return f"{self.secretHelperPackage or self.stepsPackage}.{self.secretHelperClass}"

    def secret_call(self, arg: str) -> str:
        if self.secretProvider == "HELPER":
            return f"{self.secretHelperClass}.require({arg})"
        return self.secretValueTemplate.replace("{key}", arg)

    @model_validator(mode="after")
    def _check(self):
        e = []
        for f in ("stepsPackage", "contractsPackage", "androidPackage"):
            if not is_package(getattr(self, f)):
                e.append(f"{f} geçerli bir Java paket adı olmalı.")
        for f in ("stepClassPattern", "interfacePattern", "androidClassPattern"):
            v = getattr(self, f)
            if "{name}" not in v or not is_ident(v.replace("{name}", "X")):
                e.append(f"{f} '{{name}}' içermeli ve geçerli bir sınıf adı üretmeli.")
        if self.pageName and not is_ident(self.pageName):
            e.append("pageName geçerli bir Java adı olmalı.")
        if self.pageFieldName and not is_ident(self.pageFieldName):
            e.append("pageFieldName geçerli bir Java alan adı olmalı.")
        for f in ("stepBaseClass", "pageBaseClass", "pageModelAnnotation", "stepAnnotation", "locatorAnnotation", "elementType"):
            if not is_fqcn(getattr(self, f)):
                e.append(f"{f} tam nitelikli sınıf adı olmalı (ör. com.example.framework.Xyz).")
        if self.pageFieldAnnotation and not is_fqcn(self.pageFieldAnnotation):
            e.append("pageFieldAnnotation boş ya da tam nitelikli ad olmalı.")
        lit = r'(?:"(?:[^"\\]|\\.)*"|-?\d+|true|false)'
        if self.pageModelArgs.strip() and not re.fullmatch(rf"\s*(?:{lit}|\w+\s*=\s*{lit}(?:\s*,\s*\w+\s*=\s*{lit})*)\s*", self.pageModelArgs):
            e.append("pageModelArgs tek bir sabit (\"X\") veya ad = sabit çiftleri (name = \"X\", order = 1) olmalı.")
        for k, v in self.locatorTemplates.model_dump().items():
            if v and not re.fullmatch(rf"\s*\w+\s*=\s*(?:\{{value\}}|{lit})(?:\s*,\s*\w+\s*=\s*(?:\{{value\}}|{lit}))*\s*", v):
                e.append(f"Locator şablonu {k} 'ad = {{value}}' veya 'ad = \"önek={{value}}\"' (ve isteğe bağlı ad = sabit) biçiminde olmalı.")
        if self.findByExtraArgs.strip() and not re.fullmatch(rf"\s*\w+\s*=\s*{lit}(?:\s*,\s*\w+\s*=\s*{lit})*\s*", self.findByExtraArgs):
            e.append("findByExtraArgs 'ad = sabit' çiftleri olmalı (ör. timeout = 2).")
        bad_s = set(self.unverifiedLocatorStrategies) - set(LOCATOR_STRATEGIES)
        if bad_s:
            e.append(f"unverifiedLocatorStrategies bilinmeyen strateji içeriyor: {', '.join(sorted(bad_s))}.")
        if not is_ident(self.secretHelperClass):
            e.append("secretHelperClass geçerli bir Java sınıf adı olmalı.")
        if self.secretHelperPackage and not is_package(self.secretHelperPackage):
            e.append("secretHelperPackage boş ya da geçerli bir paket adı olmalı.")
        for ln in self.existingPageMethods:
            if ln.strip() and not parse_page_method(ln):
                e.append(f"Mevcut Page metodu satırı anlaşılamadı: '{ln.strip()[:80]}'. Biçim: IDeneme3Page: void clickTransferButton()")
        for k, v in self.actionTemplates.model_dump().items():
            bad_lines = [ln for ln in v.split("\n") if ln.strip() and not ln.rstrip().endswith((";", "{", "}"))]
            if bad_lines:
                e.append(f"Aksiyon şablonu {k}: her satır ';', '{{' veya '}}' ile bitmeli.")
        cls = [v.replace("{name}", "X") for v in (self.stepClassPattern, self.interfacePattern, self.androidClassPattern)]
        if len(set(cls)) < 3:
            e.append("Step, Interface ve Android sınıf adı şablonları birbirinden farklı sınıf adları üretmeli.")
        fw = [self.stepBaseClass, self.pageBaseClass, self.pageModelAnnotation, self.stepAnnotation, self.locatorAnnotation,
              self.elementType] + ([self.pageFieldAnnotation] if self.pageFieldAnnotation else [])
        if len(set(fw)) < len(fw):
            e.append("Framework sınıf/anotasyon adları birbirinden farklı olmalı.")
        if not re.fullmatch(r"[A-Za-z_]\w*(\(\))?", self.appExpression):
            e.append("appExpression bir alan adı (mobileApp) veya parametresiz metot çağrısı (getApp()) olmalı.")
        for k, v in self.locatorTemplates.model_dump().items():
            if v and "{value}" not in v:
                e.append(f"Locator şablonu {k} '{{value}}' içermeli.")
            if set(_PLACEHOLDER.findall(v)) - {"value"}:
                e.append(f"Locator şablonu {k} yalnızca {{value}} kullanabilir.")
        allowed = {"element", "app", "value"}
        for k, v in self.actionTemplates.model_dump().items():
            bad = set(_PLACEHOLDER.findall(v)) - allowed
            if bad:
                e.append(f"Aksiyon şablonu {k} bilinmeyen yer tutucu içeriyor: {', '.join(sorted(bad))}.")
            if v and k in ("TAP", "INPUT_TEXT", "LONG_PRESS") and "{element}" not in v:
                e.append(f"Aksiyon şablonu {k} '{{element}}' içermeli.")
            if v and k == "INPUT_TEXT" and "{value}" not in v:
                e.append("INPUT_TEXT şablonu '{value}' içermeli.")
        for k, v in self.verbs.model_dump().items():
            if not is_ident(v):
                e.append(f"Metot fiili {k} geçerli bir Java adı olmalı.")
        if "{key}" not in self.secretValueTemplate:
            e.append("secretValueTemplate '{key}' içermeli.")
        for f in ("sourceRoot", "featureDir"):
            if not _PATH_RE.match(getattr(self, f)) or ".." in getattr(self, f):
                e.append(f"{f} göreli ve güvenli bir klasör yolu olmalı.")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,20}", self.secretKeyPrefix or "X"):
            e.append("secretKeyPrefix büyük harf, rakam ve _ içermeli.")
        if e:
            raise ValueError(" ".join(e))
        return self

    def names(self):
        n = self.pageName
        return {"step": self.stepClassPattern.replace("{name}", n), "iface": self.interfacePattern.replace("{name}", n),
                "android": self.androidClassPattern.replace("{name}", n)}


def cucumber_text(s: str, limit: int = 40) -> str:
    """Safe Cucumber-expression fragment: no (), {}, / (optional/alternation/parameter syntax) and no quotes."""
    return gauge_text(re.sub(r"[(){}/\[\]^$]", " ", s or ""), limit)


def resolve_pom(cfg: PomConfig, session_name: str) -> PomConfig:
    c = cfg.model_copy(deep=True)
    base = pascal(session_name) or "Recorded"
    if base[0].isdigit():
        base = "Amts" + base
    c.pageName = c.pageName or base
    iface = c.names()["iface"]
    c.pageFieldName = c.pageFieldName or (iface[1:2].lower() + iface[2:] if re.match(r"I[A-Z]", iface) else iface[:1].lower() + iface[1:])
    c.stepPrefix = cucumber_text(c.stepPrefix, 40)
    c.featureName = gauge_text(c.featureName or session_name, 80) or "AMTS"
    c.scenarioName = gauge_text(c.scenarioName or f"{session_name} senaryosu", 80)
    c.tags = " ".join("@" + t for t in (re.sub(r"[^A-Za-z0-9_\-]", "", x.lstrip("@")) for x in c.tags.split()) if t)
    return c


def feature_file_name(session_name: str) -> str:
    return ("_".join(w.lower() for w in words(session_name)) or "recorded") + ".feature"


MOBILDENIZ = {
    "javaVersion": "8", "sourceRoot": "src/test/java", "featureDir": "src/test/resources/features", "generateFeature": True,
    "stepsPackage": "testAutomation.mobile.mobildeniz.tests.V3",
    "contractsPackage": "testAutomation.mobile.mobildeniz.pageModels.contracts.V3",
    "androidPackage": "testAutomation.mobile.mobildeniz.pageModels.android.V3",
    "stepClassPattern": "{name}Test", "interfacePattern": "I{name}Page", "androidClassPattern": "{name}Page",
    "stepBaseClass": "testautomation.mobile.domainlayer.pombase.Test",
    "pageBaseClass": "testautomation.mobile.domainlayer.pombase.Model",
    "pageModelAnnotation": "testautomation.mobile.domainlayer.annotations.PageModel",
    "stepAnnotation": "cucumber.api.java.en.And",
    "locatorAnnotation": "testautomation.mobile.domainlayer.annotations.FindBy",
    "elementType": "testautomation.mobile.domainlayer.contracts.IMobileElement",
    "pageFieldAnnotation": "", "pageFieldModifier": "public", "elementFieldModifier": "public", "appExpression": "mobileApp",
    "resourceIdFormat": "FULL",
    "locatorTemplates": {"RESOURCE_ID": 'locator = "id={value}"', "ACCESSIBILITY_ID": 'locator = "accessibilityId={value}"',
                         "XPATH": 'locator = "xpath={value}"', "UIAUTOMATOR": ""},
    "findByExtraArgs": "timeout = 2", "unverifiedLocatorStrategies": ["ACCESSIBILITY_ID"],
    "actionTemplates": {"TAP": "{element}.click();", "INPUT_TEXT": "{element}.clear();\n{element}.sendKeys({value});",
                        "LONG_PRESS": "{app}.longPressOnElement({element});", "BACK": "{app}.navigateToBack();",
                        "SCROLL_DOWN": "", "SCROLL_UP": "", "SCROLL_LEFT": "", "SCROLL_RIGHT": ""},
    "stepTextStyle": "REGEX", "stepMethodNaming": "STEP_TEXT", "tags": "@amts @android", "asciiOnly": False,
    "scrollManualHint": "Framework kaydırma imzaları hedef element ve tekrar sayısı gerektiriyor (ör. swipeUp(IMobileElement, int), "
                        "swipeUpUntilElementAppears(IMobileElement, int), swipeDownUntilElementAppears(IMobileElement, int)); "
                        "kayıtta bu bilgiler yok, parametre uydurulmadı.",
}

BUILTIN_PROFILES = {
    "GENERIC": {"name": "Cucumber + POM (genel, yapılandırılabilir)", "config": {}},
    "MOBILDENIZ": {"name": "MobilDeniz - Cucumber POM", "config": MOBILDENIZ},
}


def builtin_profiles():
    return [{"id": k, "name": v["name"], "builtin": True, "config": PomConfig(**v["config"]).model_dump()} for k, v in BUILTIN_PROFILES.items()]
