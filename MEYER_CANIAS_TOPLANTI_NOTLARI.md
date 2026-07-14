# Meyer – Canias Entegrasyon Toplantısı Hazırlığı

## 1. Projenin kısa tanımı

Bu proje, Meyer PDKS’den Excel/CSV olarak dışa aktarılan puantaj verilerini yükleyip personel bazında bordroya hazırlanan çalışma süresine dönüştüren bir Streamlit uygulamasıdır. Uygulama; ham puantajı okur, izin ve rapor kodlarını yorumlar, eksik çalışma sürelerini hesaplar, haftalık 45 saat kuralını uygular ve günlük/haftalık özetler üretir.

Mevcut kullanımda Meyer’den alınan dosya uygulamaya manuel yüklenmektedir. Kullanıcı gerektiğinde NM, FM ve izin alanlarını ekranda düzeltir; sonuç olarak personel bazında günlük özet CSV’si indirip sonraki bordro/ERP sürecinde kullanır. Uygulama şu anda Canias’a doğrudan bağlanmamakta, bordro hesaplamasının tamamını da üstlenmemektedir.

## 2. Mevcut projenin teknik özeti

### Girdi

- Toplu veya tek personel Meyer `.xlsx`, `.xls` veya noktalı virgülle ayrılmış `.csv` dosyası.
- Personel kimliği ve temel bilgiler: `sicilno`, `Ad`, `Soyad`, `Firma`, `Bölüm`, `Pozisyon` vb.
- Tarih ve devam bilgileri: `mesaitarih`, `Giriş`, `Çıkış`, `MS`, `NM`, `FM`.
- İzin/rapor bilgileri: `IZS`, `YIZS`, `SGKIZS`, `UCZIZS`, `RM`, `EM`, `İzin Açıklama`.

Örnek Meyer dosyasında 35 sütunlu tek bir `Sayfa1` bulunmaktadır. Dosyadaki yapı, uygulamanın Meyer’in rapor/export formatına sıkı şekilde bağlı olduğunu gösterir.

### Hesaplama kuralları

- `NM` ve `FM` süreleri saat cinsine çevrilir.
- Hafta içi çalışma 45 saatin altında kalırsa, aynı haftanın hafta sonu `FM` süresinden eksik kısım `NM` içine aktarılır.
- `IZS`, `YIZS`, `SGKIZS`, `RM`, `EM` ve `UCZIZS` alanları izin/rapor/ücretsiz izin ayrımında kullanılır.
- `NM` yoksa ve izin bilgisi varsa gün ücretli izin/rapor veya ücretsiz izin olarak sınıflandırılır.
- Hafta içi beklenen süre varsayılan olarak 9 saat; `MS` varsa `MS` süresi olarak kabul edilir.
- Tam günlük devamsızlık ve hafta bazında pazar kesintisi ayrıca raporlanır.
- ISO haftaları üzerinden haftalık özet üretilir; ay başı/sonu haftaları kısmi hafta olarak gösterilir.

### Çıktı

- Personel listesi ve personel bazlı detay ekranı.
- Günlük özet: tarih, gün durumu, izin türü, güncel NM/FM, ücretli/ücretsiz izin ve devamsızlık.
- Haftalık mesai dağılımı: hafta içi NM, hafta sonu FM, toplam NM/FM ve pazar durumu.
- İzin/rapor kırılımı: çalışma, yıllık izin, ücretli izin, SGK raporu, ücretsiz izin, devamsızlık ve hafta sonu.
- Kullanıcı tarafından düzenlenen verinin personel bazında CSV olarak indirilmesi.

## 3. Meyer ve Canias araştırma sonucu

Meyer’in resmi PDKS sayfası, yazılımın çeşitli API’ler aracılığıyla İK, puantaj, finans, ERP ve CRM uygulamalarına veri gönderip alabileceğini; maaş, hak ediş, puantaj ve bordro için gerekli verilerin otomatik aktarılabileceğini belirtiyor. Aynı sayfada çift taraflı entegrasyon ve Microsoft SQL veritabanı kullanımı da ifade ediliyor.

Meyer’in resmi yüz tanıma/entegrasyon sayfası Canias’ı açıkça uyumlu ERP’ler arasında sayıyor ve kuruma özel entegrasyon/modül geliştirilebileceğini belirtiyor. Bu, doğrudan Canias entegrasyonu için güçlü bir başlangıç sinyali olmakla birlikte, hazır ürün bağlantısının varlığını tek başına kanıtlamaz.

Canias’ın resmi WSR sayfasına göre WSR modülü, sistemler arasında platform bağımsız veri alışverişi, web servis tanımları ve kullanıcı yetkilendirmesi sağlar; TROIA üzerinden modüllerden web servis çağrıları kurulabilir. Canias’ın ERP açıklamasında da XML, EDI, web servis ve harici API entegrasyon katmanlarından söz ediliyor.

Bu nedenle toplantı için iki uygulanabilir yol var:

1. **Tercih edilen yol – Meyer → Canias doğrudan entegrasyonu:** Meyer puantajı hesaplar veya onaylanmış puantajı sağlar; sonuç Canias’ın İK/bordro süreçlerine web servis/API veya güvenli dosya aktarımıyla otomatik yazılır.
2. **Alternatif yol – mevcut uygulama entegrasyon katmanı:** Meyer export’u mevcut uygulamaya otomatik alınır; mevcut hesaplama kuralları çalıştırılır; normalize edilmiş bordro girdileri Canias WSR/API, XML/CSV aktarımı veya Canias’a özel bir ara servis üzerinden gönderilir.

## 4. Toplantıda alınması gereken teknik cevaplar

### Meyer’e sorulacaklar

1. Canias için hazır ve desteklenen bir entegrasyonunuz var mı, yoksa proje bazlı geliştirme mi yapılacak?
2. Entegrasyon arayüzü nedir: REST API, SOAP, web servis, doğrudan SQL, SFTP, zamanlanmış dosya veya başka bir yöntem mi?
3. Güncel API/Web Service dokümanı, örnek request/response, WSDL/OpenAPI ve test ortamı paylaşılabilir mi?
4. Hangi veriler alınabilir/gönderilebilir: personel kartı, sicil no, firma, bölüm, vardiya, giriş-çıkış, puantaj, fazla mesai, izin, rapor, ücretsiz izin, devamsızlık, bordro sonucu?
5. Veriler ham hareket olarak mı, Meyer hesaplamasından geçmiş onaylı puantaj olarak mı aktarılacak?
6. `NM`, `FM`, `MS`, `IZS`, `YIZS`, `SGKIZS`, `UCZIZS`, `RM`, `EM` alanlarının resmi anlamları, birimleri ve yuvarlama kuralları nedir?
7. İzin türleri ve bordro kodları için sabit kod listesi/versiyonlama var mı?
8. Canias personel sicil numarası ile Meyer `sicilno` nasıl eşleştirilecek? Firma, alt firma ve işyeri kodları nasıl taşınacak?
9. Onay mekanizması var mı? Onaylanmış puantaj kilitleniyor mu; sonradan düzeltme ve yeniden gönderim nasıl yönetiliyor?
10. Aktarım ne sıklıkta yapılabilir: gerçek zamanlı, saatlik, günlük veya dönem kapama sonrası mı?
11. Hatalı kayıtların geri bildirimi, tekrar gönderim, idempotency ve işlem logları nasıl sağlanıyor?
12. Kimlik doğrulama, IP kısıtı, TLS, VPN, rol bazlı yetki ve KVKK kapsamındaki veri güvenliği seçenekleri nelerdir?
13. Entegrasyon lisansı, geliştirme bedeli, bakım bedeli, API kullanım limiti ve versiyon değişikliği politikası nedir?
14. Canias’ın hangi sürüm/modülleriyle test edilmiş bir referansınız var? Referans müşteri veya demo akışı paylaşabilir misiniz?

### Canias ekibine sorulacaklar

1. Kurumumuzdaki Canias sürümünde WSR/API hangi modüllerle aktif: HRM, puantaj, izin, bordro ve finans?
2. Dış sistemden hangi işlem tipi tercih edilmeli: web servis, TROIA özel servisi, XML/CSV import veya ara servis?
3. Puantaj kaydının Canias’taki hedef tablosu/iş nesnesi ve zorunlu alanları nelerdir?
4. Bordro hesaplaması Canias’ta hangi alanları bekliyor: normal gün/saat, fazla mesai türleri, izin günleri, rapor, ücretsiz izin, devamsızlık, pazar kesintisi ve maliyet merkezi?
5. Meyer’den gelen verinin Canias’a yazılması için onay, dönem kilidi ve geri alma prosedürü nedir?
6. Canias tarafında test, kabul ve üretim ortamları ayrı mı? Kullanıcı/yetki ve loglama nasıl yapılacak?
7. Canias danışmanı tarafından gerekli TROIA geliştirmesi veya WSR tanımının kapsamı ve tahmini eforu nedir?

## 5. Önerilen veri sözleşmesi

Entegrasyon günlük ham hareketten ziyade, bordro döneminde onaylanmış ve versiyonlanmış günlük puantaj kayıtlarını taşımalıdır. Her kayıt en az şu anahtarları içermelidir:

| Alan | Açıklama |
|---|---|
| `company_code` | Firma/şirket kodu |
| `workplace_code` | İşyeri/alt firma kodu |
| `employee_id` | Meyer ve Canias arasında ortak personel anahtarı |
| `work_date` | ISO tarih, `YYYY-MM-DD` |
| `normal_hours` | Normal çalışma süresi |
| `overtime_hours` | Fazla mesai süresi |
| `overtime_type` | Fazla mesai türü/kodu |
| `leave_code` | İzin/rapor/ücretsiz izin kodu |
| `leave_hours` / `leave_days` | Süre veya gün |
| `absence_hours` | Devamsızlık süresi |
| `shift_code` | Vardiya kodu |
| `cost_center` | Canias maliyet merkezi |
| `source_record_id` | Meyer kaynak kaydı |
| `period` | Bordro dönemi |
| `approval_status` | Taslak/onaylı/iptal |
| `calculation_version` | Hesap kuralı sürümü |
| `updated_at` | Son değişiklik zamanı |

Sürelerin yalnızca `HH:MM` metni olarak değil, tercihen ondalık saat veya dakika olarak da taşınması önerilir. Yuvarlama ve gece vardiyası davranışı sözleşmede açıkça tanımlanmalıdır.

## 6. Fonksiyonel gereksinimler

### Öncelikli gereksinimler

- Personel ve firma eşleştirmesi otomatik yapılmalı; eşleşmeyen kayıtlar aktarılmadan raporlanmalı.
- Meyer’den belirli tarih/firma/personel kapsamı seçilerek veri alınabilmeli.
- Ham giriş-çıkış ile onaylanmış puantaj ayrımı korunmalı.
- İzin türleri Canias bordro kodlarıyla eşleştirilebilmeli.
- 45 saat kuralı, hafta sonu FM→NM aktarımı ve pazar kesintisi gibi mevcut iş kuralları ya Meyer’de tek kaynak olarak çalışmalı ya da hangi sistemde çalıştığı açıkça belirlenmeli.
- Aynı dönem ikinci kez gönderildiğinde mükerrer kayıt oluşmamalı.
- Başarılı, kısmi başarılı ve hatalı aktarım sonuçları kayıt altına alınmalı.
- Dönem kapatma öncesi mutabakat raporu üretilmeli: Meyer toplamları, entegrasyon toplamları ve Canias toplamları karşılaştırılmalı.
- Manuel düzeltme varsa kim tarafından, ne zaman ve hangi değerin değiştirildiği izlenebilmeli.

### Teknik olmayan ama kritik gereksinimler

- KVKK’ya uygun erişim ve saklama politikası.
- Yetkili kullanıcı ve rol bazlı erişim.
- Kesinti durumunda kuyruklama ve yeniden deneme.
- API/sürüm değişiklikleri için bildirim ve geriye dönük uyumluluk.
- Test verisiyle paralel bordro çalıştırma ve yazılı kabul kriterleri.

## 7. Mevcut uygulama korunacaksa yapılacaklar

Meyer doğrudan bağlantı sunamazsa mevcut uygulama atılmamalı; entegrasyon ara katmanı olarak konumlandırılmalıdır.

1. Excel/CSV yükleme yerine Meyer’den otomatik dosya/API alımı eklenir.
2. `normalize_meyer_rows` ve hesaplama kuralları ayrı bir iş kuralı modülüne taşınır.
3. Çıktı yalnızca kişi bazlı CSV yerine Canias’ın istediği kesin veri formatında üretilir.
4. Canias’a gönderim için WSR/API istemcisi veya güvenli dosya aktarımı eklenir.
5. Aktarım kayıtları, tekrar gönderim anahtarı ve hata kuyruğu eklenir.
6. İki-üç bordro dönemi paralel kontrol yapılarak mevcut Excel süreciyle sonuçlar karşılaştırılır.

Bu yaklaşımın riski, aynı puantaj kuralının Meyer, mevcut uygulama ve Canias’ta birden fazla kez uygulanmasıdır. Bu nedenle “hesaplamanın tek sahibi hangi sistem?” kararı toplantıda mutlaka yazılı hale getirilmelidir.

## 8. Toplantı sonunda beklenen kararlar

- Meyer’in hazır Canias bağlantısı mı, proje bazlı entegrasyonu mu kullanılacak?
- PDKS ham hareketinin mi, onaylı puantaj sonucunun mu aktarılacağı.
- Puantaj ve bordro hesaplama kurallarının tek sahibi.
- Entegrasyon yöntemi ve veri sözleşmesi.
- Personel/firma/izin/fazla mesai kod eşleştirmeleri.
- Test ortamı, pilot kapsamı ve kabul kriterleri.
- Lisans, geliştirme, bakım ve destek sorumlulukları.
- Üretime geçiş tarihi ve geri dönüş planı.

## 9. Toplantıda kullanılabilecek kısa pozisyon

“Biz bugün Meyer’den puantajı Excel olarak dışarı alıp, normal çalışma, fazla mesai, izin, rapor ve devamsızlık kurallarını kendi ara uygulamamızda kontrol ederek bordro sürecine hazırlıyoruz. Hedefimiz bu manuel dosya akışını kaldırıp, Meyer’de oluşan onaylı puantaj verisini doğrudan Canias’a güvenli, izlenebilir ve mükerrer kayıt üretmeyen bir entegrasyonla aktarmak. Meyer’in hazır Canias bağlantısı ve teknik API’si varsa önceliğimiz bunu kullanmak; yoksa mevcut hesaplama katmanımızı Canias entegrasyonuna bağlamak istiyoruz.”

## Kaynaklar

- [Meyer PDKS – entegrasyon ve API açıklamaları](https://www.meyer.com.tr/pdks.htm)
- [Meyer – yüz tanıma ve Canias dahil ERP entegrasyonu](https://www.meyer.com.tr/yuz-tanima.htm)
- [Canias WSR – resmi web servisleri sayfası](https://canias.com/tr/caniaserp-modules/wsr-2/)
- [Canias ERP – modüler yapı ve entegrasyon katmanı](https://canias.com/tr/kurumsal-kaynak-planlama-erp-nedir/)

## 10. Canias içinde Excel yüklemeli özel modül yapılabilir mi?

**Evet.** En uygun yaklaşım, Canias’ın standart kaynak kodunu değiştirmeden TROIA üzerinde müşteri özelinde bir “Puantaj Aktarım ve Kontrol” modülü geliştirmektir. Canias’ın resmi geliştirme sayfası, TROIA’nın Canias ile entegre bir IDE ve geliştirme platformu olduğunu; müşteri özel kodlarının standart koddan ayrı tutulabildiğini ve sürüm geçişlerinde korunabildiğini belirtiyor. [Canias TROIA geliştirme](https://canias.com/tr/caniaserp-modules/dev-2/)

Ancak “Excel dosyasını doğrudan okuyacak hazır kütüphane ve dosya yükleme fonksiyonları mevcut Canias sürümümüzde nasıl kullanılıyor?” sorusu Canias danışmanından teyit edilmelidir. Kamuya açık sayfalarda bu işlemin TROIA içindeki kesin fonksiyon isimleri ve Excel sürümü yayınlanmamıştır. Bu nedenle aşağıdaki plan, doğru mimariyi ve geliştirme sırasını tanımlar; gerçek kod sözdizimi, kurumunuzun Canias sürümü ve kurulu modülleri üzerinde netleştirilmelidir.

### Hedef kullanıcı akışı

1. Kullanıcı Canias’ta “Puantaj Aktarım” ekranını açar.
2. Firma, işyeri, bordro dönemi ve puantaj kaynağını seçer.
3. Meyer’den alınmış Excel dosyasını yükler.
4. Sistem dosyayı geçici alana kaydeder ve kolonları tanır.
5. Ön kontrol çalışır; hatalı satırlar ve eşleşmeyen personeller gösterilir.
6. Kullanıcı “Taslak oluştur” diyerek kayıtları Canias’a taslak olarak alır.
7. Sistem mevcut puantaj kurallarını uygular ve günlük/haftalık sonuçları üretir.
8. Kullanıcı özetleri kontrol eder; gerekirse yetkisi dahilinde düzeltme yapar.
9. Yetkili kullanıcı dönem için “Onayla ve bordroya aktar” işlemini çalıştırır.
10. Sistem Canias İK/bordro kayıtlarını oluşturur, işlem numarası üretir ve log kaydeder.

Önerilen durum akışı:

`Yüklendi → Ön kontrolde → Hatalı / Taslak → Hesaplandı → Kontrol bekliyor → Onaylandı → Bordroya aktarıldı → Kilitli`

## 11. Aşama aşama geliştirme planı

### Aşama 0 – Canias uygunluk ve lisans kontrolü

Geliştirmeye başlamadan önce Canias danışmanından aşağıdaki maddeler yazılı alınmalıdır:

- Canias sürümü ve web-client/desktop kullanım şekli.
- Kurumda TROIA/DEV geliştirme araçlarının açık olup olmadığı.
- Mevcut bakım sözleşmesinin özel geliştirme ve TROIA erişimini kapsayıp kapsamadığı.
- HRM, izin, puantaj ve bordro modüllerinin aktif olup olmadığı.
- Excel yükleme, dosya saklama ve dosya erişim fonksiyonlarının mevcut sürümdeki yöntemi.
- Canias bordrosunun puantajdan beklediği hedef kayıt nesnesi ve zorunlu alanları.
- Geliştirme, test ve üretim ortamlarının ayrıştırılması.

Bu aşamanın çıktısı, “Canias içinde geliştirilebilir” onayı ve hedef veri nesnelerinin teknik dokümanıdır.

### Aşama 1 – İş kurallarını kesinleştirme

Mevcut Python uygulamasındaki kurallar Canias’a kopyalanmadan önce iş birimleriyle imzalı bir kural kataloğuna dönüştürülmelidir.

Kural kataloğunda en az şunlar bulunmalıdır:

- Normal çalışma (`NM`) ve fazla mesai (`FM`) tanımı.
- `MS` alanının anlamı ve varsayılan çalışma süresi.
- Haftalık 45 saat hesabının hangi gün ve vardiya kayıtlarına uygulandığı.
- Hafta sonu FM’nin NM’ye aktarım şartı ve aktarılabilecek azami süre.
- Pazar kesintisinin tam gün devamsızlıkla ilişkisi.
- `IZS`, `YIZS`, `SGKIZS`, `UCZIZS`, `RM`, `EM` alanlarının bordro karşılığı.
- Yıllık izin, ücretli izin, sağlık raporu ve ücretsiz izin kodları.
- Gece vardiyası, 24 saati aşan süre, eksik/bozuk saat ve resmi tatil davranışı.
- Yuvarlama: dakika, ondalık saat, gün veya bordro puantaj birimi.
- Ay başı/sonu ile ISO hafta kesişimlerinde hesaplama yöntemi.

Buradaki hedef, aynı hesabın Meyer, Python uygulaması ve Canias’ta üç farklı sonuç üretmesini önlemektir. Tercihen Meyer ham hareketi üretir; tek bir sistem onaylı puantajı hesaplar; Canias ise bordro kaydının sahibi olur.

### Aşama 2 – Excel şablonunu standardize etme

İlk versiyonda “her Excel’i anlamaya çalışan” esnek yapı yerine tek bir resmi şablon kullanılmalıdır. Meyer export formatı değişirse sürüm numarasıyla yönetilmelidir.

Önerilen şablon:

- İlk satır: kolon başlıkları.
- Bir satır: bir personelin bir iş gününe ait kaydı.
- Tarih: tercihen `YYYY-MM-DD`; mevcut Meyer formatı için `DD.MM.YYYY` de desteklenebilir.
- Süre: `HH:MM` veya dakika/ondalık saat; tek format zorunlu tutulmalı.
- Personel anahtarı: metin olarak korunmalı; baştaki sıfırlar silinmemeli.
- Firma ve işyeri kodları zorunlu olmalı.
- Dosyanın üst bilgisinde veya ayrı bir parametre alanında dönem bilgisi bulunmalı.

Kolon eşleştirme ekranı da eklenebilir. Böylece Meyer’in kolon adı değiştiğinde kullanıcı kaynak kolonunu hedef alana eşleyebilir; fakat bordroya giden zorunlu alanlar eşleşmeden işlem devam etmemelidir.

### Aşama 3 – Modül ekranlarının tasarlanması

Modül aşağıdaki ekranlardan oluşmalıdır:

#### 3.1. Parametre ve yükleme ekranı

- Firma/şirket.
- İşyeri/alt firma.
- Bordro dönemi.
- Vardiya veya çalışma takvimi.
- Meyer dosyası yükleme alanı.
- Dosya şablonu sürümü.
- “Ön kontrol” butonu.

#### 3.2. Ön kontrol ekranı

Sayaçlar gösterilmelidir:

- Toplam satır.
- Geçerli satır.
- Eşleşen personel.
- Eşleşmeyen personel.
- Geçersiz tarih.
- Geçersiz süre.
- Eksik zorunlu alan.
- Aynı personel/tarih için mükerrer kayıt.
- Dönem dışında kalan tarih.

Hatalar satır numarası, sicil numarası, tarih, kolon ve açıklamayla listelenmelidir. Kullanıcı hatalı dosyayı düzeltip yeniden yükleyebilmelidir.

#### 3.3. Taslak puantaj ekranı

Taslak kayıtlar personel ve tarih bazında gösterilir. Ham alanlar ile hesaplanan alanlar ayrılmalıdır:

- Ham: giriş, çıkış, `MS`, `NM`, `FM`, izin kodları.
- Hesaplanan: gün durumu, izin türü, devamsızlık, güncel NM/FM, pazar durumu.
- Sistem bilgisi: kaynak dosya, satır numarası, yükleme numarası, hesaplama sürümü.

#### 3.4. Mutabakat ve onay ekranı

Personel ve dönem bazında şu toplamlar yan yana gösterilmelidir:

- Meyer dosyasındaki toplamlar.
- Canias hesaplama sonucu.
- Önceki yükleme ile fark.
- Bordroya aktarılacak nihai toplam.

Fark bulunuyorsa kullanıcı fark nedenini seçmeden onay verememelidir.

#### 3.5. Aktarım geçmişi ekranı

Her yükleme için dosya adı, kullanıcı, zaman, dönem, toplam kayıt, hata sayısı, onaylayan kişi, aktarım sonucu ve Canias işlem numarası tutulmalıdır.

### Aşama 4 – Canias veri modelini oluşturma

Standart Canias HRM/bordro tablolarına doğrudan kontrolsüz yazmak yerine, önce özel taslak tabloları veya Canias’ın önerdiği iş nesnelerini kullanmak daha güvenlidir. Hedef yapı iki katmanlı olmalıdır:

1. **Staging/taslak katmanı:** Excel’den gelen ham kayıtların değişmeden saklandığı alan.
2. **İşlem/entegrasyon katmanı:** doğrulanmış ve hesaplanmış puantajın Canias bordrosuna aktarılacağı kayıt.

Her satır için asgari teknik alanlar:

- Yükleme numarası.
- Kaynak dosya adı ve dosya satır numarası.
- Firma/işyeri kodu.
- Meyer sicil no.
- Canias personel ID’si.
- Dönem ve çalışma tarihi.
- Ham NM/FM/MS değerleri.
- Ham izin kodları.
- Hesaplanmış puantaj değerleri.
- Durum.
- Hata mesajı.
- Hesaplama sürümü.
- Oluşturan/değiştiren kullanıcı ve zaman damgası.
- Canias hedef kayıt ID’si.

Bu tasarım, aynı Excel’in tekrar yüklenmesinde mükerrer kayıtları tespit etmeyi ve hangi kaydın bordroya gittiğini izlemeyi sağlar.

### Aşama 5 – Excel’i alma ve dönüştürme

TROIA içinde uygulanacak işlem sırası şu olmalıdır:

1. Dosya yükleme kontrolü: uzantı, boyut, boş dosya ve dosya güvenliği.
2. Şablon kontrolü: başlıkların varlığı ve şablon sürümü.
3. Satır okuma: her Excel satırını bir geçici kayıt olarak alma.
4. Tip dönüşümü: sicil no, tarih, süre ve kod alanlarını normalize etme.
5. Zorunlu alan kontrolü.
6. Personel eşleştirme.
7. Firma/işyeri eşleştirme.
8. Dönem kontrolü.
9. Mükerrer kontrolü.
10. Hatalı kayıtları hata tablosuna, geçerli kayıtları taslak tablosuna yazma.

Excel motorunun teknik olarak sorun çıkardığı durumlar için iki alternatif hazırlanmalıdır:

- Meyer’den aynı şablonun CSV çıktısını alıp Canias’ta CSV/ayrıştırıcı ile işlemek.
- Excel’i kurum içindeki küçük bir dönüştürücü serviste CSV/JSON’a çevirip Canias’a WSR ile göndermek.

İkinci alternatifte Canias’a Excel kütüphanesi ekleme ihtiyacı azalır; ancak harici servis, güvenlik ve işletim sorumluluğu getirir.

### Aşama 6 – Mevcut Python mantığını TROIA’ya taşıma

Mantık satır satır kopyalanmamalı; işlevsel parçalara ayrılmalıdır:

1. `Süre dönüştürme`: `HH:MM`, boş, `# __ #`, Excel zaman değeri ve hatalı değer davranışı.
2. `Gün sınıflandırma`: çalışma, ücretli izin/rapor, ücretsiz izin, devamsızlık, hafta sonu.
3. `İzin türü çözümleme`: yıllık izin, ücretli izin, sağlık raporu, ücretsiz izin.
4. `Günlük beklenti hesabı`: `MS` veya vardiya takvimi.
5. `Haftalık 45 saat hesabı`.
6. `Hafta sonu FM → NM aktarımı`.
7. `Pazar kesintisi`.
8. `Mutabakat ve toplamlar`.

Her fonksiyon için örnek veri ve beklenen sonuçlar hazırlanıp Canias testleriyle karşılaştırılmalıdır. Mevcut Python uygulaması referans hesap makinesi olarak korunabilir.

### Aşama 7 – Bordro/İK hedeflerine aktarım

Hesaplanmış puantajı Canias’a aktarmanın üç seçeneği değerlendirilmelidir:

#### Seçenek A – Özel TROIA modülü doğrudan standart bordro nesnesini çağırır

En bütünleşik seçenektir. Kullanıcı taslak puantajı onaylar; özel modül Canias’ın İK/bordro işlemlerini çağırır. Standart Canias validasyonları ve yetki mekanizmaları kullanılabilir.

#### Seçenek B – WSR/API ile Canias servisine aktarım

Meyer veya ara servis, Canias WSR üzerinde tanımlanan servise onaylı puantaj gönderir. WSR’de kullanıcı yetkisi, servis sözleşmesi, başarılı/başarısız yanıt ve tekrar gönderim davranışı tanımlanmalıdır. Canias WSR’nin platform bağımsız veri alışverişini ve web servis tanımlarını desteklediği resmi olarak belirtilmektedir. [Canias WSR](https://canias.com/tr/caniaserp-modules/wsr-2/)

#### Seçenek C – Dosya tabanlı aktarım

Özel modül onaylanmış kayıtları Canias’ın kabul ettiği CSV/XML formatına üretir; standart import veya danışman tarafından hazırlanan import programı çalıştırılır. En hızlı MVP seçeneği olabilir, ancak otomasyon ve hata geri bildirimi API’ye göre daha sınırlıdır.

İlk pilot için A veya C, Canias’ın mevcut bordro arayüzüne göre tercih edilebilir; uzun vadede WSR/API tabanlı aktarım daha sürdürülebilir olur.

### Aşama 8 – Yetki, onay ve dönem kilidi

Roller en az şu şekilde ayrılmalıdır:

- **Yükleyici:** Dosya yükler ve ön kontrol görür.
- **İK kontrolörü:** Hataları düzeltir, taslağı hesaplatır.
- **Onaycı:** Mutabakat sonrası dönemi onaylar.
- **Bordro kullanıcısı:** Canias bordrosuna aktarır.
- **Yönetici:** Logları ve raporları görüntüler.

Onay sonrası kayıtlar değiştirilememeli; düzeltme gerekiyorsa yeni revizyon veya kontrollü geri alma süreci çalışmalıdır. Silme yerine iptal/revizyon yaklaşımı kullanılmalıdır.

### Aşama 9 – Test planı

Testler yalnızca “dosya yüklendi” seviyesinde bırakılmamalıdır.

#### Birim testleri

- Saat dönüşümü.
- Boş veya hatalı değerler.
- İzin kodu sınıflandırması.
- Tam gün ve kısmi devamsızlık.
- 45 saat altı/üstü haftalar.
- Hafta sonu FM aktarımı.
- Pazar kesintisi.
- ISO hafta ve ay sınırı.

#### Entegrasyon testleri

- Personel eşleştirme.
- Firma/işyeri eşleştirme.
- Canias hedef kaydı oluşturma.
- Mükerrer gönderimi engelleme.
- Hatalı satırların geri bildirimi.
- Bağlantı kesilmesi ve yeniden deneme.

#### Kullanıcı kabul testleri

- Haziran gibi gerçek bir bordro dönemi mevcut Excel süreciyle paralel çalıştırılır.
- Her personelin toplam NM/FM/izin/devamsızlık değerleri karşılaştırılır.
- En az iki dönem paralel sonuç alınmadan eski süreç kapatılmaz.

### Aşama 10 – Canlıya geçiş

1. Test ortamında modül kurulumu.
2. Gerçek verinin maskelenmiş kopyasıyla test.
3. Pilot firma/işyeri ve sınırlı personel grubu.
4. Bir bordro döneminde paralel çalışma.
5. Kullanıcı kabul tutanağı.
6. Canlı kurulum ve rol tanımları.
7. İlk canlı dönemde manuel geri dönüş planı.
8. İki dönem izleme ve hata düzeltme.
9. Eski Excel sürecinin yalnızca yedek/karşılaştırma amacıyla tutulması.

## 12. Önerilen teknik mimari

```text
Meyer Excel / API
        ↓
Canias Puantaj Aktarım Modülü (TROIA)
        ↓
Dosya doğrulama + personel/izin kod eşleştirme
        ↓
Taslak/staging kayıtları
        ↓
Puantaj iş kuralları ve haftalık hesaplama
        ↓
Mutabakat + İK onayı + dönem kilidi
        ↓
Canias HRM / Puantaj / Bordro hedef kayıtları
        ↓
Log, hata kuyruğu, rapor ve denetim izi
```

Bu mimarinin avantajı, Excel’in doğrudan bordro tablolarına yazılmamasıdır. Önce kontrol edilebilir taslak kayıt oluşur; bordroya yalnızca onaylanmış ve izlenebilir veri gider.

## 13. MVP ve sonraki sürümler

### MVP – ilk canlı pilot

- Manuel Excel yükleme.
- Tek Meyer şablonu.
- Personel eşleştirme.
- Zorunlu alan ve mükerrer kontrolleri.
- Mevcut NM/FM/izin/devamsızlık kuralları.
- Günlük ve haftalık kontrol ekranı.
- Taslak ve onay akışı.
- Canias’a dosya veya standart hedef nesne üzerinden aktarım.
- Log ve hata raporu.

### Sürüm 2

- Otomatik Meyer API/WSR entegrasyonu.
- Çoklu firma ve farklı şablon sürümleri.
- Otomatik zamanlanmış aktarım.
- Canias bordro sonucundan Meyer’e veya raporlama katmanına geri bildirim.
- Gelişmiş izin/vardiya/resmi tatil kuralları.

### Sürüm 3

- Gerçek zamanlı veya gün içi aktarım.
- Yönetim dashboard’ları.
- Kural sürümleme ve simülasyon.
- Bordro öncesi fark analizi.
- Meyer ve Canias arasında çift yönlü personel/izin senkronizasyonu.

## 14. Toplantıda Canias’a söylenecek teknik talep

“Canias içinde TROIA ile, Meyer Excel dosyasını yükleyebileceğimiz müşteri özelinde bir Puantaj Aktarım ve Kontrol modülü geliştirmek istiyoruz. Modül önce dosyayı staging/taslak alana kaydetmeli, personel ve kod eşleştirmelerini doğrulamalı, mevcut 45 saat ve izin kurallarını uygulamalı, kullanıcı onayı sonrasında Canias HRM/bordro hedef kayıtlarına aktarmalıdır. Her yükleme versiyonlu, mükerrer gönderime dayanıklı, yetkilendirilmiş ve denetlenebilir olmalıdır. Öncelikle mevcut Canias sürümümüzde Excel dosya okuma ve bordro hedef nesnesi imkanlarını, ardından TROIA/WSR geliştirme kapsamını ve tahmini eforu netleştirmek istiyoruz.”

## 15. Sonuç

Bu proje Canias içinde özel modül olarak yapılabilir ve mevcut Excel tabanlı sürecin kontrollü bir şekilde ERP’ye taşınması mümkündür. En önemli teknik karar Excel’in okunması değil, hesaplanan verinin Canias’ta hangi standart iş nesnesine ve hangi onay akışıyla aktarılacağıdır. Ayrıca hesaplama kurallarının tek sahibi belirlenmeden geliştirmeye başlanmamalıdır.
