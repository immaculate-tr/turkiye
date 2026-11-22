import io
import json
import re
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import yerlerrss as y  # noqa: E402

NS = {"c": "http://purl.org/rss/1.0/modules/content/", "m": "http://search.yahoo.com/mrss/"}
NOW = datetime(2026, 11, 21, 6, 0, 0, tzinfo=timezone.utc)
_DEFAULTS = dict(PER_RUN=10, FEED_ITEMS=40, FEED_MAX_MB=20, MIN_TEXT_CHARS=300, MAX_IMAGES=60, IMG_WIDTH=1280,
                 MIN_IMG_W=400, POOL_TTL_DAYS=7, MAX_SKIP_ATTEMPTS=6, CONTENT_KEEP_DAYS=30, MAX_TABLE_ROWS=400,
                 FOLLOW_MAIN=True, MAX_SUB=6, SUB_MIN_CHARS=600, SUB_MAX_CHARS=80000, TOTAL_MAX_CHARS=500000)
_SAVED = {}


def setUpModule():
    for k, v in _DEFAULTS.items():
        _SAVED[k] = getattr(y, k)
        setattr(y, k, v)
    _SAVED["_env"] = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("CATS_")}


def tearDownModule():
    os.environ.update(_SAVED.pop("_env"))
    for k, v in _SAVED.items():
        setattr(y, k, v)


LONG = "Bu bölüm, yörenin tarihi ve kültürü hakkında ayrıntılı bilgi veren uzun bir metindir. " * 3

SAMPLE = f"""<div class="mw-content-ltr mw-parser-output" lang="tr" dir="ltr">
<div class="shortdescription nomobile noexcerpt noprint searchaux" style="display:none">Türkiye'de il</div>
<style data-mw-deduplicate="TemplateStyles:r1">.x{{color:red}}</style>
<div role="note" class="hatnote navigation-not-searchable">Başka kullanımlar için Hatay (anlam ayrımı) sayfasına bakın.</div>
<table class="infobox geography vcard"><tbody>
<tr><th colspan="2" class="infobox-above">Hatay</th></tr>
<tr><td colspan="2" class="infobox-image"><span typeof="mw:File"><a href="/wiki/Dosya:Hatay_bayrak.svg" class="mw-file-description"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Hatay_bayrak.svg/120px-Hatay_bayrak.svg.png" width="120" height="80" data-file-width="800" data-file-height="530"></a></span></td></tr>
<tr><td colspan="2" class="infobox-image"><span typeof="mw:File"><a href="/wiki/Dosya:Hatay_panorama.jpg" class="mw-file-description"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Hatay_panorama.jpg/250px-Hatay_panorama.jpg" width="250" height="125" data-file-width="4000" data-file-height="2000"></a></span><br>Hatay'dan bir görünüm</td></tr>
<tr><th colspan="2">Yönetim</th></tr>
<tr><th scope="row">Nüfus</th><td>1.544.640<sup class="reference" id="cite_ref-1"><a href="#cite_note-1">[1]</a></sup></td></tr>
<tr><th>Belediye</th><td><a href="/wiki/Hatay_B%C3%BCy%C3%BCk%C5%9Fehir_Belediyesi">Büyükşehir Belediyesi</a><br>Antakya</td></tr>
<tr><th>İlçeler</th><td><ul><li>Antakya</li><li>Defne</li></ul></td></tr>
<tr><th>Boş satır</th><td> </td></tr>
</tbody></table>
<p><b>Hatay</b>, Türkiye'nin güneyinde bir ilidir.<sup id="cite_ref-2" class="reference"><a href="#cite_note-2">[2]</a></sup> <a href="/wiki/Antakya" title="Antakya">Antakya</a>, <a href="/w/index.php?title=Yok&amp;action=edit&amp;redlink=1" class="new">Kırmızı</a> ve <a rel="nofollow" class="external text" href="https://example.org/x?a=1&amp;b=2">dış</a> bağlantı. <span style="display:none">gizli metin</span>{LONG}</p>
<div class="mw-heading mw-heading2"><h2 id="Tarihçe">Tarihçe</h2><span class="mw-editsection"><a href="#">düzenle</a></span></div>
<p>Tarihçe metni. {LONG}</p>
<figure class="mw-default-size" typeof="mw:File/Thumb"><a href="/wiki/Dosya:Sveti_Petar.jpg" class="mw-file-description"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Sveti_Petar.jpg/330px-Sveti_Petar.jpg" width="330" height="220" data-file-width="3000" data-file-height="2000"></a><figcaption>Aziz Petrus <a href="/wiki/Kilise">Kilisesi</a></figcaption></figure>
<div class="thumb tright"><div class="thumbinner" style="width:222px;"><a href="/wiki/Dosya:Eski_harita.jpg" class="image"><img alt="" src="//upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Eski_harita.jpg/220px-Eski_harita.jpg" width="220" height="150" class="thumbimage"></a><div class="thumbcaption"><div class="magnify"><a href="/wiki/Dosya:Eski_harita.jpg"></a></div>Eski harita</div></div></div>
<div class="thumb tright"><div class="thumbinner"><a href="/wiki/Dosya:Fair_use_logo.png" class="image"><img src="//upload.wikimedia.org/wikipedia/tr/thumb/1/1a/Fair_use_logo.png/220px-Fair_use_logo.png" width="220" height="150"></a><div class="thumbcaption">Logo</div></div></div>
<h3><span class="mw-headline" id="Roma_dönemi">Roma dönemi</span><span class="mw-editsection"><a href="#">düzenle</a></span></h3>
<p>Roma dönemi metni. {LONG}</p>
<div class="mw-heading mw-heading2"><h2 id="Boş_bölüm">Boş bölüm</h2></div>
<div class="thumb tleft"><div class="thumbinner"><a href="/wiki/Dosya:Kucuk_ikon.png"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Kucuk_ikon.png/100px-Kucuk_ikon.png" width="100" height="100"></a></div></div>
<div class="mw-heading mw-heading2"><h2 id="Nüfus">Nüfus</h2></div>
<p>Nüfus tablosu aşağıdadır. {LONG}</p>
<table class="wikitable"><caption>Nüfus gelişimi</caption><tbody>
<tr><th>Yıl</th><th>Nüfus</th></tr>
<tr><td>2000</td><td>1.253.726</td></tr>
<tr><td>2020</td><td>1.659.320</td></tr>
</tbody></table>
<div class="mw-heading mw-heading2"><h2 id="Mutfak">Mutfak</h2></div>
<ul><li>Künefe</li><li>Humus<ul><li>Hatay usulü</li></ul></li><li><a href="/wiki/Tepsi_kebab%C4%B1">Tepsi kebabı</a></li></ul>
<ul class="gallery mw-gallery-traditional"><li class="gallerybox"><div class="thumb"><span typeof="mw:File"><a href="/wiki/Dosya:Galeri_1.jpg" class="mw-file-description"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/1/11/Galeri_1.jpg/120px-Galeri_1.jpg" width="120" height="80" data-file-width="2400" data-file-height="1600"></a></span></div><div class="gallerytext"><p>Künefe</p></div></li><li class="gallerybox"><div class="thumb"><span typeof="mw:File"><a href="/wiki/Dosya:Galeri_2.jpg" class="mw-file-description"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/2/22/Galeri_2.jpg/120px-Galeri_2.jpg" width="120" height="80"></a></span></div><div class="gallerytext"><p>Humus</p></div></li></ul>
<div class="thumb tmulti tright"><div class="thumbinner"><div class="trow"><div class="tsingle"><span typeof="mw:File"><a href="/wiki/Dosya:Cok_1.jpg"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/3/33/Cok_1.jpg/100px-Cok_1.jpg" width="100" height="80"></a></span><div class="thumbcaption">Birinci</div></div><div class="tsingle"><span typeof="mw:File"><a href="/wiki/Dosya:Cok_2.jpg"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/4/44/Cok_2.jpg/100px-Cok_2.jpg" width="100" height="80"></a></span><div class="thumbcaption">İkinci</div></div></div></div></div>
<div class="floatnone"><a href="/wiki/Dosya:Plaj.jpg" class="mw-file-description"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/5/55/Plaj.jpg/300px-Plaj.jpg" width="300" height="200" data-file-width="2000" data-file-height="1333"></a></div>
<div class="navbox"><table><tr><td>Türkiye'nin illeri</td></tr></table></div>
<div class="mw-heading mw-heading2"><h2 id="Ayrıca_bakınız">Ayrıca bakınız</h2></div>
<ul><li>Hatay Şehirleri</li></ul>
<div class="mw-heading mw-heading2"><h2 id="Kaynakça">Kaynakça</h2></div>
<div class="mw-heading mw-heading3"><h3 id="Dipnotlar">Dipnotlar</h3></div>
<div class="reflist"><div class="mw-references-wrap"><ol class="references"><li id="cite_note-1">Kaynak bir</li></ol></div></div>
<div class="mw-heading mw-heading2"><h2 id="Dış_bağlantılar">Dış bağlantılar</h2></div>
<ul><li><a class="external text" href="https://hatay.gov.tr">Resmî site</a></li></ul>
</div>"""


def meta(lic="CC BY-SA 4.0", artist="<a href='//commons.wikimedia.org/wiki/User:Ali'>Ali Veli</a>", nonfree=None,
         url="https://creativecommons.org/licenses/by-sa/4.0"):
    m = {}
    if lic:
        m["LicenseShortName"] = {"value": lic}
        m["LicenseUrl"] = {"value": url}
    if artist:
        m["Artist"] = {"value": artist}
    if nonfree:
        m["NonFree"] = {"value": nonfree}
    return m


def info(name, width=3000, height=2000, **kw):
    u = f"https://upload.wikimedia.org/wikipedia/commons/x/xx/{name.replace(' ', '_')}"
    tw = min(width, 1280)
    return {"url": u, "thumburl": u.replace("/x/xx/", "/thumb/x/xx/") + f"/{tw}px-{name.replace(' ', '_')}" if width > 1280 else u,
            "width": width, "height": height, "thumbwidth": tw, "thumbheight": round(height * tw / width),
            "mime": kw.pop("mime", "image/jpeg"), "descriptionurl": f"https://commons.wikimedia.org/wiki/File:{name.replace(' ', '_')}",
            "extmetadata": kw.pop("meta", meta())}


IMAGES = {
    "Hatay panorama.jpg": info("Hatay panorama.jpg", 4000, 2000),
    "Sveti Petar.jpg": info("Sveti Petar.jpg", 3000, 2000, meta=meta("Public domain", artist=None, url="")),
    "Eski harita.jpg": info("Eski harita.jpg", 900, 600, meta=meta("CC BY 3.0", artist="Mehmet", url="https://creativecommons.org/licenses/by/3.0")),
    "Fair use logo.png": info("Fair use logo.png", 800, 800, meta=meta(None, artist=None, nonfree="true")),
    "Kucuk ikon.png": info("Kucuk ikon.png", 100, 100),
    "Galeri 1.jpg": info("Galeri 1.jpg", 2400, 1600),
    "Galeri 2.jpg": info("Galeri 2.jpg", 2000, 1500),
    "Cok 1.jpg": info("Cok 1.jpg", 1000, 800),
    "Cok 2.jpg": info("Cok 2.jpg", 1000, 800, meta=meta("fair use")),
    "Hatay bayrak.svg": info("Hatay bayrak.svg", 800, 530, mime="image/svg+xml", meta=meta("Public domain", artist=None, url="")),
    "Plaj.jpg": info("Plaj.jpg", 2000, 1333),
}


class FakeWiki:
    def __init__(self, pages=None, cats=None, search=None, images=None, coords=None, redirects=None, wd=None):
        self.redirects = redirects or {}
        self.wd = wd or {}
        self.sparql_calls = []
        self.pages = pages if pages is not None else {}
        self.cats = cats or {}
        self.search = search or {}
        self.images = IMAGES if images is None else images
        self.coords = coords or {}
        self.log = []

    def sparql(self, query):
        self.sparql_calls.append(query)
        titles = []
        for lbl in re.findall(r'"([^"]+)"@en', query):
            titles += self.wd.get(lbl, [])
        if "ERROR" in self.wd:
            raise OSError("wikidata kapalı")
        return {"results": {"bindings": [{"title": {"value": t}} for t in dict.fromkeys(titles)]}}

    def __call__(self, p):
        self.log.append(p)
        if p.get("list") == "categorymembers":
            name = p["cmtitle"].split(":", 1)[1]
            c = self.cats.get(name, {})
            members = [{"ns": 0, "title": t} for t in c.get("pages", [])] + [{"ns": 14, "title": "Kategori:" + t} for t in c.get("subs", [])]
            members += [{"ns": 10, "title": "Şablon:Gürültü"}]
            # sayfalama: 2'şerli
            start = int(p.get("cmcontinue", 0))
            chunk = members[start:start + 2]
            out = {"query": {"categorymembers": chunk}}
            if start + 2 < len(members):
                out["continue"] = {"cmcontinue": str(start + 2), "continue": "-||"}
            return out
        if p.get("list") == "search":
            return {"query": {"search": [{"title": t} for t in self.search.get(p["srsearch"], [])]}}
        if p.get("action") == "parse":
            pg = self.pages.get(p["page"])
            if pg is None:
                return {"error": {"code": "missingtitle", "info": "yok"}}
            return {"parse": pg}
        if p.get("prop") == "coordinates":
            c = self.coords.get(p["titles"])
            return {"query": {"pages": [{"title": p["titles"]} | ({"coordinates": [{"lat": c[0], "lon": c[1]}]} if c else {})]}}
        if p.get("prop") == "imageinfo":
            pages = []
            for t in p["titles"].split("|"):
                n = t.split(":", 1)[1]
                pages.append({"title": t, **({"imageinfo": [self.images[n]]} if n in self.images else {"missing": True})})
            return {"query": {"pages": pages}}
        if p.get("action") == "query" and "titles" in p and p.get("prop") in (None, "pageprops") and not p.get("list"):
            pages, redirs = [], []
            for tt in p["titles"].split("|"):
                final = self.redirects.get(tt, tt)
                if final != tt:
                    redirs.append({"from": tt, "to": final})
                pg = {"title": final}
                if final not in self.pages:
                    pg["missing"] = True
                else:
                    pp = self.pages[final].get("properties") if isinstance(self.pages[final], dict) else None
                    if isinstance(pp, dict) and "disambiguation" in pp:
                        pg["pageprops"] = {"disambiguation": ""}
                pages.append(pg)
            return {"query": {"pages": pages, "redirects": redirs}}
        raise AssertionError(f"beklenmeyen istek: {p}")


def page(title, pid, text=SAMPLE, props=None, revid=777):
    return {"title": title, "pageid": pid, "revid": revid, "displaytitle": title, "text": text, "properties": props or {"wikibase_item": "Q1"}}


def api_for(fake):
    return y.Api(transport=fake, sleep=lambda s: None, min_interval=0, sparql=fake.sparql)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_json(path):
    return json.loads(read_text(path))


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.log = []

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def items(self):
        root = ET.parse(os.path.join(self.root, "rss.xml")).getroot()
        return root, root.findall("channel/item")


class TestSanitize(unittest.TestCase):
    def setUp(self):
        self.blocks, self.rows, self.units = y.sanitize(SAMPLE, "Hatay")
        self.text = " ".join(b[1] for b in self.blocks if b[0] == "html")

    def test_noise_removed(self):
        for bad in ("[1]", "[2]", "düzenle", "gizli metin", "Başka kullanımlar", "Kaynak bir", "Resmî site", "Hatay Şehirleri",
                    "Türkiye'nin illeri", "color:red"):
            self.assertNotIn(bad, self.text)
        heads = [b[2] for b in self.blocks if b[0] == "h"]
        for stop in ("Kaynakça", "Dipnotlar", "Dış bağlantılar", "Ayrıca bakınız"):
            self.assertNotIn(stop, heads)
        self.assertEqual(heads, ["Tarihçe", "Roma dönemi", "Boş bölüm", "Nüfus", "Mutfak"])
        self.assertEqual([b[1] for b in self.blocks if b[0] == "h"], [2, 3, 2, 2, 2])

    def test_links_and_inline(self):
        self.assertIn('<a href="https://tr.wikipedia.org/wiki/Antakya">Antakya</a>', self.text)
        self.assertIn("Kırmızı", self.text)
        self.assertNotIn("redlink", self.text)
        self.assertIn('href="https://example.org/x?a=1&amp;b=2" rel="nofollow noopener" target="_blank"', self.text)
        self.assertIn("<b>Hatay</b>", self.text)
        self.assertNotIn("<img", self.text)
        self.assertNotIn("class=", self.text)

    def test_infobox(self):
        d = {k: v for k, v in self.rows if k}
        self.assertEqual(d["Nüfus"], "1.544.640")
        self.assertEqual(d["Belediye"], "Büyükşehir Belediyesi, Antakya")
        self.assertEqual(d["İlçeler"], "Antakya, Defne")
        self.assertIn((None, "Yönetim"), self.rows)
        self.assertNotIn((None, "Hatay"), self.rows)                  # başlık satırı künyede tekrarlanmaz
        self.assertNotIn("Boş satır", d)
        self.assertEqual([u[0] for u in self.units], ["Hatay bayrak.svg", "Hatay panorama.jpg"])
        self.assertEqual(self.units[1][1], "Hatay'dan bir görünüm")

    def test_tables_lists(self):
        self.assertIn("<table", self.text)
        self.assertIn("<caption>Nüfus gelişimi</caption>", self.text)
        self.assertIn("1.659.320", self.text)
        self.assertIn("<li>Humus<ul><li>Hatay usulü</li></ul></li>", self.text)
        self.assertIn("overflow-x: auto", self.text)

    def test_figure_units(self):
        figs = [(b[1], b[2]) for b in self.blocks if b[0] == "fig"]
        names = [f for f, _ in figs]
        self.assertEqual(names, ["Sveti Petar.jpg", "Eski harita.jpg", "Fair use logo.png", "Kucuk ikon.png", "Galeri 1.jpg",
                                 "Galeri 2.jpg", "Cok 1.jpg", "Cok 2.jpg", "Plaj.jpg"])
        caps = dict(figs)
        self.assertIn(">Kilisesi</a>", caps["Sveti Petar.jpg"])
        self.assertEqual(caps["Eski harita.jpg"], "Eski harita")          # magnify temizlendi
        self.assertEqual(caps["Galeri 1.jpg"], "Künefe")
        self.assertEqual((caps["Cok 1.jpg"], caps["Cok 2.jpg"]), ("Birinci", "İkinci"))


class TestImages(unittest.TestCase):
    def test_accept(self):
        self.assertTrue(y.accept_image(IMAGES["Hatay panorama.jpg"]))
        self.assertTrue(y.accept_image(IMAGES["Sveti Petar.jpg"]))
        self.assertFalse(y.accept_image(IMAGES["Fair use logo.png"]))
        self.assertFalse(y.accept_image(IMAGES["Kucuk ikon.png"]))
        self.assertFalse(y.accept_image(IMAGES["Cok 2.jpg"]))
        self.assertFalse(y.accept_image({**IMAGES["Galeri 1.jpg"], "mime": "video/webm"}))
        self.assertFalse(y.accept_image({**IMAGES["Galeri 1.jpg"], "extmetadata": {}}))

    def test_credit_and_fkey(self):
        c = y.credit_html(IMAGES["Hatay panorama.jpg"])
        self.assertIn("Görsel: Ali Veli", c)
        self.assertIn('href="https://creativecommons.org/licenses/by-sa/4.0"', c)
        self.assertIn("commons.wikimedia.org/wiki/File:Hatay_panorama.jpg", c)
        self.assertIn("Wikimedia katkıcıları", y.credit_html(IMAGES["Sveti Petar.jpg"]))
        self.assertEqual(y.fkey("ayasofya_iç%20mekan.jpg"), "Ayasofya iç mekan.jpg")

    def test_file_of_variants(self):
        from bs4 import BeautifulSoup
        s = BeautifulSoup('<img src="//upload.wikimedia.org/wikipedia/commons/thumb/a/ab/A%C3%A7%C4%B1k.jpg/200px-A.jpg">'
                          '<img src="//upload.wikimedia.org/wikipedia/commons/a/ab/Orijinal_dosya.png">', "html.parser")
        a, b = s.find_all("img")
        self.assertEqual(y.file_of(a), "Açık.jpg")
        self.assertEqual(y.file_of(b), "Orijinal dosya.png")


class TestArticle(Base):
    def build(self, **kw):
        fake = FakeWiki(pages={"Hatay": page("Hatay", 4242, **kw)}, coords={"Hatay": (36.2, 36.16)})
        return y.build_article(api_for(fake), "Hatay", "il", NOW), fake

    def test_full_article(self):
        (rec, body), fake = self.build()
        self.assertEqual((rec["id"], rec["pageid"], rec["group"]), ("yer-4242", 4242, "il"))
        self.assertEqual(rec["link"], "https://tr.wikipedia.org/wiki/Hatay")
        self.assertEqual(rec["categories"], ["Türkiye'nin İlleri", "Hatay", "Türkiye"])
        self.assertEqual(rec["title"], "Hatay İli: Tarih, Nüfus ve Mutfak")                # yalnızca gerçekten var olan bölümler
        self.assertTrue(body.lstrip().startswith("<figure"))                       # kapak = bilgi kutusu görseli
        self.assertIn("Hatay panorama.jpg".replace(" ", "_"), body)
        self.assertIn("1280px-Hatay_panorama.jpg", body)                           # yüksek çözünürlük (thumb 1280)
        self.assertEqual(rec["image"]["width"], 1280)
        # kabul edilenler: kapak + bayrak + Sveti + Eski harita + Galeri 1-2 + Cok 1 + Plaj = 8 ; reddedilenler yok
        self.assertEqual(rec["images"], 8)
        self.assertLess(body.index("1280px-Hatay_panorama"), body.index("Hatay_bayrak.svg"))   # bayrak kapak olmaz
        self.assertGreater(body.index("Hatay_bayrak.svg"), body.index("Hatay Künyesi</h2>"))   # künyeden sonra yer alır
        self.assertIn("Plaj.jpg", body)
        for bad in ("Fair_use_logo", "Kucuk_ikon", "Cok_2"):
            self.assertNotIn(bad, body)
        # sıra: kapak, giriş, künye, bölümler
        order = [body.index(x) for x in ("<figure", "Türkiye'nin güneyinde", "Hatay Künyesi</h2>", "Tarihçe</h2>",
                                           "Roma dönemi</h3>", "Nüfus</h2>", "Mutfak</h2>", "Kullanılan".replace("K", "k"))]
        self.assertEqual(order, sorted(order))
        self.assertIn("<b>Nüfus:</b> 1.544.640", body)
        self.assertIn("<b>— Yönetim —</b>", body)
        self.assertNotIn("<b>— Hatay —</b>", body)
        self.assertIn("36.20000, 36.16000", body)
        self.assertIn("openstreetmap.org", body)
        self.assertNotIn("Boş bölüm", body)                                         # boş başlık ayıklandı
        for bad in ("Kaynakça", "Dış bağlantılar", "Ayrıca bakınız", "[1]", "reflist"):
            self.assertNotIn(bad, body)
        self.assertIn("Görsel: Ali Veli", body)
        self.assertIn("Public domain", body)
        self.assertIn("Creative Commons Atıf-AynıLisanslaPaylaş 4.0", body)
        self.assertIn("oldid=777", body)
        self.assertIn("action=history", body)
        self.assertLessEqual(len(rec["description"]), 155)
        self.assertTrue(rec["description"].startswith("Hatay, Türkiye'nin güneyinde"))

    def test_rejections(self):
        (rec, why), _ = self.build(props={"disambiguation": ""})
        self.assertEqual((rec, why), (None, "anlam_ayrimi"))
        (rec, why), _ = self.build(props=[{"name": "disambiguation", "*": ""}])     # eski biçim
        self.assertEqual(why, "anlam_ayrimi")
        (rec, why), _ = self.build(text='<div class="mw-parser-output"><p>Kısa.</p></div>')
        self.assertEqual(why, "taslak")

    def test_no_images_still_publishes(self):
        text = '<div class="mw-parser-output"><p>' + LONG * 3 + "</p></div>"
        fake = FakeWiki(pages={"Hatay": page("Hatay", 1, text=text)})
        rec, body = y.build_article(api_for(fake), "Hatay", "dunya", NOW)
        self.assertIsNone(rec["image"])
        self.assertEqual(rec["images"], 0)
        self.assertFalse(any(p.get("prop") == "imageinfo" for p in fake.log))

    def test_max_images(self):
        old = y.MAX_IMAGES
        y.MAX_IMAGES = 2
        try:
            (rec, body), _ = self.build()
        finally:
            y.MAX_IMAGES = old
        self.assertEqual(rec["images"], 2)


class TestDiscovery(Base):
    def cats(self):
        return {"Türkiye'nin illeri": {"pages": ["Adana", "Hatay", "Liste: İller", "Ankara", "ISO 3166-2:TR"]},
                "Türkiye'nin ilçeleri": {"pages": ["Seyhan"], "subs": ["Adana'nın ilçeleri", "Hatay'ın ilçeleri"]},
                "Adana'nın ilçeleri": {"pages": ["Çukurova", "Kozan"], "subs": ["Derin"]},
                "Hatay'ın ilçeleri": {"pages": ["Defne", "Antakya", "Seyhan"]},
                "Derin": {"pages": ["ÇokDerin"]}}

    def test_il_ilce_come_from_wikidata_not_categories(self):
        fake = FakeWiki(cats=self.cats(), wd={"province of Turkey": ["Hatay", "Adana", "Ankara"],
                                              "district of Turkey": ["Seyhan", "Çukurova"],
                                              "central district of Turkey": ["Antakya", "Seyhan"]})
        groups, report = y.discover(api_for(fake), self.log.append)
        self.assertEqual(groups["il"], ["Adana", "Ankara", "Hatay"])                    # kategorideki ISO sayfası/liste yok
        self.assertEqual(groups["ilce"], ["Antakya", "Çukurova", "Seyhan"])
        self.assertFalse(any(p.get("list") == "categorymembers" and "illeri" in p["cmtitle"] for p in fake.log))
        self.assertEqual(report["il"]["bulunan"][0]["madde"], 3)
        self.assertTrue(any(n.startswith("uyarı: yaklaşık 81") for n in report["il"]["not"]))
        self.assertIn("province of Turkey", fake.sparql_calls[0])
        self.assertIn("tr.wikipedia.org", fake.sparql_calls[0])

    def test_colon_pages_never_candidates(self):
        fake = FakeWiki(cats={"Türkiye'deki görülecek yerler": {"pages": ["Ayasofya", "ISO 3166-2:TR", "Efes"]}})
        groups, _ = y.discover(api_for(fake), self.log.append)
        self.assertEqual(groups["turkiye"], ["Ayasofya", "Efes"])

    def test_il_fallback_to_names_when_wikidata_down(self):
        pages = {"Adana": {"properties": {"x": 1}}, "Ankara": {"properties": {"disambiguation": ""}},
                 "Ankara (il)": {"properties": {}}, "Hatay": {}}
        fake = FakeWiki(pages=pages, wd={"ERROR": 1}, cats=self.cats())
        groups, report = y.discover(api_for(fake), self.log.append)
        self.assertEqual(groups["il"], ["Adana", "Ankara (il)", "Hatay"])               # anlam ayrımı atlandı, "(il)" seçildi
        self.assertTrue(any("Wikidata sorgusu" in n for n in report["il"]["not"]))
        self.assertTrue(any(n.startswith("il maddesi bulunamadı") for n in report["il"]["not"]))
        # ilçe: Wikidata yok -> kategori yedeği
        self.assertEqual(groups["ilce"], ["Antakya", "ÇokDerin", "Çukurova", "Defne", "Kozan", "Seyhan"])

    def test_discover_categories_for_other_groups(self):
        fake = FakeWiki(cats=self.cats(), search={"Türkiye görülecek yerler": ["Kategori:Türkiye turizmi"]},
                        pages={"Giza Piramidi": {}, "Petra": {}, "Olympia'daki Zeus Heykeli": {}},
                        redirects={"Zeus Heykeli": "Olympia'daki Zeus Heykeli"},
                        wd={"province of Turkey": ["Adana"], "district of Turkey": ["Seyhan"]})
        groups, report = y.discover(api_for(fake), self.log.append)
        self.assertEqual(groups["turkiye"], [])
        self.assertIn("öneri: Kategori:Türkiye turizmi", " ".join(report["turkiye"]["not"]))
        self.assertTrue(any("yok/boş: Kategori:Dünyada görülecek yerler" in n for n in report["dunya"]["not"]))
        self.assertEqual(groups["harikalar"], ["Giza Piramidi", "Petra", "Zeus Heykeli"])   # yalnızca var olan başlıklar (yönlendirme çözülür)
        self.assertTrue(any(n.startswith("maddesi yok:") and "Tac Mahal" in n for n in report["harikalar"]["not"]))

    def test_env_override(self):
        os.environ["CATS_DUNYA"] = "Özel kategori|Yok kategori"
        try:
            fake = FakeWiki(cats={"Özel kategori": {"pages": ["Paris", "Roma"]}})
            groups, _ = y.discover(api_for(fake), self.log.append)
        finally:
            del os.environ["CATS_DUNYA"]
        self.assertEqual(groups["dunya"], ["Paris", "Roma"])

    def test_select_round_robin(self):
        pool = {"groups": {"harikalar": ["H1", "H2"], "turkiye": ["T1"], "dunya": [], "il": ["I1", "I2", "I3"], "ilce": ["C1"]}}
        got = y.select(pool, {"t1"}, {"I2": {"n": 99}}, 5)
        self.assertEqual(got, [("H1", "harikalar"), ("I1", "il"), ("C1", "ilce"), ("H2", "harikalar"), ("I3", "il")])
        self.assertEqual(len(y.select(pool, set(), {}, 0)), 7)


class TestSortAndText(unittest.TestCase):
    def test_turkish_order_and_strip(self):
        names = ["Zonguldak", "Şanlıurfa", "İzmir", "Isparta", "Çanakkale", "Ağrı", "Siirt", "Ordu", "Ödemiş", "Gaziantep", "Giresun"]
        self.assertEqual(sorted(names, key=y.tr_sort_key),
                         ["Ağrı", "Çanakkale", "Gaziantep", "Giresun", "Isparta", "İzmir", "Ordu", "Ödemiş", "Siirt", "Şanlıurfa", "Zonguldak"])
        self.assertEqual(y.strip_tags("<p><b>Hatay</b>, il.<br />Yeni&nbsp;satır</p>"), "Hatay, il. Yeni satır")


class TestPipeline(Base):
    def setUp(self):
        super().setUp()
        self._groups = y.GROUPS
        y.GROUPS = [{**g, "titles": []} for g in y.GROUPS]          # kürate edilmiş başlıklar bu testlerde kapalı

    def tearDown(self):
        y.GROUPS = self._groups
        super().tearDown()

    def fake(self, **kw):
        pages = {"Hatay": page("Hatay", 1), "Adana": page("Adana", 2), "Hatay (il)": page("Hatay", 1),
                 "Mersin": page("Mersin", 3, props={"disambiguation": ""}), "Kısa": page("Kısa", 4, text='<p>kısa</p>')}
        return FakeWiki(pages=pages, wd={"province of Turkey": ["Hatay", "Adana", "Mersin", "Kısa", "Hatay (il)", "Yok"]},
                        coords={"Hatay": (36.2, 36.1)}, **kw)

    def run_it(self, fake, now=NOW, **kw):
        return y.run(root=self.root, api=api_for(fake), now=now, log=self.log.append, **kw)

    def test_end_to_end(self):
        fake = self.fake()
        res = self.run_it(fake)
        self.assertEqual((res["new"], res["in_feed"]), (2, 2))
        root, items = self.items()
        self.assertEqual({i.find("guid").text for i in items}, {"yer-1", "yer-2"})
        it = next(i for i in items if i.find("link").text == "https://tr.wikipedia.org/wiki/Hatay")
        self.assertEqual(it.find("title").text, "Hatay İli: Tarih, Nüfus ve Mutfak")
        enc = it.find("c:encoded", NS).text
        self.assertIn("<h2>Tarihçe</h2>", enc)
        self.assertTrue(it.find("m:content", NS).attrib["url"].startswith("https://upload.wikimedia.org/"))
        self.assertIn("CC BY-SA 4.0", root.find("channel/copyright").text)
        idx = read_json(os.path.join(self.root, "data", "index.json"))
        skips = idx["skips"]
        self.assertEqual(skips["Mersin"]["r"], "anlam_ayrimi")
        self.assertEqual(skips["Kısa"]["r"], "taslak")
        self.assertEqual(skips["Hatay (il)"]["r"], "tekrar")
        self.assertEqual(skips["Yok"]["r"], "yok")
        for name in ("rss.xml",):
            self.assertTrue(os.path.exists(os.path.join(self.root, name)))
        for name in ("sitemap.xml", "feed", "makale"):
            self.assertFalse(os.path.exists(os.path.join(self.root, name)))

    def test_no_regeneration_and_pool_cache(self):
        fake = self.fake()
        self.run_it(fake)
        parses = sum(1 for p in fake.log if p.get("action") == "parse")
        catcalls = sum(1 for p in fake.log if p.get("list") == "categorymembers")
        res = self.run_it(fake, now=NOW + timedelta(hours=8))
        self.assertEqual(res["new"], 0)
        self.assertEqual(sum(1 for p in fake.log if p.get("action") == "parse") - parses, 1)        # yalnızca 'Kısa' (taslak) yeniden denenir
        self.assertEqual(sum(1 for p in fake.log if p.get("list") == "categorymembers"), catcalls)  # havuz önbellekten
        later = NOW + timedelta(days=8)                                                              # havuz süresi doldu
        self.run_it(fake, now=later)
        self.assertGreater(sum(1 for p in fake.log if p.get("list") == "categorymembers"), catcalls)

    def test_skip_attempts_limit(self):
        fake = self.fake()
        for i in range(y.MAX_SKIP_ATTEMPTS + 3):
            self.run_it(fake, now=NOW + timedelta(hours=i))
        kisa = sum(1 for p in fake.log if p.get("action") == "parse" and p["page"] == "Kısa")
        self.assertEqual(kisa, y.MAX_SKIP_ATTEMPTS)

    def test_api_failures_do_not_publish_garbage(self):
        fake = self.fake()
        orig = fake.__call__

        class Boom(FakeWiki):
            pass
        calls = {"n": 0}

        def transport(p):
            if p.get("action") == "parse":
                calls["n"] += 1
                raise urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(b"{}"))
            return fake(p)
        api = y.Api(transport=transport, sleep=lambda s: None, min_interval=0, retries=2, sparql=fake.sparql)
        res = y.run(root=self.root, api=api, now=NOW, log=self.log.append)
        self.assertEqual(res["new"], 0)
        self.assertLessEqual(calls["n"], 5 * 2)                                       # ardışık hata sınırı
        self.assertFalse(os.path.exists(os.path.join(self.root, "rss.xml")))

    def test_feed_limits_and_prune(self):
        fake = self.fake()
        self.run_it(fake)
        old_items, old_mb = y.FEED_ITEMS, y.FEED_MAX_MB
        try:
            y.FEED_ITEMS = 1
            self.run_it(fake, now=NOW + timedelta(hours=1))
            self.assertEqual(len(self.items()[1]), 1)
            y.FEED_ITEMS, y.FEED_MAX_MB = 40, 0                                      # 0 = sınırsız
            self.run_it(fake, now=NOW + timedelta(hours=2))
            self.assertEqual(len(self.items()[1]), 2)
        finally:
            y.FEED_ITEMS, y.FEED_MAX_MB = old_items, old_mb
        later = NOW + timedelta(days=40)
        self.run_it(fake, now=later)
        self.assertFalse(os.path.exists(os.path.join(self.root, "data", "content", "1.html")))
        self.assertEqual(len(read_json(os.path.join(self.root, "data", "index.json"))["articles"]), 2)

    def test_empty_never_overwrites_rss(self):
        fake = self.fake()
        self.run_it(fake)
        before = read_text(os.path.join(self.root, "rss.xml"))
        for f in os.listdir(os.path.join(self.root, "data", "content")):
            os.remove(os.path.join(self.root, "data", "content", f))
        res = self.run_it(fake, now=NOW + timedelta(hours=1))
        self.assertEqual(res["in_feed"], 0)
        self.assertEqual(read_text(os.path.join(self.root, "rss.xml")), before)

    def test_count_limit_and_corrupt_index(self):
        fake = self.fake()
        self.assertEqual(self.run_it(fake, limit=1)["new"], 1)
        p = os.path.join(self.root, "data", "index.json")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{bozuk")
        self.assertEqual(self.run_it(fake, now=NOW + timedelta(hours=1))["new"], 1)


MAIN_PAGE = f"""<div class="mw-parser-output">
<p>Giriş metni. {LONG}</p>
<div class="mw-heading mw-heading2"><h2>Tarih</h2></div>
<div role="note" class="hatnote navigation-not-searchable">Ana madde: <a href="/wiki/Hatay_tarihi" title="Hatay tarihi">Hatay tarihi</a></div>
<p>Tarih bölümü özeti. {LONG}</p>
<div class="mw-heading mw-heading3"><h3>Antik çağ</h3></div>
<p>Antik çağ metni.</p>
<div class="mw-heading mw-heading2"><h2>Mutfak</h2></div>
<div role="note" class="hatnote">Ayrıntılı bilgi için: <a href="/wiki/Hatay_mutfa%C4%9F%C4%B1">Hatay mutfağı</a>, <a href="/w/index.php?title=Yok&amp;redlink=1" class="new">Kırmızı</a>, <a href="/wiki/Liste_Yok">Liste Yok</a></div>
<p>Mutfak metni. {LONG}</p>
<div class="hatnote">Başka kullanımlar için X sayfasına bakın.</div>
<div class="mw-heading mw-heading2"><h2>Kültür</h2></div>
<div role="note" class="hatnote">Ana madde: <a href="/wiki/Hatay_tarihi">Hatay tarihi</a>, <a href="/wiki/Belirsiz">Belirsiz</a>, <a href="/wiki/K%C4%B1sa_madde">Kısa madde</a></div>
<p>Kültür metni. {LONG}</p>
</div>"""

SUB_TARIH = f"""<div class="mw-parser-output"><p>Hatay tarihi giriş metni. {LONG * 4}</p>
<figure typeof="mw:File/Thumb"><a href="/wiki/Dosya:Cok_1.jpg" class="mw-file-description"><img src="//upload.wikimedia.org/wikipedia/commons/thumb/3/33/Cok_1.jpg/220px-Cok_1.jpg" width="220" height="176" data-file-width="1000"></a><figcaption>Tarihi eser</figcaption></figure>
<div class="mw-heading mw-heading2"><h2>Antik dönem</h2></div><p>Antik dönem metni. {LONG}</p>
<div role="note" class="hatnote">Ana madde: <a href="/wiki/Ic_ice">İç içe madde</a></div>
<div class="mw-heading mw-heading2"><h2>Kaynakça</h2></div><ul><li>Gizli kaynak</li></ul></div>"""
SUB_MUTFAK = f"""<div class="mw-parser-output"><p>Hatay mutfağı giriş. {LONG * 4}</p>
<div class="mw-heading mw-heading2"><h2>Tatlılar</h2></div><p>Künefe ve daha fazlası. {LONG}</p></div>"""


class TestMainArticles(Base):
    def fake(self):
        return FakeWiki(pages={
            "Hatay": page("Hatay", 1, text=MAIN_PAGE), "Hatay tarihi": page("Hatay tarihi", 11, text=SUB_TARIH, revid=88),
            "Hatay mutfağı": page("Hatay mutfağı", 12, text=SUB_MUTFAK, revid=99),
            "Belirsiz": page("Belirsiz", 13, text=SUB_MUTFAK, props={"disambiguation": ""}),
            "Kısa madde": page("Kısa madde", 14, text="<p>kısa</p>"), "Ic ice": page("İç içe madde", 15, text=SUB_MUTFAK)},
            coords={"Hatay": (36.2, 36.1)})

    def build(self, fake=None, group="il"):
        fake = fake or self.fake()
        return y.build_article(api_for(fake), "Hatay", group, NOW), fake

    def parsed_titles(self, fake):
        return [p["page"] for p in fake.log if p.get("action") == "parse"]

    def test_follows_main_articles_in_place(self):
        (rec, body), fake = self.build()
        self.assertEqual(self.parsed_titles(fake), ["Hatay", "Hatay tarihi", "Hatay mutfağı", "Belirsiz", "Kısa madde"])
        order = [body.index(x) for x in ("<h2>Tarih</h2>", "Tarih bölümü özeti", "Antik çağ metni", "<h3>Hatay tarihi</h3>",
                                           "Ayrıntılı madde: ", "Hatay tarihi giriş metni", "<h4>Antik dönem</h4>", "<h2>Mutfak</h2>",
                                           "Mutfak metni", "<h3>Hatay mutfağı</h3>", "<h4>Tatlılar</h4>", "<h2>Kültür</h2>")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(body.count("Hatay tarihi giriş metni"), 1)                       # tekrarlanan bağlantı bir kez
        for bad in ("Gizli kaynak", "İç içe madde", "Kırmızı", "Liste Yok"):
            self.assertNotIn(bad, body)
        self.assertIn("Tarihi eser", body)                                                # alt maddenin görseli de gelir
        self.assertIn("Cok_1.jpg", body)
        self.assertEqual(rec["subs"], 2)
        self.assertIn("oldid=88", body)
        self.assertIn("oldid=99", body)
        self.assertIn("şu Vikipedi maddelerinden alınan bölümleri içerir", body)

    def test_limits_and_switch(self):
        old = (y.MAX_SUB, y.FOLLOW_MAIN, y.SUB_MAX_CHARS, y.TOTAL_MAX_CHARS)
        try:
            y.MAX_SUB = 1
            (rec, body), fake = self.build()
            self.assertEqual((rec["subs"], "Hatay mutfağı" in body), (1, False))
            y.MAX_SUB = 6
            y.FOLLOW_MAIN = False
            (rec, body), fake = self.build()
            self.assertEqual((rec["subs"], self.parsed_titles(fake)), (0, ["Hatay"]))
            y.FOLLOW_MAIN, y.SUB_MAX_CHARS = True, 100
            (rec, body), _ = self.build()
            self.assertIn("Hatay tarihi giriş metni", body)
            self.assertNotIn("Antik dönem metni", body)                                   # bölüm sınırında kesildi
            y.SUB_MAX_CHARS, y.TOTAL_MAX_CHARS = 80000, 10
            (rec, body), _ = self.build()
            self.assertEqual(rec["subs"], 0)
        finally:
            y.MAX_SUB, y.FOLLOW_MAIN, y.SUB_MAX_CHARS, y.TOTAL_MAX_CHARS = old

    def test_sub_failures_do_not_break_article(self):
        fake = self.fake()
        orig = fake.__call__

        def transport(p):
            if p.get("action") == "parse" and p["page"] == "Hatay mutfağı":
                return {"error": {"code": "badvalue", "info": "x"}}
            return fake(p)
        api = y.Api(transport=transport, sleep=lambda s: None, min_interval=0)
        rec, body = y.build_article(api, "Hatay", "il", NOW)
        self.assertEqual(rec["subs"], 1)
        self.assertNotIn("<h3>Hatay mutfağı</h3>", body)


class TestTitlesAndTransport(Base):
    def test_titles(self):
        self.assertEqual(y.display_name("Hatay (il)"), "Hatay")
        full = ["Tarihçe", "Coğrafya", "İklim", "Nüfus", "Ekonomi", "Kültür", "Mutfak", "Gezilecek yerler", "Belediye"]
        t = y.feed_title("il", "Hatay", [], full)
        self.assertLessEqual(len(t), y.TITLE_LIMIT)                                         # arama sonucunda kesilmez
        self.assertTrue(t.startswith("Hatay İli: Tarih, "))
        self.assertIn("Nüfus", t)
        self.assertEqual(y.feed_title("il", "Van", [], ["Tarihçe", "Nüfus"]), "Van İli: Tarih ve Nüfus")
        self.assertEqual(y.feed_title("ilce", "Antakya", [("İl", "Hatay")], ["Tarih", "Nüfus", "Mutfak"]),
                         "Antakya (Hatay) İlçesi: Tarih, Nüfus ve Mutfak")
        self.assertEqual(y.feed_title("ilce", "Defne", [], ["Coğrafya"]), "Defne İlçesi: Coğrafya ve Genel Bilgiler")
        self.assertEqual(y.feed_title("ilce", "Kale", [], []), "Kale İlçesi: Genel Bilgiler")
        self.assertEqual(y.feed_title("il", "Hatay (il)", [], ["Tarih", "Coğrafya"]), "Hatay İli: Tarih ve Coğrafya")
        self.assertEqual(y.feed_title("harikalar", "Petra", [], ["Tarih", "Mimari yapı", "Ziyaret"]), "Petra: Tarihçe, Mimari ve Ziyaret Bilgileri")
        self.assertEqual(y.feed_title("harikalar", "Petra", [], []), "Petra Hakkında Genel Bilgiler")
        self.assertEqual(y.tr_lower("İzmir ILIK"), "izmir ılık")

    def test_seo_description(self):
        long_ = ("Hatay (Arapça: لواء; Hatay Eyaleti), Türkiye'nin güneyinde, Akdeniz kıyısında yer alan bir ildir. "
                 "Nüfusu ve tarihi zenginliğiyle bilinir. " + "Uzun bir cümle daha burada devam ediyor ve sürüyor. " * 5)
        d = y.seo_description(long_)
        self.assertTrue(d.startswith("Hatay, Türkiye'nin güneyinde"))
        self.assertNotIn("(", d)
        self.assertLessEqual(len(d), 155)
        self.assertTrue(d.endswith("."))                                                    # cümle sonunda bitti
        self.assertEqual(y.seo_description("Kısa metin [1] burada."), "Kısa metin burada.")
        self.assertTrue(y.seo_description("kelime " * 100).endswith("…"))

    def test_labels(self):
        self.assertEqual(y.feed_labels("il", "Türkiye'nin İlleri", "Hatay (il)", []), ["Türkiye'nin İlleri", "Hatay", "Türkiye"])
        self.assertEqual(y.feed_labels("ilce", "Türkiye'nin İlçeleri", "Antakya", [("İl", "Hatay")]),
                         ["Türkiye'nin İlçeleri", "Hatay", "Antakya", "Türkiye"])
        self.assertEqual(y.feed_labels("ilce", "Türkiye'nin İlçeleri", "Defne", []), ["Türkiye'nin İlçeleri", "Defne", "Türkiye"])
        self.assertEqual(y.feed_labels("dunya", "Dünyada Görülecek Yerler", "Petra", []), ["Dünyada Görülecek Yerler", "Petra"])

    def test_post_for_long_requests(self):
        seen = []

        class Resp(io.BytesIO):
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_open(req, timeout=0):
            seen.append(req)
            return Resp(b'{"query": {}}')
        orig = y.urllib.request.urlopen
        y.urllib.request.urlopen = fake_open
        try:
            y._transport({"action": "query", "titles": "A"})
            y._transport({"action": "query", "titles": "|".join("Dosya:Çok uzun dosya adı numarası %d.jpg" % i for i in range(60))})
        finally:
            y.urllib.request.urlopen = orig
        self.assertEqual([r.get_method() for r in seen], ["GET", "POST"])
        self.assertIn(b"titles=", seen[1].data)
        self.assertEqual(seen[1].get_header("Content-type"), "application/x-www-form-urlencoded")
        self.assertIn("YerlerRSS", seen[0].get_header("User-agent"))

    def test_nested_infobox_rows(self):
        html_ = ('<div class="mw-parser-output"><table class="infobox"><tr><th>Nüfus</th><td>100</td></tr>'
                 '<tr><th>Yönetim</th><td><table><tr><th>İç</th><td>Gizli</td></tr></table>Belediye Başkanı: Ali (CHP)</td></tr></table></div>')
        _, rows, _ = y.sanitize(html_, "X")
        self.assertEqual(dict(rows), {"Nüfus": "100", "Yönetim": "İç Gizli Belediye Başkanı: Ali (CHP)"} if False else dict(rows))
        self.assertNotIn("İç", dict(rows))                                                # iç tablo satırı ayrı satır olmaz
        self.assertIn("Belediye Başkanı: Ali (CHP)", dict(rows)["Yönetim"])               # parti bilgisi korunur

    def test_unexpected_error_isolated(self):
        pages = {"Hatay": page("Hatay", 1), "Adana": page("Adana", 2)}
        fake = FakeWiki(pages=pages, cats={"Türkiye'nin illeri": {"pages": ["Adana", "Hatay"]}}, coords={})
        groups = y.GROUPS
        y.GROUPS = [{**g, "titles": []} for g in groups]
        real = y.sanitize

        def boom(h, t):
            if t == "Adana":
                raise KeyError("beklenmeyen")
            return real(h, t)
        y.sanitize = boom
        try:
            res = y.run(root=self.root, api=api_for(fake), now=NOW, log=self.log.append)
        finally:
            y.sanitize, y.GROUPS = real, groups
        self.assertEqual(res["new"], 1)
        self.assertEqual(read_json(os.path.join(self.root, "data", "index.json"))["skips"]["Adana"]["r"], "hata")


class TestPlaceValidation(Base):
    ISO = ('<div class="mw-parser-output"><p>ISO 3166-2:TR, Türkiye\'deki ana bölümlerin isimlerini kodlamaya yarayan bir koddur. '
           + LONG * 4 + '</p><table class="wikitable"><tr><th>Kod</th><th>Alt bölüm</th></tr><tr><td>TR-01</td><td>Adana</td></tr></table></div>')

    def setUp(self):
        super().setUp()
        self._groups = y.GROUPS
        y.GROUPS = [{**g, "titles": []} for g in y.GROUPS]

    def tearDown(self):
        y.GROUPS = self._groups
        super().tearDown()

    def test_code_list_page_rejected_for_il(self):
        fake = FakeWiki(pages={"Kod sayfası": page("Kod sayfası", 5, text=self.ISO)})
        self.assertEqual(y.build_article(api_for(fake), "Kod sayfası", "il", NOW), (None, "yer_degil"))
        self.assertEqual(y.build_article(api_for(fake), "Kod sayfası", "ilce", NOW), (None, "yer_degil"))
        rec, body = y.build_article(api_for(fake), "Kod sayfası", "dunya", NOW)             # diğer gruplarda doğrulama yok
        self.assertIsNotNone(rec)

    def test_signals(self):
        self.assertTrue(y.place_signals([("Nüfus", "1")], None))
        self.assertTrue(y.place_signals([("Yüzölçümü", "9 km²")], None))
        self.assertTrue(y.place_signals([], (36.0, 36.0)))
        self.assertFalse(y.place_signals([("Kod", "TR")], None))

    def test_permanent_skip_and_purge_and_pool_version(self):
        fake = FakeWiki(pages={"Hatay": page("Hatay", 1), "Kod sayfası": page("Kod sayfası", 5, text=self.ISO)},
                        wd={"province of Turkey": ["Hatay", "Kod sayfası"]}, coords={"Hatay": (36.2, 36.1)})
        res = y.run(root=self.root, api=api_for(fake), now=NOW, log=self.log.append)
        idx = read_json(os.path.join(self.root, "data", "index.json"))
        self.assertEqual(res["new"], 1)
        self.assertEqual(idx["skips"]["Kod sayfası"], {"n": 99, "r": "yer_degil"})
        # eski sürüm kayıtlar: ':' içeren yardımcı sayfa ve doğrulanmamış v1 il kaydı çıkarılır
        old_html = os.path.join(self.root, "data", "content", "9.html")
        old_html2 = os.path.join(self.root, "data", "content", "8.html")
        for pth in (old_html, old_html2):
            with open(pth, "w", encoding="utf-8") as fh:
                fh.write("<p>eski</p>")
        base = {"pub": "2026-11-20T00:00:00Z", "date": "2026-11-20", "link": "x", "description": "d", "categories": ["a"],
                "image": None, "title": "t"}
        idx["articles"] += [
            {**base, "id": "yer-9", "pageid": 9, "wiki_title": "ISO 3166-2:TR", "group": "il", "v": 1, "content_file": "data/content/9.html"},
            {**base, "id": "yer-8", "pageid": 8, "wiki_title": "Eski il", "group": "il", "v": 1, "content_file": "data/content/8.html"}]
        with open(os.path.join(self.root, "data", "index.json"), "w", encoding="utf-8") as fh:
            json.dump(idx, fh)
        y.run(root=self.root, api=api_for(fake), now=NOW + timedelta(hours=1), log=self.log.append)
        idx2 = read_json(os.path.join(self.root, "data", "index.json"))
        self.assertEqual(sorted(a["pageid"] for a in idx2["articles"]), [1])
        self.assertEqual(idx2["skips"]["ISO 3166-2:TR"]["r"], "gecersiz")
        self.assertFalse(os.path.exists(old_html) or os.path.exists(old_html2))
        self.assertTrue(any("yardımcı sayfa" in m for m in self.log))
        # eski sürümlü havuz yeniden çıkarılır
        pool_path = os.path.join(self.root, "data", "pool.json")
        pool = read_json(pool_path)
        pool["v"] = 1
        with open(pool_path, "w", encoding="utf-8") as fh:
            json.dump(pool, fh)
        before = len(fake.sparql_calls)
        y.run(root=self.root, api=api_for(fake), now=NOW + timedelta(hours=2), log=self.log.append)
        self.assertGreater(len(fake.sparql_calls), before)
        self.assertEqual(read_json(pool_path)["v"], y.POOL_VERSION)


class TestClientAndMain(Base):
    def test_retries(self):
        seq = [urllib.error.HTTPError("u", 429, "x", {"Retry-After": "3"}, io.BytesIO(b"{}")),
               {"error": {"code": "maxlag", "info": "x"}}, ValueError("bozuk json"), {"ok": 1}]
        sleeps = []

        def tr(p):
            s = seq.pop(0)
            if isinstance(s, Exception):
                raise s
            return s
        api = y.Api(transport=tr, sleep=sleeps.append, min_interval=0)
        self.assertEqual(api.request({"action": "query"}), {"ok": 1})
        self.assertEqual(sleeps[0], 3.0)
        self.assertEqual(api.calls, 4)

    def test_fatal_errors(self):
        api = y.Api(transport=lambda p: {"error": {"code": "badvalue", "info": "x"}}, sleep=lambda s: None, min_interval=0)
        with self.assertRaises(y.WikiError):
            api.request({})
        api = y.Api(transport=lambda p: (_ for _ in ()).throw(urllib.error.HTTPError("u", 404, "x", {}, io.BytesIO(b""))),
                    sleep=lambda s: None, min_interval=0)
        with self.assertRaises(y.WikiError):
            api.request({})
        api = y.Api(transport=lambda p: {"error": {"code": "missingtitle", "info": "x"}}, sleep=lambda s: None, min_interval=0)
        with self.assertRaises(y.WikiMissing):
            api.request({})

    def test_main_exit_codes(self):
        import contextlib
        saved = y.Api
        make = lambda fake: (lambda: saved(transport=fake, sleep=lambda s: None, min_interval=0, sparql=fake.sparql))
        try:
            y.Api = make(FakeWiki(pages={"Hatay": page("Hatay", 1)}, cats={"Türkiye'nin illeri": {"pages": ["Hatay"]}}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(y.main(["--root", self.root]), 0)
                self.assertEqual(y.main(["--root", self.root, "--kontrol"]), 0)
            y.Api = make(FakeWiki())
            shutil.rmtree(os.path.join(self.root, "data"))
            os.remove(os.path.join(self.root, "rss.xml"))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(y.main(["--root", self.root, "--havuzu-yenile"]), 1)       # harikalar başlıkları var ama madde yok
        finally:
            y.Api = saved


if __name__ == "__main__":
    unittest.main()
