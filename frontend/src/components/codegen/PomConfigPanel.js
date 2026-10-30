import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Accordion } from "@/components/ui/accordion";
import { Field, Text, Choice, Toggle, Section, get, setIn } from "@/components/codegen/ConfigPanel";

const Template = ({ cfg, onChange, path, label, rows = 1 }) => (
  <Field label={label}>
    <Textarea data-testid={`cg-${path.replace(/\./g, "-")}`} rows={rows} className="min-h-0 font-mono text-[11px]" value={get(cfg, path) ?? ""}
      placeholder="boş = desteklenmiyor" onChange={(e) => onChange(setIn(cfg, path, e.target.value))} />
  </Field>
);

const MODS = [["private", "private"], ["protected", "protected"], ["public", "public"], ["package", "(paket erişimi)"]];
const ACTIONS = [["TAP", "TAP", 1], ["INPUT_TEXT", "INPUT_TEXT", 2], ["LONG_PRESS", "LONG_PRESS", 1], ["SCROLL_DOWN", "Aşağı kaydırma (listenin altı)", 1],
  ["SCROLL_UP", "Yukarı kaydırma", 1], ["SCROLL_LEFT", "Sola kaydırma", 1], ["SCROLL_RIGHT", "Sağa kaydırma", 1], ["BACK", "BACK", 1]];

export const PomConfigPanel = ({ cfg, onChange, derived }) => {
  const p = { cfg, onChange };
  return (
    <div>
      {cfg.stepBaseClass?.startsWith("com.example.") ? <p data-testid="cg-pom-local-note" className="mb-2 rounded border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-[11px] leading-snug text-amber-500">
        Varsayılan adlar kurgusal örneklerdir (com.example.*). Kendi proje adlarınızı girin; ayarlar yalnızca bu tarayıcıda saklanır ve dış servise gönderilmez.</p>
        : <p data-testid="cg-pom-local-note" className="mb-2 rounded border border-border px-2 py-1.5 text-[11px] leading-snug text-muted-foreground">
        Paket ve sınıf adları büyük/küçük harfe duyarlıdır ve otomatik değiştirilmez. Özelleştirmeler yalnızca bu tarayıcıda saklanır; yerleşik varsayılanlar uygulama kodundadır.</p>}
      <Accordion type="multiple" defaultValue={["general", "framework", "actions"]} data-testid="cg-pom-config-panel">
        <Section value="general" title="Genel">
          <div className="grid grid-cols-2 gap-3">
            <Choice {...p} path="javaVersion" label="Java sürümü" options={[["8", "Java 8"], ["11", "Java 11"]]} />
            <Text {...p} path="pageName" label="Sayfa adı ({name})" placeholder={derived?.pageName || "oturum adından"} />
          </div>
          <div className="grid grid-cols-1 gap-2">
            <Text {...p} path="stepClassPattern" label="Step sınıfı" />
            <Text {...p} path="interfacePattern" label="Interface" />
            <Text {...p} path="androidClassPattern" label="Android sınıfı" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Text {...p} path="sourceRoot" label="Java kaynak klasörü" />
            <Text {...p} path="featureDir" label="Feature klasörü" />
          </div>
          <Toggle {...p} path="generateFeature" label="Türkçe .feature dosyası üret" />
          <div className="grid grid-cols-2 gap-3">
            <Text {...p} path="stepPrefix" label="Adım ön eki (opsiyonel)" hint="Mevcut adımlarla çakışmayı önler." />
            <Text {...p} path="tags" label="Etiketler" />
          </div>
          <Text {...p} path="scenarioName" label="Senaryo adı" placeholder={derived?.scenarioName || "otomatik"} />
          <div className="grid grid-cols-2 gap-3">
            <Choice {...p} path="stepTextStyle" label="Step metni biçimi" options={[["REGEX", "Regex (^…$) — Cucumber 4"], ["EXPRESSION", "Cucumber expression ({string})"]]} />
            <Choice {...p} path="stepMethodNaming" label="Step metot adı" options={[["STEP_TEXT", "Adım metninden (transferOgesineTiklar)"], ["PAGE_METHOD", "Page metodu ile aynı"]]} />
          </div>
          <Toggle {...p} path="asciiOnly" label="Yalnızca ASCII (\u kaçış)" />
        </Section>
        <Section value="packages" title="Paketler">
          <Text {...p} path="stepsPackage" label="Step Definition paketi" />
          <Text {...p} path="contractsPackage" label="Page Interface paketi" />
          <Text {...p} path="androidPackage" label="Android Page paketi" />
        </Section>
        <Section value="framework" title="Framework sınıfları (tam ad)">
          <Text {...p} path="stepBaseClass" label="Step temel sınıfı (extends)" />
          <Text {...p} path="pageBaseClass" label="Page temel sınıfı (extends)" />
          <div className="grid grid-cols-2 gap-3">
            <Text {...p} path="pageModelAnnotation" label="Page Model anotasyonu" />
            <Text {...p} path="pageModelArgs" label="Anotasyon argümanları" placeholder='ör. name = "Demo"' />
          </div>
          <Text {...p} path="stepAnnotation" label="Cucumber step anotasyonu" />
          <div className="grid grid-cols-2 gap-3">
            <Text {...p} path="pageFieldAnnotation" label="Page alanı anotasyonu (ops.)" placeholder="boş = yok" />
            <Choice {...p} path="pageFieldModifier" label="Page alanı erişimi" options={MODS} />
          </div>
          <Text {...p} path="pageFieldName" label="Page alanı adı" placeholder={derived?.pageFieldName || "otomatik"} />
          <div className="grid grid-cols-2 gap-3">
            <Text {...p} path="locatorAnnotation" label="Locator anotasyonu" />
            <Text {...p} path="elementType" label="Element tipi" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Choice {...p} path="elementFieldModifier" label="Element alanı erişimi" options={MODS} />
            <Text {...p} path="appExpression" label="Uygulama nesnesi ({app})" hint="Alan adı veya parametresiz metot: getApp()" />
          </div>
          <p className="text-[11px] text-muted-foreground">Page nesneleri new ile oluşturulmaz; step sınıfındaki alan framework'ünüzün bağlama mekanizmasına bırakılır.</p>
        </Section>
        <Section value="locators" title="Locator şablonları">
          <p className="text-[11px] text-muted-foreground">Anotasyon parantezi içi. {"{value}"} locator değeriyle değiştirilir; tırnak içindeyse değer yalnızca bir kez tırnaklanır
            (ör. locator = "id={"{value}"}"). Değer zaten önekle başlıyorsa önek tekrarlanmaz. Boş = bu strateji desteklenmiyor.</p>
          {["RESOURCE_ID", "ACCESSIBILITY_ID", "XPATH", "UIAUTOMATOR"].map((k) => <Text key={k} {...p} path={`locatorTemplates.${k}`} label={k} placeholder="boş = desteklenmiyor" />)}
          <Text {...p} path="findByExtraArgs" label="Ek anotasyon argümanları" placeholder="ör. timeout = 2 (boş = eklenmez)" />
          <Field label="Framework desteği doğrulanmamış stratejiler (virgülle)" hint="Bu stratejiler kullanılırsa adımda uyarı gösterilir.">
            <Input data-testid="cg-unverifiedLocatorStrategies" className="h-8 font-mono text-xs" value={(cfg.unverifiedLocatorStrategies || []).join(", ")}
              onChange={(e) => onChange(setIn(cfg, "unverifiedLocatorStrategies", e.target.value.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean)))} />
          </Field>
          <Choice {...p} path="resourceIdFormat" label="Resource ID biçimi" options={[["FULL", "Tam (paket:id/ad)"], ["SHORT", "Kısa (ad)"]]} />
        </Section>
        <Section value="actions" title="Aksiyon şablonları">
          <p className="text-[11px] text-muted-foreground">Yer tutucular: {"{element}"}, {"{app}"}, {"{value}"}. Boş şablon = aksiyon desteklenmiyor olarak işaretlenir; metot uydurulmaz.</p>
          {ACTIONS.map(([k, l, r]) => <Template key={k} {...p} path={`actionTemplates.${k}`} label={l} rows={r} />)}
          <Template {...p} path="scrollManualHint" label="Kaydırma şablonu boşsa 'MANUEL UYARLAMA GEREKLİ' açıklaması" rows={3} />
          <div className="grid grid-cols-3 gap-2">{["TAP", "INPUT_TEXT", "LONG_PRESS", "SCROLL", "BACK"].map((k) => <Text key={k} {...p} path={`verbs.${k}`} label={`Fiil: ${k}`} />)}</div>
        </Section>
        <Section value="data" title="Hassas veri & çakışma">
          <Choice {...p} path="secretProvider" label="Şifre/PIN/OTP çözümleme" options={[["HELPER", "Üretilen yardımcı sınıf (ortam değişkeni → -D, eksikse hata)"], ["CUSTOM", "Özel sağlayıcı ifadesi"]]} />
          {cfg.secretProvider === "HELPER" ? <div className="grid grid-cols-2 gap-3">
            <Text {...p} path="secretHelperClass" label="Yardımcı sınıf adı" />
            <Text {...p} path="secretHelperPackage" label="Yardımcı paketi" placeholder="boş = step paketi" />
          </div> : <Text {...p} path="secretValueTemplate" label="Özel sağlayıcı ifadesi" hint="{key} feature'daki anahtar adıyla değiştirilir; eksik değer için hata vermesi sağlayıcının sorumluluğundadır." />}
          <Text {...p} path="secretKeyPrefix" label="Anahtar ön eki" />
          <Field label="Mevcut Cucumber adım ifadeleri (satır başına bir)" hint="Örn: {string} butonuna tıklar">
            <Textarea data-testid="cg-pom-existingStepTexts" rows={4} className="font-mono text-xs" value={(cfg.existingStepTexts || []).join("\n")}
              onChange={(e) => onChange(setIn(cfg, "existingStepTexts", e.target.value.split("\n")))} />
          </Field>
          <Field label="Projemdeki mevcut sınıf adları (satır başına bir, tam ad veya kısa ad)" hint="Üretilen sınıf adı eşleşirse uyarı verilir; kaynak kod gerekmez.">
            <Textarea data-testid="cg-existingClassNames" rows={3} className="font-mono text-xs" value={(cfg.existingClassNames || []).join("\n")}
              onChange={(e) => onChange(setIn(cfg, "existingClassNames", e.target.value.split("\n")))} />
          </Field>
          <Field label="Mevcut Page Interface metotları (satır başına bir)" hint="Biçim: IDeneme3Page: void clickTransferButton() — interface ve imza birebir eşleşirse metot yeniden üretilmez.">
            <Textarea data-testid="cg-existingPageMethods" rows={3} className="font-mono text-xs" value={(cfg.existingPageMethods || []).join("\n")}
              onChange={(e) => onChange(setIn(cfg, "existingPageMethods", e.target.value.split("\n")))} />
          </Field>
        </Section>
      </Accordion>
    </div>
  );
};
