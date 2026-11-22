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

## Kategoriler
Aday havuzu çalışma anında Vikipedi'den çıkarılır ve 7 gün saklanır. Varsayılan adlar `yerlerrss.py` içindeki `GROUPS`
listesindedir. Bir kategori adı Vikipedi'de farklıysa kontrol raporu "yok/boş" der ve benzer kategori önerir; doğru adı
workflow'daki `env:` bölümüne yazın, örneğin `CATS_ILCE: "Kategori adı 1|Kategori adı 2"` (kategori adını `Kategori:` öneki olmadan yazın).

## "Ana madde" ile bağlı ayrıntılı maddeler
Vikipedi'de bir bölümün başında "Ana madde: Hatay mutfağı" gibi bir dipnot varsa, o maddenin tam metni (ve görselleri) o bölümün
sonuna alt başlık olarak eklenir. Böylece il/ilçe makalesi tarih, mutfak, kültür, gezilecek yerler gibi konuların ayrıntılı
maddelerini de içerir. Her makalede en çok 6 ayrıntılı madde eklenir, iç içe takip yapılmaz; eklenen maddelerin bağlantıları
makalenin lisans notunda listelenir. Kapatmak için `FOLLOW_MAIN: "0"`.

## Çıktı
* `content:encoded`: temizlenmiş tam makale (başlıklar, paragraflar, listeler, tablolar, figürler). Referans numaraları,
  düzenle bağlantıları, şablon kutuları, Kaynakça/Dış bağlantılar bölümleri çıkarılır.
* Görseller: yalnızca lisansı bilinen dosyalar alınır (telifli/fair-use olanlar alınmaz). Her görselin altında yazar,
  lisans ve Commons bağlantısı vardır.
* Her makalenin sonunda Vikipedi kaynağı ve **CC BY-SA 4.0** lisans notu bulunur. Makaleleri blogunuzda yayınlarken bu notu
  ve görsel altyazılarını silmeyin; lisans gereğidir.

## Ayarlar (workflow `env:`)
`PER_RUN` (10), `FEED_ITEMS` (100), `FEED_MAX_MB` (25), `MAX_IMAGES` (80), `MIN_TEXT_CHARS` (1500), `MIN_IMG_W` (400),
`POOL_TTL_DAYS` (7), `CONTENT_KEEP_DAYS` (30), `FOLLOW_MAIN` (1), `MAX_SUB` (6), `SUB_MAX_CHARS` (80000),
`TOTAL_MAX_CHARS` (500000), `CATS_<GRUP>`.

## Bilinmesi gerekenler
* Metinler Vikipedi'de ne yazıyorsa odur. Belediye başkanı ve partisi gibi bilgiler maddede varsa gelir; güncel olmayabilir
  (kullanılan sürüm bağlantısı her makalenin sonundadır).
* Çok kısa (taslak) ilçe maddeleri atlanır (`MIN_TEXT_CHARS`).
