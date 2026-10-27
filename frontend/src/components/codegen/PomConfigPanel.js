import { Textarea } from "@/components/ui/textarea";
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
      <p data-testid="cg-pom-local-note" className="mb-2 rounded border border-amber-500/30 bg-amber-500/5 px-2 py-1.5 text-[11px] leading-snug text-amber-500">
        Varsayılan adlar kurgusal örneklerdir (com.example.*). Kendi proje adlarınızı girin; ayarlar yalnızca bu tarayıcıda saklanır ve dış servise gönderilmez.</p>
      <Accordion type="multiple" defaultValue={["general", "framework", "actions"]} data-testid="cg-pom-config-panel">
        <Section value="general" title="Genel">
          <div className="grid grid-cols-2 gap-3">
            <Choice {...p} path="javaVersion" label="Java sürümü" options={[["8", "Java 8"], ["11", "Java 11"]]} />
            <Text {...p} path="pageName" label="Sayfa adı ({name})" placeholder={derived?.pageName || "oturum adından"} />
          </div>
          <div className="grid grid-cols-3 gap-2">
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
          <p className="text-[11px] text-muted-foreground">Anotasyon parantezi içi; {"{value}"} locator değeriyle değiştirilir. Boş = bu strateji desteklenmiyor.</p>
          {["RESOURCE_ID", "ACCESSIBILITY_ID", "XPATH", "UIAUTOMATOR"].map((k) => <Text key={k} {...p} path={`locatorTemplates.${k}`} label={k} placeholder="boş = desteklenmiyor" />)}
          <Choice {...p} path="resourceIdFormat" label="Resource ID biçimi" options={[["FULL", "Tam (paket:id/ad)"], ["SHORT", "Kısa (ad)"]]} />
        </Section>
        <Section value="actions" title="Aksiyon şablonları">
          <p className="text-[11px] text-muted-foreground">Yer tutucular: {"{element}"}, {"{app}"}, {"{value}"}. Boş şablon = aksiyon desteklenmiyor olarak işaretlenir; metot uydurulmaz.</p>
          {ACTIONS.map(([k, l, r]) => <Template key={k} {...p} path={`actionTemplates.${k}`} label={l} rows={r} />)}
          <div className="grid grid-cols-3 gap-2">{["TAP", "INPUT_TEXT", "LONG_PRESS", "SCROLL", "BACK"].map((k) => <Text key={k} {...p} path={`verbs.${k}`} label={`Fiil: ${k}`} />)}</div>
        </Section>
        <Section value="data" title="Hassas veri & çakışma">
          <Text {...p} path="secretValueTemplate" label="Gizli değer çözümleme" hint="{key} feature'daki anahtar adıyla değiştirilir." />
          <Text {...p} path="secretKeyPrefix" label="Anahtar ön eki" />
          <Field label="Mevcut Cucumber adım ifadeleri (satır başına bir)" hint="Örn: {string} butonuna tıklar">
            <Textarea data-testid="cg-pom-existingStepTexts" rows={4} className="font-mono text-xs" value={(cfg.existingStepTexts || []).join("\n")}
              onChange={(e) => onChange(setIn(cfg, "existingStepTexts", e.target.value.split("\n")))} />
          </Field>
        </Section>
      </Accordion>
    </div>
  );
};
