# Bordro / Puantaj Hesaplayıcı — Proje Tanıtımı (Frontend)

Bu metin Next.js frontend ekibine ürünü ve ekran mantığını anlatmak içindir. Teknik endpoint detayları için: [`FRONTEND_API.md`](./FRONTEND_API.md).

---

## Bu proje nedir?

**Meyer PDKS**’ten dışa aktarılan puantaj dosyalarını (Excel/CSV) yükleyip, personel bazında **bordroya hazır çalışma süresi özetine** dönüştüren bir uygulamadır.

Yapmaz:
- Canias / ERP’ye doğrudan bağlanmaz
- Maaş / bordro tutarı hesaplamaz
- Kullanıcı dosyayı kendisi yükler; sunucu dosyayı kalıcı saklamaz

Yapar:
- Ham puantajı okur
- İzin, rapor, ücretsiz izin ve devamsızlığı ayırır
- Haftalık **45 saat** kuralını uygular (eksik NM varsa hafta sonu FM → NM aktarımı)
- Pazar kesintisi durumunu gösterir
- Günlük / haftalık / aylık özet ve Excel rapor üretir

Kaynak sistem: **Meyer**. Hedef kullanım: İK / bordro hazırlığı; çıktılar sonraki ERP sürecine manuel veya entegrasyonla taşınabilir.

---

## Ürün yapısı: iki ana ekran

Frontend’de Streamlit demosundaki gibi **iki ayrı sayfa / route** düşünülmelidir. Ortak nokta: kullanıcı bir Meyer dosyası yükler; backend hesabı yapar; UI sonucu gösterir.

### 1) Puantaj Hesaplama

**Amaç:** Tek personelin (veya toplu dosyadan seçilen kişinin) dönem içi mesaisini detaylı görmek ve gerekirse ham veriyi düzeltmek.

**Akış:**
1. Dosya yükle (`.csv` / `.xlsx` / `.xls`)
2. Dosya **toplu** ise → personel listesi → bir kişi seç
3. Dosya **tekil** ise → doğrudan hesaplama ekranı
4. Özet metrikler + izin dağılımı + günlük tablo + haftalık tablo
5. İsteğe bağlı: ham satırları düzenle → anında yeniden hesapla
6. İsteğe bağlı: günlük özeti CSV indir

**Kullanıcıya gösterilen başlıca kavramlar:**
- **NM** — normal mesai
- **FM** — fazla mesai
- **Gün durumu** — Çalışma / Ücretli İzin·Rapor / Ücretsiz İzin / Devamsızlık / Hafta Sonu
- **Pazar durumu** — Hak Edildi / Yanar (kesinti)
- **ISO hafta** — Pazartesi–Pazar; ay başı/sonu haftaları “kısmi” olabilir

### 2) Puantaj Raporu V2 (Aylık rapor)

**Amaç:** Tüm personel için seçilen ayın **yatay puantaj matrisi** ve özetlerini üretmek; biçimlendirilmiş Excel indirmek.

**Akış:**
1. Dosya yükle (Meyer kişi-gün veya Sakra tarzı yatay Excel de desteklenir)
2. Rapor dönemini seç (örn. `06.2026`)
3. Sekmeler: Aylık Puantaj · Personel Özeti · Haftalık Kontrol · Günlük Detay
4. Personel adı / sicil ile client-side arama
5. Excel raporu indir

**Matris hücreleri:**
- Çalışılan günde: o günün çalışma saati (NM + FM özeti)
- Diğer günlerde: durum kodu (`T`, `Z`, `Y`, `Ü`, `R`, `M`, `A3`, …) — efsane API `meta` ve rapor ekranında vardır

---

## Girdi dosyası (kısaca)

| Alan grubu | Örnek sütunlar |
|------------|----------------|
| Kimlik | `sicilno`, `Ad`, `Soyad`, `Firma`, `Bölüm`, `Pozisyon` |
| Gün | `mesaitarih`, `Giriş`, `Çıkış` |
| Süre | `MS`, `NM`, `FM` |
| İzin / rapor | `IZS`, `YIZS`, `SGKIZS`, `UCZIZS`, `RM`, `EM`, `İzin Açıklama` |

CSV’ler genelde `;` ayraçlıdır. Boş / anlamsız hücrelerde Meyer bazen `#__#` yazar; sistem bunları 0 saat sayar.

---

## Bilmeniz gereken iş kuralları (UI metni için)

Bunları frontend’de yeniden hesaplamanız gerekmez; backend uygular. Kullanıcıya “Nasıl çalışır?” metninde özetlenebilir:

1. **45 saat kuralı** — Hafta içi NM 45’in altındaysa, aynı haftanın hafta sonu FM’sinden eksik kısım NM’ye aktarılır.
2. **İzin ayrımı** — Ücretli izin / yıllık / SGK raporu / ücretsiz izin sütun ve açıklamalardan ayrılır.
3. **Devamsızlık** — Hafta içi beklenen süre (varsayılan 9 saat veya `MS`) karşılanmazsa ve izin yoksa (`M`).
4. **Pazar kesintisi** — Yalnızca mazeretsiz tam gün (~9 saat) devamsızlıkta o haftanın pazarı kesilir (`Z`). Rapor, yıllık/ücretli mazeret izni, işveren izni ve resmi tatiller **çalışılmış sayılır**; hafta tatili hakkı düşmez (`T`).
5. **Cumartesi** — Mesai (NM/FM) yoksa `A3` (serbest zaman); mesai varsa saat yazılır.
6. **Hafta sayısı** — Takvim ayına sabit değildir; dosyadaki tarihlerin düştüğü ISO haftaları sayılır.

---

## Mimari (frontend bakışı)

```
[ Next.js UI ]  --HTTP-->  [ FastAPI backend (Vercel) ]  -->  [ puantaj_calc / puantaj_report ]
```

- Backend **stateless**: her istekte dosya (veya düzenlenmiş satır JSON’u) yeniden gönderilir; oturum / job_id yok.
- Yerelde eski Streamlit demo hâlâ var: `streamlit run streamlit_demo.py` — ürün referansı / davranış karşılaştırması için; production UI Next.js olacak.
- Auth şu an yok; ileride eklenebilir.

**Önerilen route’lar:**
- `/hesaplama` → Puantaj Hesaplama
- `/rapor` → Aylık Puantaj Raporu

**Bağlantı sözleşmesi:** tüm istek/yanıt tipleri, örnek `fetch` kodları ve hata kodları → [`FRONTEND_API.md`](./FRONTEND_API.md). Canlı şema → `{API_BASE}/docs`.

---

## Başarı kriteri (frontend)

- İki ekranın Streamlit demodaki akışa denk UX’i
- Toplu dosyada personel seçimi + tekil dosyada doğrudan sonuç
- Hesaplama ekranında özet / günlük / haftalık / izin kırılımının okunaklı gösterimi
- Rapor ekranında dönem seçimi + dört tablo + Excel indirme
- API hata mesajlarının (`detail.code` / `message`) kullanıcıya anlaşılır yansıması
- Saat alanlarında backend’in verdiği `HH:MM` (`*_fmt`) formatının kullanılması

---

## Tek cümlelik özet

> Kullanıcı Meyer puantaj dosyasını yükler; sistem izin ve 45 saat kurallarını uygulayarak personel bazlı mesai özeti ve aylık puantaj raporu üretir; Next.js bu sonuçları gösterir, FastAPI hesabı yapar.
