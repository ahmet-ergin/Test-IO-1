# Kod Üreteci — Java + Appium 2 + Gauge

Kayıtlı bir AMTS oturumundan mevcut framework'e eklenecek dosyalar üretir. Yeni Maven/Gauge projesi, yeni bağımlılık veya yeni Appium oturumu oluşturmaz; uygulamayı yeniden başlatmaz.

## Akış
1. **Oturum seçimi** → `POST /api/codegen/plan`: adımlar, seçili/alternatif locator'lar, uyarılar, desteklenmeyen adımlar (henüz kod üretilmez).
2. **Kodu üret** → `POST /api/codegen/generate`: dosyalar + otomatik doğrulama.
3. **Önizleme & düzenleme** (tarayıcıda) → `POST /api/codegen/validate` düzenlenmiş içeriği yeniden doğrular.
4. **ZIP** → `POST /api/codegen/zip`: gönderilen (düzenlenmiş) dosyalar sunucuda yeniden doğrulanır; `AMTS_VALIDATION.md` + `amts-validation.json` eklenir, durum `X-AMTS-Validation` başlığında döner.

Diğer: `GET /api/codegen/sessions`, `GET /api/codegen/defaults`.

## Üretilen dosyalar
- `specs/<oturum>.spec` — Türkçe adımlar, ön ek (varsayılan: oturum adı) ile çakışmaya karşı benzersiz.
- `src/test/java/<paket>/<Oturum>Steps.java` — `@Step` metotları; driver yalnızca yapılandırılan erişimle alınır.
- `<Oturum>Locators.java` (opsiyonel) — `public static final By` sabitleri; alternatifler yorum satırında.
- `amts/AmtsGestures.java` (opsiyonel) — W3C Actions tabanlı tap/longPress/scroll/swipe/tapAt/longPressAt; belirsiz (çoklu) eşleşmede hata verir.
- `AMTS_INTEGRATION.md`.

## Eşleme
RESOURCE_ID→`AppiumBy.id`, ACCESSIBILITY_ID→`AppiumBy.accessibilityId`, UIAUTOMATOR→`AppiumBy.androidUIAutomator`, XPATH→`AppiumBy.xpath`, COORDINATES→W3C Actions.
TAP / LONG_PRESS (kayıtlı süre, 600–5000 ms) / SCROLL (yön kayıttan; yoksa DOWN + uyarı) desteklenir. Diğer aksiyonlar (INPUT_TEXT, BACK, …) atlanmaz: spec'te `AMTS UYARI` satırı + `UnsupportedOperationException` fırlatan step.
Maskeli/şifre alanları: değer koda yazılmaz, `AMTS_<ALAN>` test verisi anahtarı parametre olarak geçer; maskeli locator'lar kullanılmaz.

## Yapılandırma
Java 11/17/21, java-client 8.x/9.x/10.x, step paketi/sınıfı, kaynak & spec klasörü, driver erişimi (statik metot veya temel sınıftan miras; dönüş tipi AppiumDriver/AndroidDriver/WebDriver), yardımcılar (üretilen sınıf / mevcut statik sınıf / temel sınıf metotları, metot adları, driver parametresi), locator saklama (ayrı sınıf / inline), ön ek, etiketler, bekleme süresi, ASCII-only, test verisi anahtar ön eki, mevcut step metinleri (çakışma kontrolü).

## Doğrulama (DOĞRULANDI yalnızca hepsi geçerse)
- `gauge_match`: her spec adımı tam bir `@Step` ile eşleşir, kullanılmayan/tekrar eden step yok, parametre sayıları uyumlu.
- `step_collisions`: girilen mevcut step metinleriyle çakışma yok.
- `javac`: dosya yolu ↔ package/sınıf uyumu + `javac --release <Java>` ile java-client 9.5.0, Selenium 4.34.0, gauge-java 0.11.1 (`backend/codegen_lib`) karşısında derleme. Framework sınıflarınız (driver, temel sınıf, yardımcı) **yalnızca derleme için stub** ile temsil edilir.
- Sunucu javac'ı seçilen sürümü desteklemiyorsa (Java 21 → 17) sonuç `PARTIAL` / **DOĞRULANMADI**; javac yoksa `SKIPPED` / DOĞRULANMADI.

## Sınırlamalar
- Gerçek framework imzalarınız stub'lardan farklıysa projenizde ayrıca derleyin; gerçek cihazda Gauge çalıştırması AMTS içinde yapılmaz (doğrulanmadı).
- Doğrulama yalnızca java-client 9.5.0'a karşı yapılır; 8.x/10.x seçimi bilgi amaçlıdır.
- Üretim ortamında JDK yoksa doğrulama "DOĞRULANMADI" döner.
- Kod Üreteci ekranı yalnızca Türkçe.

---

# Profil 2 — Cucumber + Page Object Model (yapılandırılabilir)

Kurum içi framework adları paylaşılamadığı için tüm adlar ayarlanabilir; varsayılanlar kurgusaldır (`com.example.*`). Ayarlar yalnızca tarayıcıda (`amts.codegen.pom.config.v1`) saklanır. Gauge profili değişmedi.

API: `GET /api/codegen/pom/defaults`, `POST /api/codegen/pom/{plan|generate|validate|zip}` (gövde: `{sessionId, config, files?}`).

## Çıktılar
- `src/test/resources/features/<oturum>.feature`: `# language: tr`, `Diyelim ki` / `Ve` adımları (opsiyonel).
- Step Definition (`stepsPackage`): `extends <stepBaseClass>`, `@<stepAnnotation>("...")`, yalnızca `<pageField>.metot()` çağrıları; page alanı `new` ile oluşturulmaz.
- Page Interface (`contractsPackage`): `@<pageModelAnnotation>`, yalnızca metot imzaları.
- Android Page (`androidPackage`): `extends <pageBaseClass> implements <Interface>`, `@<locatorAnnotation>(<şablon>) <elementType> alan;`, aksiyonlar şablonlardan.
- Her Java dosyasında `// <amts:members>` … `// </amts:members>`: mevcut sınıfa eklemek için "Üyeleri kopyala".

## Şablonlar
- Locator: `RESOURCE_ID: id = {value}`, `ACCESSIBILITY_ID: accessibilityId = {value}`, `XPATH: xpath = {value}`, `UIAUTOMATOR: (boş)`. Boş = strateji desteklenmiyor. Seçili locator ifade edilemiyorsa öncelik RESOURCE_ID > ACCESSIBILITY_ID > XPATH > UIAUTOMATOR ile ilk desteklenen alternatif kullanılır ve uyarı verilir.
- Aksiyon (`{element}`, `{app}`, `{value}`): TAP, INPUT_TEXT, LONG_PRESS, SCROLL_DOWN/UP/LEFT/RIGHT, BACK. Boş/eksik şablon veya bilinmeyen aksiyon olursa adım işaretlenir ve page metodu `UnsupportedOperationException` fırlatır; metot uydurulmaz.
- Hassas değerler: feature'da anahtar (`AMTS_PIN_INPUT`), step'te `secretValueTemplate` (varsayılan `System.getenv({key})`).

## Doğrulama
- `structure`: paket/import, `@PageModel`, extends/implements, her `@FindBy` bir element alanında, interface metotlarının hepsi uygulanmış, step sınıfında locator/element/app/driver ve `new` yok.
- `feature_match`: her feature adımı tam bir Cucumber ifadesiyle eşleşir; `step_collisions`: girilen mevcut ifadelerle belirsizlik/çakışma yok.
- `java_syntax`: `javac --release 8|11`, kurum içi sınıflar yerine yerel stub'larla (şablonlardan türetilen metot adları, `Object...` parametreler). Cucumber `io.cucumber.java.en.And` gerçek jar'dan gelir (cucumber-java 7.20.1).
- `framework_compile`: her zaman **NOT_VERIFIED**. En iyi genel durum **STRUCTURE_VERIFIED**'dır, hiçbir zaman VERIFIED değildir.
