import re
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from services.codegen.javautil import is_ident, is_package, is_fqcn, pascal, words, gauge_text

_PATH_RE = re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-.]+)*$")


class DriverAccess(BaseModel):
    mode: Literal["STATIC_METHOD", "INHERITED_METHOD"] = "STATIC_METHOD"
    className: str = "com.example.framework.DriverManager"
    methodName: str = "getDriver"
    driverType: Literal["AppiumDriver", "AndroidDriver", "WebDriver"] = "AppiumDriver"


class HelperMethods(BaseModel):
    tap: str = "tap"
    longPress: str = "longPress"
    scroll: str = "scroll"
    swipe: str = "swipe"
    tapAt: str = "tapAt"
    longPressAt: str = "longPressAt"


class ActionHelper(BaseModel):
    mode: Literal["GENERATED", "STATIC", "INHERITED"] = "GENERATED"
    className: str = "AmtsGestures"
    passDriver: bool = True
    methods: HelperMethods = Field(default_factory=HelperMethods)


class CodegenConfig(BaseModel):
    javaVersion: Literal["11", "17", "21"] = "11"
    appiumClientVersion: Literal["8.x", "9.x", "10.x"] = "9.x"
    stepsPackage: str = "com.example.steps"
    stepClassName: str = ""
    baseClass: str = ""
    helperPackage: str = ""
    locatorStorage: Literal["INLINE", "LOCATOR_CLASS"] = "LOCATOR_CLASS"
    locatorClassName: str = ""
    sourceRoot: str = "src/test/java"
    specDir: str = "specs"
    specFileName: str = ""
    stepPrefix: Optional[str] = None
    scenarioName: str = ""
    tags: str = "amts, android"
    waitTimeoutSeconds: int = Field(10, ge=1, le=120)
    asciiOnly: bool = False
    secretKeyPrefix: str = "AMTS_"
    existingStepTexts: List[str] = Field(default_factory=list, max_length=5000)
    driver: DriverAccess = Field(default_factory=DriverAccess)
    helper: ActionHelper = Field(default_factory=ActionHelper)

    @model_validator(mode="after")
    def _check(self):
        errs = []
        if not is_package(self.stepsPackage):
            errs.append("stepsPackage geçerli bir Java paket adı olmalı.")
        if self.helperPackage and not is_package(self.helperPackage):
            errs.append("helperPackage geçerli bir Java paket adı olmalı.")
        for f in ("stepClassName", "locatorClassName"):
            v = getattr(self, f)
            if v and not is_ident(v):
                errs.append(f"{f} geçerli bir Java sınıf adı olmalı.")
        inherited = self.driver.mode == "INHERITED_METHOD" or self.helper.mode == "INHERITED"
        if inherited and not is_fqcn(self.baseClass):
            errs.append("Miras alınan erişim için baseClass tam nitelikli sınıf adı olmalı (ör. com.bank.steps.BaseSteps).")
        if self.baseClass and not is_fqcn(self.baseClass):
            errs.append("baseClass tam nitelikli sınıf adı olmalı.")
        if self.driver.mode == "STATIC_METHOD" and not is_fqcn(self.driver.className):
            errs.append("driver.className tam nitelikli sınıf adı olmalı (ör. com.bank.core.DriverManager).")
        if not is_ident(self.driver.methodName):
            errs.append("driver.methodName geçerli bir Java metot adı olmalı.")
        if self.helper.mode == "STATIC" and not is_fqcn(self.helper.className):
            errs.append("helper.className tam nitelikli sınıf adı olmalı.")
        if self.helper.mode == "GENERATED" and not is_ident(self.helper.className):
            errs.append("Üretilen yardımcı sınıf adı geçerli bir Java sınıf adı olmalı.")
        for k, v in self.helper.methods.model_dump().items():
            if not is_ident(v):
                errs.append(f"helper.methods.{k} geçerli bir Java metot adı olmalı.")
        for f in ("sourceRoot", "specDir"):
            if not _PATH_RE.match(getattr(self, f)) or ".." in getattr(self, f):
                errs.append(f"{f} göreli ve güvenli bir klasör yolu olmalı.")
        if self.specFileName and not re.fullmatch(r"[A-Za-z0-9_\-]+\.spec", self.specFileName):
            errs.append("specFileName yalnızca harf, rakam, _ ve - içermeli ve .spec ile bitmeli.")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,20}", self.secretKeyPrefix or "X"):
            errs.append("secretKeyPrefix büyük harf, rakam ve _ içermeli.")
        if errs:
            raise ValueError(" ".join(errs))
        return self


def resolve(cfg: CodegenConfig, session_name: str) -> CodegenConfig:
    base = pascal(session_name) or "Recorded"
    if base[0].isdigit():
        base = "Amts" + base
    c = cfg.model_copy(deep=True)
    c.stepClassName = c.stepClassName or f"{base}Steps"
    c.locatorClassName = c.locatorClassName or f"{base}Locators"
    c.helperPackage = c.helperPackage or f"{c.stepsPackage}.amts"
    c.specFileName = c.specFileName or ("_".join(w.lower() for w in words(session_name)) or "recorded") + ".spec"
    c.stepPrefix = gauge_text(session_name if c.stepPrefix is None else c.stepPrefix, 40)
    c.scenarioName = gauge_text(c.scenarioName or f"{session_name} senaryosu", 80)
    c.tags = ", ".join(t for t in (re.sub(r"[^A-Za-z0-9_\-]", "", x) for x in c.tags.split(",")) if t)
    return c
