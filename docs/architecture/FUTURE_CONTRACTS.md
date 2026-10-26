# Future module contracts (PLANNED — not implemented)

These are design contracts only. No code exists for them in Phase 1, by design.

## Phase 2 — Locator Engine
```java
public interface LocatorEngine {
    List<LocatorCandidate> candidates(RecordedElement element, ScreenSnapshot snapshot);
    LocatorValidation validateOnDevice(LocatorCandidate candidate, DeviceRef device); // via Recorder Agent
}
public final class LocatorCandidate {
    Strategy strategy;              // ACCESSIBILITY_ID, RESOURCE_ID, STABLE_ATTRIBUTES, UIAUTOMATOR, XPATH, COORDINATES
    String value; double confidence;
    Uniqueness uniqueness;          // checked, matchCount, unique
    Instant validatedAt; List<LocatorCandidate> alternatives;
    Map<String, Double> scores;     // uniqueness, stability, readability, platformCompat, structureDependency, interactable
}
```
Phase 1 already emits `locatorCandidate` objects (schema `$defs/locatorCandidate`) with uniqueness checked against the captured XML only. XPath is never preferred over id-based strategies.

## Phase 3 — AI Screen & Action Understanding
```python
class AiProvider(Protocol):            # provider-agnostic; configured per deployment
    def analyze(self, flow: RedactedFlow, consent: ConsentToken) -> FlowInterpretation: ...

class FlowInterpretation(BaseModel):
    observed_facts: list[str]           # copied from events, never invented
    inferred_meaning: str               # e.g. "Create an EFT transfer ..."
    suggested_assertions: list[SuggestedAssertion]   # status = PENDING_USER_APPROVAL
    unverified_assumptions: list[str]
```
Rules: explicit consent per request; only redacted, text-only data by default; screenshots/XML never auto-uploaded; AI cannot mark verification as passed.

## Phase 4 — Framework-Aware Code Generator
```java
public interface AutomationFrameworkAdapter {
    FrameworkIndex index(Path projectRoot);                       // read-only scan: steps, locators, helpers
    List<StepMatch> findReusableSteps(RecordedStep step, FrameworkIndex idx);
    GaugeSpecDraft generateGaugeSpec(List<RecordedStep> steps, List<StepMatch> matches);
    List<JavaMethodDraft> generateMissingImplementations(List<RecordedStep> unmatched, JavaLevel level); // JAVA_8 | JAVA_11
    ValidationReport validate(PatchProposal patch);                // compile check in sandbox copy
    PatchProposal toPatch(GaugeSpecDraft spec, List<JavaMethodDraft> methods); // unified diff for review
}
```
Never writes to the existing framework, never commits/merges/executes without explicit approval.

## Phase 5 — Jira / Zephyr Scale
Separate adapters (different APIs and auth):
```java
public interface JiraAdapter { List<IssueRef> searchTests(String jql); IssueMeta read(String key); }
public interface ZephyrScaleAdapter {
    List<TestCaseRef> searchTestCases(String projectKey, String query);
    TestCase read(String key);
    void linkAutomation(String key, AutomationLink link);   // only after approval
    void setAutomationStatus(String key, AutomationStatus s);
}
```
Credentials via secure secret storage. No Jira writes in Phase 1.

## iOS (future)
Schema `platform` already allows `IOS`. Planned capture: XCUITest/WebDriverAgent hierarchy + a host-side agent module; manual-touch capture on iOS has no `getevent` equivalent, so fidelity will differ and will be documented separately.
