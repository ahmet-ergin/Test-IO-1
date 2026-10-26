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
