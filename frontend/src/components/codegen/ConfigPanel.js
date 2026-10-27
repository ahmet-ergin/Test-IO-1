import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

export const get = (o, path) => path.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
export const setIn = (o, path, v) => {
  const [k, ...rest] = path.split(".");
  return { ...o, [k]: rest.length ? setIn(o[k] || {}, rest.join("."), v) : v };
};

export const Field = ({ label, hint, children }) => (
  <div className="space-y-1">
    <Label className="text-xs text-muted-foreground">{label}</Label>
    {children}
    {hint && <p className="text-[11px] leading-snug text-muted-foreground/80">{hint}</p>}
  </div>
);

export const Text = ({ cfg, onChange, path, label, hint, placeholder }) => (
  <Field label={label} hint={hint}>
    <Input data-testid={`cg-${path.replace(/\./g, "-")}`} className="h-8 font-mono text-xs" value={get(cfg, path) ?? ""}
      placeholder={placeholder} onChange={(e) => onChange(setIn(cfg, path, e.target.value))} />
  </Field>
);

export const Choice = ({ cfg, onChange, path, label, options, hint }) => (
  <Field label={label} hint={hint}>
    <Select value={String(get(cfg, path))} onValueChange={(v) => onChange(setIn(cfg, path, v))}>
      <SelectTrigger data-testid={`cg-${path.replace(/\./g, "-")}`} className="h-8 text-xs"><SelectValue /></SelectTrigger>
      <SelectContent>{options.map(([v, l]) => <SelectItem key={v} value={v} data-testid={`cg-${path.replace(/\./g, "-")}-opt-${v}`}>{l}</SelectItem>)}</SelectContent>
    </Select>
  </Field>
);

export const Toggle = ({ cfg, onChange, path, label }) => (
  <label className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
    {label}
    <Switch data-testid={`cg-${path.replace(/\./g, "-")}`} checked={!!get(cfg, path)} onCheckedChange={(v) => onChange(setIn(cfg, path, v))} />
  </label>
);

export const Section = ({ value, title, children }) => (
  <AccordionItem value={value} className="border-border">
    <AccordionTrigger data-testid={`cg-section-${value}`} className="py-2.5 text-xs font-semibold uppercase tracking-wider hover:no-underline">{title}</AccordionTrigger>
    <AccordionContent className="space-y-3 pb-4">{children}</AccordionContent>
  </AccordionItem>
);

const METHODS = ["tap", "longPress", "scroll", "swipe", "tapAt", "longPressAt"];

export const ConfigPanel = ({ cfg, onChange, derived }) => {
  const p = { cfg, onChange };
  const needsBase = cfg.driver.mode === "INHERITED_METHOD" || cfg.helper.mode === "INHERITED";
  return (
    <Accordion type="multiple" defaultValue={["general", "driver", "helper"]} data-testid="cg-config-panel">
      <Section value="general" title="Genel">
        <div className="grid grid-cols-2 gap-3">
          <Choice {...p} path="javaVersion" label="Java sürümü" options={[["11", "Java 11"], ["17", "Java 17"], ["21", "Java 21"]]} />
          <Choice {...p} path="appiumClientVersion" label="Appium java-client" options={[["8.x", "8.x"], ["9.x", "9.x"], ["10.x", "10.x"]]} />
        </div>
        <Text {...p} path="stepsPackage" label="Step paket adı" placeholder="com.bank.mobile.steps" />
        <div className="grid grid-cols-2 gap-3">
          <Text {...p} path="stepClassName" label="Step sınıf adı" placeholder={derived?.stepClassName || "otomatik"} />
          <Text {...p} path="sourceRoot" label="Java kaynak klasörü" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Text {...p} path="specDir" label="Spec klasörü" />
          <Text {...p} path="specFileName" label="Spec dosya adı" placeholder={derived?.specFileName || "otomatik"} />
        </div>
        <Text {...p} path="scenarioName" label="Senaryo adı" placeholder={derived?.scenarioName || "otomatik"} />
        <div className="grid grid-cols-2 gap-3">
          <Text {...p} path="stepPrefix" label="Gauge adım ön eki" placeholder={derived?.stepPrefix || "oturum adı"} hint="Step metinlerinin mevcut adımlarla çakışmasını önler." />
          <Text {...p} path="tags" label="Etiketler" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Bekleme süresi (sn)"><Input data-testid="cg-waitTimeoutSeconds" type="number" min={1} max={120} className="h-8 text-xs"
            value={cfg.waitTimeoutSeconds} onChange={(e) => onChange(setIn(cfg, "waitTimeoutSeconds", Number(e.target.value) || 1))} /></Field>
          <div className="pt-6"><Toggle {...p} path="asciiOnly" label="Yalnızca ASCII (\u kaçış)" /></div>
        </div>
      </Section>
      <Section value="driver" title="Driver erişimi">
        <Choice {...p} path="driver.mode" label="Driver nasıl alınır?" options={[["STATIC_METHOD", "Statik metot (ör. DriverManager.getDriver())"], ["INHERITED_METHOD", "Temel sınıftan miras alınan metot"]]} />
        {cfg.driver.mode === "STATIC_METHOD" && <Text {...p} path="driver.className" label="Driver sınıfı (tam ad)" placeholder="com.bank.core.DriverManager" />}
        <div className="grid grid-cols-2 gap-3">
          <Text {...p} path="driver.methodName" label="Metot adı" />
          <Choice {...p} path="driver.driverType" label="Dönüş tipi" options={[["AppiumDriver", "AppiumDriver"], ["AndroidDriver", "AndroidDriver"], ["WebDriver", "WebDriver"]]} />
        </div>
        <Text {...p} path="baseClass" label={`Temel step sınıfı (tam ad)${needsBase ? " — gerekli" : " — opsiyonel"}`} placeholder="com.bank.steps.BaseSteps" />
        <p className="text-[11px] text-muted-foreground">Üretilen kod yeni Appium oturumu açmaz; yalnızca bu erişim ile mevcut driver'ı kullanır.</p>
      </Section>
      <Section value="helper" title="Ortak aksiyon metotları">
        <Choice {...p} path="helper.mode" label="TAP / SCROLL / LONG_PRESS nasıl çağrılsın?" options={[
          ["GENERATED", "AMTS yardımcı sınıfı üret (W3C Actions)"], ["STATIC", "Mevcut statik yardımcı sınıfım"], ["INHERITED", "Temel sınıftaki metotlar"]]} />
        {cfg.helper.mode !== "INHERITED" && <Text {...p} path="helper.className" label={cfg.helper.mode === "GENERATED" ? "Yardımcı sınıf adı" : "Yardımcı sınıf (tam ad)"} />}
        {cfg.helper.mode === "GENERATED" && <Text {...p} path="helperPackage" label="Yardımcı paket" placeholder={derived?.helperPackage || "stepsPackage.amts"} />}
        {cfg.helper.mode !== "GENERATED" && <>
          <Toggle {...p} path="helper.passDriver" label="İlk parametre olarak driver gönder" />
          <div className="grid grid-cols-2 gap-3">{METHODS.map((m) => <Text key={m} {...p} path={`helper.methods.${m}`} label={m} />)}</div>
          <p className="text-[11px] text-muted-foreground">Beklenen imzalar: tap(By), longPress(By, Duration), scroll(By, String yön), tapAt(int, int), longPressAt(int, int, Duration), swipe(int, int, int, int, Duration).</p>
        </>}
      </Section>
      <Section value="locators" title="Locator'lar">
        <Choice {...p} path="locatorStorage" label="Locator'lar nerede tutulsun?" options={[["LOCATOR_CLASS", "Ayrı locator sınıfında"], ["INLINE", "Doğrudan step içinde"]]} />
        {cfg.locatorStorage === "LOCATOR_CLASS" && <Text {...p} path="locatorClassName" label="Locator sınıf adı" placeholder={derived?.locatorClassName || "otomatik"} />}
      </Section>
      <Section value="data" title="Hassas veri & çakışma">
        <Text {...p} path="secretKeyPrefix" label="Test verisi anahtar ön eki" hint="Şifre/OTP değerleri koda yazılmaz; bu ön ekle anahtar üretilir." />
        <Field label="Projemdeki mevcut Gauge step metinleri (satır başına bir)" hint="Çakışma kontrolü için. Örn: Kullanıcı <ad> ile giriş yapar">
          <Textarea data-testid="cg-existingStepTexts" rows={4} className="font-mono text-xs" value={(cfg.existingStepTexts || []).join("\n")}
            onChange={(e) => onChange(setIn(cfg, "existingStepTexts", e.target.value.split("\n")))} />
        </Field>
      </Section>
    </Accordion>
  );
};
