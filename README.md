# Yerler RSS (Vikipedi)

Dünyanın harikaları, Türkiye'de ve dünyada görülecek yerler ile Türkiye'nin illeri ve ilçeleri için
**Vikipedi maddesinin tamamını** (giriş, künye/bilgi kutusu, tüm bölümler, tablolar, galeri) ve maddede geçen
görselleri **yüksek çözünürlükte** (en çok 1280 px) taşıyan bir `rss.xml` üretir. Günde iki kez çalışır, depoya veri yazmaz,
yalnızca `rss.xml`'i GitHub Pages'e yayınlar. Aynı madde bir daha üretilmez.

## Kurulum
1. Bu klasörün içeriğini yeni (public) bir depoya yükleyin (`.github` klasörü dahil).
2. **Settings → Pages → Source: GitHub Actions**.
3. **Actions → "Yerler RSS (Vikipedi)" → Run workflow** → önce **kontrol** kutusunu işaretleyip çalıştırın:
   hangi kategorilerin bulunduğunu ve kaç madde içerdiğini günlükte gösterir (makale üretmez).
4. Rapor iyiyse kutuyu işaretlemeden tekrar çalıştırın. RSS adresi:
   `https://KULLANICI.github.io/DEPO/rss.xml` (depo adı `KULLANICI.github.io` ise `https://KULLANICI.github.io/rss.xml`).

## Aday listeleri
* **İller ve ilçeler:** Kategoriden değil, **Wikidata**'dan alınır ("province of Turkey" = 81 il, "district of Turkey" = ilçeler;
  Vikipedi madde adlarıyla birlikte gelir). Böylece "ISO 3166-2:TR" gibi yardımcı sayfalar listeye giremez. Her il/ilçe maddesi
  ayrıca doğrulanır (koordinat ya da nüfus/yüzölçümü/plaka gibi künye satırı yoksa atlanır). Wikidata'ya ulaşılamazsa iller için
  81 il adı listesi, ilçeler için kategori yedeği kullanılır.
* **Dünyanın harikaları, Türkiye'de/dünyada görülecek yerler:** Vikipedi kategorilerinden ve kürate edilmiş başlık listesinden.
  Başlığında `:` geçen sayfalar (yardımcı/kod sayfaları) hiçbir grupta aday olmaz.
* Aday havuzu çalışma anında çıkarılır ve 7 gün saklanır. `kontrol` seçeneği her grubun kaynağını ve sayısını raporlar.
  Bir kategori adı Vikipedi'de farklıysa rapor "yok/boş" der ve benzer kategori önerir; doğru adı workflow'daki `env:` bölümüne
  yazın, örneğin `CATS_TURKIYE: "Kategori adı 1|Kategori adı 2"` (`Kategori:` öneki olmadan).

## "Ana madde" ile bağlı ayrıntılı maddeler
Vikipedi'de bir bölümün başında "Ana madde: Hatay mutfağı" gibi bir dipnot varsa, o maddenin tam metni (ve görselleri) o bölümün
sonuna alt başlık olarak eklenir. Böylece il/ilçe makalesi tarih, mutfak, kültür, gezilecek yerler gibi konuların ayrıntılı
maddelerini de içerir. Her makalede en çok 6 ayrıntılı madde eklenir, iç içe takip yapılmaz; eklenen maddelerin bağlantıları
makalenin lisans notunda listelenir. Kapatmak için `FOLLOW_MAIN: "0"`.

## SEO
* **Konu başlığı** kısa ve temizdir: "İli / İlçesi" eki yoktur, en çok 5 konu içerir ve yaklaşık 68 karakteri geçmez.
  Konular şablon değil, makalenin gerçekten içerdiği bölümlerden üretilir; örneğin
  `Hatay: Tarih, Coğrafya, Nüfus, Kültür ve Mutfak`, `Adapazarı (Sakarya): Tarih, Coğrafya, Nüfus, Kültür ve Mutfak`.
  Başlık uzarsa önce Yönetim, Ekonomi, Coğrafya atılır; "Gezilecek Yerler" en son atılır. Ayraç `TITLE_SEP` ile değiştirilir.
  Maddede olmayan konu başlığa yazılmaz.
* **Açıklama** (`description`): giriş paragrafından, parantez içi okunuş/yazılış çıkarılarak, mümkünse cümle sonunda biten
  en çok 155 karakterlik meta açıklamadır.
* **Etiketler**: `Türkiye'nin İlleri`, il/ilçe adı, `Türkiye` gibi konuya özgü etiketler (Blogger etiketi olur).
* **Bağlantılar:** Makale metnindeki Vikipedi ve dış bağlantılar kaldırılır (metin kalır). Yalnızca görsel yazar/lisans satırı ve makale sonundaki kaynak/lisans notu bağlantı içerir. Eski davranış için `KEEP_LINKS: "1"`.
* **Premium düzen (Blogger uyumlu, yalnızca satır içi stil):** kapak görseli 1920 px; Nüfus, Yüzölçümü, Rakım, Plaka/Alan/Posta
  kodu, Belediye Başkanı, Kaymakam/Vali kutuları (yalnızca künyede varsa); sabit düzenli künye tablosu; İçindekiler;
  künyedeki gerçek değerlerden **Sık Sorulan Sorular** (il/ilçe). Uzun kelime/adres, geniş tablo ve görseller taşmaz:
  5+ sütunlu tablolar sıkışmak yerine kendi içinde yatay kaydırılır.
* Görsellerin `alt` metni ad + açıklamadan oluşur; her görselin altında yazar ve lisans vardır. Sayfada tek H1 yoktur
  (Blogger başlığı H1 yapar); bölümler H2–H4 olarak sıralanır.

## Çıktı
* `content:encoded`: temizlenmiş tam makale (başlıklar, paragraflar, listeler, tablolar, figürler). Referans numaraları,
  düzenle bağlantıları, şablon kutuları, Kaynakça/Dış bağlantılar bölümleri çıkarılır.
* Görseller: yalnızca lisansı bilinen dosyalar alınır (telifli/fair-use olanlar alınmaz). Her görselin altında yazar,
  lisans ve Commons bağlantısı vardır.
* Her makalenin sonunda Vikipedi kaynağı ve **CC BY-SA 4.0** lisans notu bulunur. Makaleleri blogunuzda yayınlarken bu notu
  ve görsel altyazılarını silmeyin; lisans gereğidir.

## Ayarlar (workflow `env:`)
`PER_RUN` (10), `FEED_ITEMS` (100), `FEED_MAX_MB` (25), `MAX_IMAGES` (80), `MIN_TEXT_CHARS` (1500), `MIN_IMG_W` (400),
`LEAD_WIDTH` (1920), `POOL_TTL_DAYS` (7), `CONTENT_KEEP_DAYS` (30), `FOLLOW_MAIN` (1), `MAX_SUB` (6), `SUB_MAX_CHARS` (80000),
`TOTAL_MAX_CHARS` (500000), `CATS_<GRUP>`.

## Bilinmesi gerekenler
* Metinler Vikipedi'de ne yazıyorsa odur. Belediye başkanı ve partisi gibi bilgiler maddede varsa gelir; güncel olmayabilir
  (kullanılan sürüm bağlantısı her makalenin sonundadır).
* Çok kısa (taslak) ilçe maddeleri atlanır (`MIN_TEXT_CHARS`).

## Sürüm notu (BUILD_VERSION 3)
Yeni başlık biçimi ve düzen yalnızca **yeni üretilen** makalelere uygulanır. Eski sürümle üretilmiş il/ilçe makaleleri ilk
çalışmada kayıttan çıkarılır ve yeni biçimde, aynı kimlikle yeniden üretilir (her çalışmada `PER_RUN` kadar). Blogger'a
önceden aktarılmış yazılar RSS'ten otomatik güncellenmez; gerekirse bu yazıları Blogger'da silip yeniden içe aktarın.

## Tema uyumu ve HTML doğrulama
* **Tema uyumu (style.css'e göre):** Hiçbir renk sabit değil; hepsi temanın CSS değişkenlerinden okunur
  (`var(--navy, …)`, `--line`, `--soft`, `--soft-2`, `--page`, `--text`, `--muted`, `--radius`). Mavi ve altın (`data-skin=orange`) tema
  otomatik uyar; yedek değerler yalnızca tema dışı okuyucular içindir. Başlık rengi/boyutu/boşluğu, blockquote, liste girintisi, hücre
  yazı boyutu ve tablo kenarlığı temadan gelir, makale bunları ezmez. Görseller bağlantıya sarılmaz; temanın kendi görsel büyütücüsü çalışır.
  Künyedeki dış site adresleri ve harita bağlantısı makaleye alınmaz.
* **HTML denetimi:** `tests/htmlcheck.py` üretilen makaleleri HTML5 içerik modeline göre denetler (etiket eşleşmesi, tablo/liste/figür yapısı,
  benzersiz id, çalışan `#` bağlantıları, görsel nitelikleri, başlık sırası). Bu resmi W3C doğrulayıcısının yerine geçmez;
  yayın öncesi bir örneği https://validator.w3.org/nu/ adresinde de denemeniz önerilir.
