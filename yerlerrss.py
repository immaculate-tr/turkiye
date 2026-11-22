#!/usr/bin/env python3
"""Vikipedi (tr) yer / il / ilçe makaleleri -> tam içerikli RSS (yalnızca rss.xml).

Kaynak gruplar (aday havuzu Vikipedi kategorilerinden çıkarılır, çalışma anında doğrulanır):
  * Dünyanın Harikaları, Türkiye'de Görülecek Yerler, Dünyada Görülecek Yerler, Türkiye'nin İlleri, İlçeleri

Her makale: Vikipedi maddesinin TAMAMI (giriş, künye/bilgi kutusu, tüm bölümler, tablolar, galeri) temizlenmiş HTML olarak
`content:encoded` içinde gelir. Görseller maddede geçen dosyaların birebir kendisidir; Wikimedia API'sinden
yüksek çözünürlükte (en çok 1280 px) alınır, her görselin yazarı ve lisansı altına yazılır. Telifsiz/lisansı belirsiz
(fair-use) görseller alınmaz. Makale metni CC BY-SA 4.0'dır; kaynak ve lisans notu her makalenin sonuna eklenir.

* Aynı madde (pageid) bir daha üretilmez; kayıt data/index.json içindedir (Actions önbelleği).
* Aday havuzu data/pool.json içinde POOL_TTL_DAYS gün saklanır.
* `python yerlerrss.py --kontrol` yalnızca kategorileri doğrular ve raporlar (makale üretmez).
"""
from __future__ import annotations

import argparse
import gzip
import html
import http.client
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape, quoteattr

try:
    from bs4 import BeautifulSoup, Comment, NavigableString, Tag
except ImportError:  # pragma: no cover
    print("::error::beautifulsoup4 kurulu değil: pip install beautifulsoup4")
    raise


def _int(name, default):
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


# ----------------------------------------------------------------------------- ayarlar
SITE_URL = (os.environ.get("SITE_URL") or "https://xmifrmx.github.io/yerler").rstrip("/")
SITE_ROOT = os.environ.get("SITE_ROOT", ".")
SITE_TITLE = "Yerler Rehberi – Dünya, Türkiye, İl ve İlçeler"
SITE_DESC = ("Dünyanın harikaları, Türkiye ve dünyada görülecek yerler, Türkiye'nin illeri ve ilçeleri: tarih, coğrafya, "
             "kültür, mutfak, nüfus ve ekonomi. Metinler Vikipedi'den (CC BY-SA 4.0) alınmıştır.")
COPYRIGHT = "Makale metinleri Vikipedi'den CC BY-SA 4.0 lisansıyla alınmıştır; görsellerin lisansı altlarında belirtilmiştir."
CONTACT = os.environ.get("WIKI_CONTACT") or "https://github.com/xmifrmx/yerler"
USER_AGENT = f"YerlerRSS/1.0 ({CONTACT}; GitHub Actions) python-urllib"
WIKI = "tr"
WIKI_HOST = f"https://{WIKI}.wikipedia.org"
PER_RUN = _int("PER_RUN", 10)                    # bir çalışmada en fazla yeni makale (0 = sınırsız)
FEED_ITEMS = _int("FEED_ITEMS", 100)              # RSS'teki en yeni makale sayısı
FEED_MAX_MB = _int("FEED_MAX_MB", 25)            # rss.xml üst boyutu (aşılırsa en eski öğeler çıkar)
MIN_TEXT_CHARS = _int("MIN_TEXT_CHARS", 1500)    # bundan kısa madde = taslak, atlanır (sonra yeniden denenir)
MAX_IMAGES = _int("MAX_IMAGES", 80)              # makale başına en çok görsel
IMG_WIDTH = _int("IMG_WIDTH", 1280)              # görsel genişliği (Wikimedia'nın izin verdiği basamak)
MIN_IMG_W = _int("MIN_IMG_W", 400)               # bundan dar görseller (ikon, bayrak) alınmaz
POOL_TTL_DAYS = _int("POOL_TTL_DAYS", 7)
MAX_SKIP_ATTEMPTS = _int("MAX_SKIP_ATTEMPTS", 6)
CONTENT_KEEP_DAYS = _int("CONTENT_KEEP_DAYS", 30)
MAX_TABLE_ROWS = _int("MAX_TABLE_ROWS", 400)
FOLLOW_MAIN = (os.environ.get("FOLLOW_MAIN") or "1").strip().lower() not in ("0", "false", "hayır", "hayir", "no")
MAX_SUB = _int("MAX_SUB", 6)                     # makale başına en çok "Ana madde" ile bağlı ayrıntılı madde
SUB_MIN_CHARS = _int("SUB_MIN_CHARS", 600)       # bundan kısa ayrıntılı maddeler eklenmez
SUB_MAX_CHARS = _int("SUB_MAX_CHARS", 80000)     # tek ayrıntılı maddeden en çok metin (bölüm sınırında kesilir)
TOTAL_MAX_CHARS = _int("TOTAL_MAX_CHARS", 500000)  # makalenin toplam metin sınırı (aşılınca yeni ayrıntılı madde eklenmez)
BUILD_VERSION = 1

# Gruplar: cats = denenecek kategori adları (varolanların hepsi birleştirilir), titles = doğrudan madde adları.
# Ortam değişkeniyle değiştirilebilir: CATS_ILCE="Kategori adı 1|Kategori adı 2"
GROUPS = [
    {"key": "harikalar", "label": "Dünyanın Harikaları", "depth": 1, "search": "Dünyanın harikaları",
     "cats": ["Dünyanın harikaları", "Dünyanın yedi harikası", "Dünyanın Yedi Harikası"],
     "titles": ["Dünyanın Yedi Harikası", "Dünyanın Yeni Yedi Harikası", "Giza Piramidi", "Babil'in Asma Bahçeleri", "Artemis Tapınağı", "Halikarnas Mozolesi",
                "İskenderiye Feneri", "Rodos Heykeli", "Zeus Heykeli", "Çin Seddi", "Petra", "Machu Picchu",
                "Kurtarıcı İsa Heykeli", "Chichén Itzá", "Kolezyum", "Tac Mahal"]},
    {"key": "turkiye", "label": "Türkiye'de Görülecek Yerler", "depth": 2, "search": "Türkiye görülecek yerler",
     "cats": ["Türkiye'deki görülecek yerler", "Türkiye'de görülecek yerler"], "titles": []},
    {"key": "dunya", "label": "Dünyada Görülecek Yerler", "depth": 2, "search": "Dünyada görülecek yerler",
     "cats": ["Dünyada görülecek yerler", "Dünyadaki görülecek yerler"], "titles": []},
    {"key": "il", "label": "Türkiye'nin İlleri", "depth": 0, "search": "Türkiye'nin illeri",
     "cats": ["Türkiye'nin illeri", "Türkiye illeri"], "titles": []},
    {"key": "ilce", "label": "Türkiye'nin İlçeleri", "depth": 2, "search": "Türkiye'nin ilçeleri",
     "cats": ["Türkiye'nin ilçeleri", "Türkiye ilçeleri"], "titles": []},
]
SKIP_TITLE = re.compile(r"^(liste|kategori|şablon|vikipedi|portal|yardım)\b|\blistesi$|\bkategorisi$", re.I)
STOP_SECTIONS = {
    "kaynakça", "dış bağlantılar", "notlar", "dipnotlar", "ayrıca bakınız", "kaynaklar", "konuyla ilgili yayınlar",
    "harici bağlantılar", "bibliyografya", "daha fazla okuma", "ek okumalar", "sonnotlar", "referanslar",
    "dış kaynaklar", "notlar ve kaynaklar", "dipnot ve kaynaklar", "kaynakça ve notlar", "dış bağlantılar ve kaynaklar",
}
NOISE_CLASSES = {
    "reference", "references", "reflist", "refbegin", "mw-references-wrap", "mw-editsection", "navbox", "navbox-inner",
    "navbox-styles", "vertical-navbox", "sidebar", "hatnote", "dablink", "rellink", "ambox", "metadata", "noprint", "toc",
    "mw-empty-elt", "sistersitebox", "sister-box", "portal", "mw-authority-control", "printfooter", "catlinks", "magnify",
    "mw-cite-backlink", "shortdescription", "navigation-not-searchable", "mbox-small", "mw-jump-link", "commonscat",
    "stub", "cs1-hidden-error", "error", "mw-collapsible-toggle", "listen", "mw-kartographer-container",
}
NOISE_TAGS = {"style", "script", "link", "meta", "noscript", "template", "form", "input", "button", "audio", "video"}
INLINE_KEEP = {"b", "strong", "i", "em", "u", "s", "sub", "sup", "small", "abbr", "code", "cite", "q", "mark"}
BLOCK_LIST = {"ul", "ol", "dl"}
ATTRIBUTION_URL = "https://creativecommons.org/licenses/by-sa/4.0/deed.tr"

esc = html.escape
_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def xml_clean(s):
    return _BAD_XML.sub("", s or "")


def collapse(s):
    return " ".join((s or "").replace("\xa0", " ").split())


# ----------------------------------------------------------------------------- MediaWiki istemcisi
class WikiError(RuntimeError):
    pass


class WikiMissing(WikiError):
    """Madde yok / geçersiz başlık (API hatası değil; kalıcı atlanır)."""


def _transport(params):
    data = urllib.parse.urlencode(params)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Encoding": "gzip"}
    if len(data) > 1800:                              # uzun URL (çok sayıda dosya adı) -> POST
        req = urllib.request.Request(f"{WIKI_HOST}/w/api.php", data=data.encode("utf-8"),
                                     headers={**headers, "Content-Type": "application/x-www-form-urlencoded"})
    else:
        req = urllib.request.Request(f"{WIKI_HOST}/w/api.php?{data}", headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


class Api:
    def __init__(self, transport=None, sleep=time.sleep, min_interval=0.25, retries=5):
        self.transport, self.sleep, self.min_interval, self.retries = transport or _transport, sleep, min_interval, retries
        self._last, self.calls = 0.0, 0

    def _throttle(self):
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            self.sleep(wait)
        self._last = time.monotonic()

    def _backoff(self, attempt, retry_after=None):
        try:
            delay = min(60.0, float(retry_after))
        except (TypeError, ValueError):
            delay = min(60.0, 2 ** attempt + random.random())
        self.sleep(delay)

    def request(self, params):
        p = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
        last = None
        for attempt in range(self.retries):
            self._throttle()
            self.calls += 1
            try:
                data = self.transport(p)
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (429, 500, 502, 503, 504):
                    self._backoff(attempt, e.headers.get("Retry-After") if e.headers else None)
                    continue
                raise WikiError(f"HTTP {e.code}") from e
            except (OSError, http.client.HTTPException, EOFError, zlib.error, ValueError) as e:
                last = e
                self._backoff(attempt)
                continue
            err = data.get("error") if isinstance(data, dict) else None
            if err:
                if err.get("code") in ("maxlag", "ratelimited"):
                    last = WikiError(err.get("code"))
                    self._backoff(attempt)
                    continue
                if err.get("code") in ("missingtitle", "invalidtitle", "nosuchpageid"):
                    raise WikiMissing(f"{err.get('code')}: {err.get('info')}")
                raise WikiError(f"{err.get('code')}: {err.get('info')}")
            return data
        raise WikiError(f"API yanıt vermedi: {last}")

    def category_members(self, cat):
        """-> (sayfalar[ns0], altkategoriler) ; kategori yoksa (None, None)."""
        pages, subs, cont = [], [], {}
        title = cat if cat.startswith("Kategori:") else f"Kategori:{cat}"
        for _ in range(60):
            data = self.request({"action": "query", "list": "categorymembers", "cmtitle": title,
                                 "cmtype": "page|subcat", "cmlimit": "500", **cont})
            for m in data.get("query", {}).get("categorymembers", []):
                (pages if m.get("ns") == 0 else subs if m.get("ns") == 14 else []).append(m["title"])
            if "continue" not in data:
                break
            cont = data["continue"]
        return pages, subs

    def existing_titles(self, titles):
        """İstenen başlıklardan Vikipedi'de gerçekten var olanlar (yönlendirmeler çözülür)."""
        ok = set()
        titles = list(dict.fromkeys(titles))
        for i in range(0, len(titles), 40):
            batch = titles[i:i + 40]
            q = self.request({"action": "query", "titles": "|".join(batch), "redirects": "1"}).get("query", {})
            norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
            red = {r["from"]: r["to"] for r in q.get("redirects", [])}
            alive = {pg["title"] for pg in q.get("pages", []) if not pg.get("missing") and not pg.get("invalid")}
            for t in batch:
                f = norm.get(t, t)
                if red.get(f, f) in alive:
                    ok.add(t)
        return ok

    def search_categories(self, term, limit=5):
        data = self.request({"action": "query", "list": "search", "srsearch": term, "srnamespace": "14",
                             "srlimit": str(limit)})
        return [x["title"] for x in data.get("query", {}).get("search", [])]

    def parse(self, title):
        data = self.request({"action": "parse", "page": title, "redirects": "1", "prop": "text|revid|properties|displaytitle",
                             "disableeditsection": "1", "disablelimitreport": "1", "disabletoc": "1",
                             "wrapoutputclass": "mw-parser-output"})
        if "parse" not in data:
            raise WikiError(f"parse boş: {title}")
        return data["parse"]

    def coordinates(self, title):
        data = self.request({"action": "query", "prop": "coordinates", "titles": title, "coprimary": "primary",
                             "colimit": "1", "redirects": "1"})
        pg = (data.get("query", {}).get("pages") or [{}])[0]
        c = (pg.get("coordinates") or [None])[0]
        return (c["lat"], c["lon"]) if c and "lat" in c and "lon" in c else None

    def image_info(self, names):
        """dosya adları -> {anahtar: bilgi}; anahtar = fkey(ad)."""
        out = {}
        names = list(dict.fromkeys(names))
        for i in range(0, len(names), 40):
            batch = names[i:i + 40]
            data = self.request({"action": "query", "prop": "imageinfo", "titles": "|".join("Dosya:" + n for n in batch),
                                 "iiprop": "url|size|mime", "iiurlwidth": str(IMG_WIDTH), "redirects": "1",
                                 "iiextmetadatafilter": "Artist|Credit|LicenseShortName|LicenseUrl|NonFree|Copyrighted|UsageTerms",
                                 "iiextmetadatalanguage": WIKI})
            q = data.get("query", {})
            redir = {fkey(r["from"].split(":", 1)[-1]): fkey(r["to"].split(":", 1)[-1]) for r in q.get("redirects", [])}
            for pg in q.get("pages", []):
                ii = (pg.get("imageinfo") or [None])[0]
                if ii:
                    out[fkey(pg["title"].split(":", 1)[-1])] = ii
            for src, dst in redir.items():
                if dst in out and src not in out:
                    out[src] = out[dst]
        return out


_TR_ALPHA = "abcçdefgğhıijklmnoöprsştuüvwxyz"
_TR_ORDER = {c: i for i, c in enumerate(_TR_ALPHA)}


def tr_sort_key(title):
    t = (title or "").replace("I", "ı").replace("İ", "i").lower()
    return [(_TR_ORDER.get(c, 100 + ord(c))) for c in t]


def fkey(name):
    n = urllib.parse.unquote(name or "").replace("_", " ").strip()
    return n[:1].upper() + n[1:]


# ----------------------------------------------------------------------------- aday havuzu
def group_cats(g):
    env = os.environ.get("CATS_" + g["key"].upper())
    return [c.strip() for c in env.split("|") if c.strip()] if env else g["cats"]


def crawl_category(api, cat, depth, seen, log, first=None):
    pages, subs = first if first is not None else api.category_members(cat)
    out = list(pages)
    if depth > 0:
        for s in subs:
            name = s.split(":", 1)[-1]
            if name in seen:
                continue
            seen.add(name)
            try:
                out += crawl_category(api, name, depth - 1, seen, log)
            except WikiError as e:
                log(f"::warning::alt kategori okunamadı ({name}): {e}")
    return out


def discover(api, log=print):
    """Tüm grupların aday başlıkları + rapor."""
    groups, report = {}, {}
    for g in GROUPS:
        found, titles, notes = [], [], []
        for cat in group_cats(g):
            try:
                top = api.category_members(cat)
                if not top[0] and not top[1]:
                    notes.append(f"yok/boş: Kategori:{cat}")
                    continue
                got = crawl_category(api, cat, g["depth"], {cat}, log, first=top)
            except WikiError as e:
                notes.append(f"hata: Kategori:{cat}: {e}")
                continue
            found.append({"kategori": cat, "madde": len(got)})
            titles += got
        if g["titles"]:
            try:
                alive = api.existing_titles(g["titles"])
            except WikiError as e:
                alive = set(g["titles"])
                notes.append(f"hata: madde denetimi: {e}")
            gone = [t for t in g["titles"] if t not in alive]
            if gone:
                notes.append("maddesi yok: " + ", ".join(gone))
            titles += [t for t in g["titles"] if t in alive]
        titles = [t for t in dict.fromkeys(titles) if not SKIP_TITLE.search(t)]
        if not found and not g["titles"]:
            try:
                sug = api.search_categories(g["search"])
                notes.append("öneri: " + ("; ".join(sug) if sug else "bulunamadı"))
            except WikiError:
                pass
        groups[g["key"]] = sorted(titles, key=tr_sort_key)
        report[g["key"]] = {"etiket": g["label"], "bulunan": found, "not": notes, "toplam": len(groups[g["key"]]),
                            "örnek": groups[g["key"]][:5]}
        log(f"grup {g['key']:10s} aday={len(groups[g['key']]):5d} kategoriler={[f['kategori'] for f in found] or 'YOK'}"
            + (f"  {notes}" if notes else ""))
    return groups, report


# ----------------------------------------------------------------------------- HTML temizleme
def is_noise(tag):
    if not isinstance(tag, Tag):
        return False
    if tag.name in NOISE_TAGS:
        return True
    cls = set(tag.get("class") or [])
    if cls & NOISE_CLASSES:
        return True
    if tag.get("role") == "navigation" or tag.get("id") == "toc":
        return True
    style = (tag.get("style") or "").replace(" ", "").lower()
    if "display:none" in style:
        return True
    if tag.name == "sup" and (tag.get("id") or "").startswith("cite_ref"):
        return True
    return False


def abs_url(href):
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return WIKI_HOST + href
    return href


FILE_HREF = re.compile(r"/wiki/(?:Dosya|File|Resim|Image|Medya|Media):(.+)$", re.I)


def inline(node):
    """Düğümü yalnızca güvenli satır içi HTML'e çevirir (görseller atılır)."""
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return esc(str(node), quote=False)
    if not isinstance(node, Tag) or is_noise(node):
        return ""
    name = node.name
    inner = "".join(inline(c) for c in node.children)
    if name in ("img", "figure", "table", "style"):
        return ""
    if name == "br":
        return "<br />"
    if name == "a":
        href = node.get("href") or ""
        cls = set(node.get("class") or [])
        if not href or href.startswith("#") or "new" in cls or FILE_HREF.search(href) or "mw-file-description" in cls:
            return inner
        if "redlink=1" in href:
            return inner
        url = abs_url(href)
        if url.startswith(WIKI_HOST + "/wiki/") or url.startswith(WIKI_HOST + "/w/index.php"):
            return f'<a href="{esc(url)}">{inner}</a>' if inner.strip() else ""
        if url.startswith(("http://", "https://")):
            return f'<a href="{esc(url)}" rel="nofollow noopener" target="_blank">{inner}</a>' if inner.strip() else ""
        return inner
    if name in INLINE_KEEP:
        return f"<{name}>{inner}</{name}>" if inner.strip() else ""
    return inner


def plain(node):
    """Yalnızca düz metin (gürültüsüz)."""
    if isinstance(node, Comment):
        return ""
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag) or is_noise(node):
        return ""
    if node.name == "br":
        return " "
    if node.name in ("li", "dd", "dt", "p", "div", "tr"):
        return " " + "".join(plain(c) for c in node.children) + " "
    return "".join(plain(c) for c in node.children)


def cell_text(node):
    parts = []
    li = node.find_all("li") if isinstance(node, Tag) else []
    if li:
        parts = [collapse(plain(x)) for x in li]
    else:
        txt = "".join("\n" if getattr(c, "name", "") == "br" else plain(c) for c in node.children)
        parts = [collapse(x) for x in txt.split("\n")]
    parts = [p for p in parts if p and not re.fullmatch(r"[\W_]*", p)]
    return ", ".join(dict.fromkeys(parts))


def file_of(img):
    """<img> -> Dosya adı (boşluklu, ilk harf büyük)."""
    a = img.find_parent("a")
    href = (a.get("href") if a else "") or ""
    m = FILE_HREF.search(urllib.parse.unquote(href))
    if m:
        return fkey(m.group(1).split("#")[0])
    src = img.get("src") or ""
    parts = [p for p in urllib.parse.urlparse(src).path.split("/") if p]
    if "thumb" in parts:
        i = parts.index("thumb")
        return fkey(parts[i + 3]) if len(parts) > i + 3 else None
    return fkey(parts[-1]) if parts else None


def caption_html(cap):
    if cap is None:
        return ""
    for bad in cap.find_all(class_="magnify"):
        bad.decompose()
    return inline(cap).strip()


def figure_units(block):
    """Bir blok içindeki görselleri [(dosya, başlık_html)] olarak döndürür."""
    units, classes = [], set(block.get("class") or [])

    def add(img, cap):
        f = file_of(img) if img is not None else None
        if f:
            units.append((f, caption_html(cap)))

    if block.name == "figure":
        add(block.find("img"), block.find("figcaption"))
    elif "gallery" in classes or block.name == "ul" and block.find(class_="gallerybox"):
        for li in block.find_all(class_="gallerybox"):
            add(li.find("img"), li.find(class_="gallerytext"))
    elif "tmulti" in classes:
        singles = block.find_all(class_="tsingle")
        overall = None
        for c in block.find_all(class_="thumbcaption"):
            if not c.find_parent(class_="tsingle"):
                overall = c
        for i, ts in enumerate(singles):
            cap = ts.find(class_="thumbcaption")
            add(ts.find("img"), cap if cap is not None else (overall if i == len(singles) - 1 else None))
    else:
        cap = block.find("figcaption") or block.find(class_="thumbcaption")
        imgs = block.find_all("img")
        for i, img in enumerate(imgs):
            add(img, cap if i == len(imgs) - 1 else None)
    return units


def img_width(img):
    try:
        return int(img.get("width") or 0)
    except ValueError:
        return 0


def is_figure_block(tag):
    cls = set(tag.get("class") or [])
    if tag.name == "figure" or cls & {"thumb", "tmulti", "gallery"}:
        return bool(tag.find("img"))
    if cls & {"floatright", "floatleft", "floatnone", "tright", "tleft"}:
        return bool(tag.find("img")) and len(plain(tag)) < 600
    return tag.name == "ul" and bool(tag.find(class_="gallerybox"))


def list_html(tag):
    name = tag.name
    items = []
    for li in tag.find_all(["li", "dt", "dd"], recursive=False):
        if is_noise(li):
            continue
        parts = []
        for ch in li.children:
            parts.append(list_html(ch) if isinstance(ch, Tag) and ch.name in BLOCK_LIST else inline(ch))
        body = "".join(parts).strip()
        if re.sub(r"<[^>]+>|\s|&nbsp;", "", body):
            items.append(f"<{li.name}>{body}</{li.name}>")
    return f"<{name}>{''.join(items)}</{name}>" if items else ""


def table_html(tag):
    rows = []
    for tr in tag.find_all("tr")[:MAX_TABLE_ROWS]:
        if is_noise(tr) or tr.find_parent("table") is not tag:
            continue
        cells = []
        for c in tr.find_all(["th", "td"], recursive=False):
            if is_noise(c):
                continue
            body = inline(c).strip()
            attrs = ""
            for a in ("colspan", "rowspan"):
                v = (c.get(a) or "").strip()
                if v.isdigit() and 1 < int(v) <= 50:
                    attrs += f' {a}="{int(v)}"'
            style = "border: 1px solid #ccc; padding: 4px 8px; vertical-align: top;"
            if c.name == "th":
                style += " background: #f2f2f2; font-weight: bold;"
            cells.append(f'<{c.name}{attrs} style="{style}">{body}</{c.name}>')
        if cells:
            rows.append("<tr>" + "".join(cells) + "</tr>")
    if not rows or not re.sub(r"<[^>]+>|\s|&nbsp;", "", "".join(rows)):
        return ""
    cap = tag.find("caption")
    cap_html = f"<caption>{inline(cap).strip()}</caption>" if cap is not None and inline(cap).strip() else ""
    return ('<div style="overflow-x: auto;"><table style="border-collapse: collapse; width: 100%; margin: 1em 0;">'
            f'{cap_html}{"".join(rows)}</table></div>')


def infobox_rows(tag, title=""):
    """Bilgi kutusundan [(etiket|None, değer)] ve görsel birimleri."""
    rows, units = [], []
    for tr in tag.find_all("tr"):
        if is_noise(tr) or tr.find_parent("table") is not tag:
            continue
        ths, tds = tr.find_all("th", recursive=False), tr.find_all("td", recursive=False)
        if tr.find("img") and not (ths and tds):
            u = figure_units(tr)
            note = collapse(plain(tds[0])) if tds else ""
            if u and note and not u[-1][1]:
                u[-1] = (u[-1][0], esc(note, quote=False))
            units += u
        elif ths and tds:
            label, val = collapse(plain(ths[0])), cell_text(tds[0])
            if label and val:
                rows.append((label, val))
        elif len(ths) == 1 and not tds:
            head = collapse(plain(ths[0]))
            above = {"infobox-above", "infobox-title", "fn", "org"} & set(ths[0].get("class") or [])
            if head and len(head) < 80 and not above and head.casefold() != collapse(title).casefold():
                rows.append((None, head))                       # bölüm başlığı (madde başlığını tekrarlama)
        elif len(tds) == 2:
            label, val = collapse(plain(tds[0])), cell_text(tds[1])
            if label and val:
                rows.append((label, val))
    return rows, units, ""


MAIN_PREFIX = re.compile(r"^(ana madde|ana maddeler|ayrıntılı bilgi için|daha fazla bilgi için|ayrıntılar için)\b", re.I)


def wiki_link_titles(el):
    out = []
    for a in el.find_all("a", href=True):
        if "new" in (a.get("class") or []):
            continue
        m = re.match(r"^(?:https?:)?(?://tr\.wikipedia\.org)?/wiki/([^#?]+)", a["href"])
        if not m:
            continue
        t = urllib.parse.unquote(m.group(1)).replace("_", " ").strip()
        if t and ":" not in t and not SKIP_TITLE.search(t) and t not in out:
            out.append(t)
    return out


def sanitize(parse_html, title):
    """Maddeyi (blok listesi, künye satırları, görsel dosyaları) olarak ayrıştırır.

    blok: ("h", seviye, metin) | ("html", str) | ("fig", dosya, başlık_html)
    """
    soup = BeautifulSoup(parse_html, "html.parser")
    root = soup.find(class_="mw-parser-output") or soup
    blocks, info_rows, info_units = [], [], []
    state = {"skip": None}

    def add_figs(units):
        for f, cap in units:
            blocks.append(("fig", f, cap))

    def handle(el):
        if isinstance(el, Tag) and state["skip"] is None and set(el.get("class") or []) & {"hatnote", "dablink", "rellink", "mainarticle"}:
            if MAIN_PREFIX.match(collapse("".join(plain(c) for c in el.children))):
                titles = wiki_link_titles(el)
                if titles:
                    blocks.append(("main", titles))                   # "Ana madde: ..." -> ayrıntılı madde
            return
        if isinstance(el, (NavigableString, Comment)) or is_noise(el):
            return
        name = el.name
        if re.fullmatch(r"h[1-6]", name or ""):
            level = max(2, min(int(name[1]), 4))
            text = collapse(plain(el))
            if state["skip"] is not None and level <= state["skip"]:
                state["skip"] = None
            if text.lower() in STOP_SECTIONS:
                state["skip"] = level
                return
            if state["skip"] is None and text:
                blocks.append(("h", level, text))
            return
        if state["skip"] is not None:
            if name == "div" and "mw-heading" in (el.get("class") or []):
                for ch in el.children:
                    handle(ch)
            return
        cls = set(el.get("class") or [])
        if name == "table" and ("infobox" in " ".join(cls) or "vcard" in cls):
            rows, units, _ = infobox_rows(el, title)
            info_rows.extend(rows)
            info_units.extend(units)
            return
        if is_figure_block(el):
            add_figs(figure_units(el))
            return
        if name == "p":
            imgs = [i for i in el.find_all("img") if img_width(i) >= 150]
            body = inline(el).strip()
            if re.sub(r"<[^>]+>|\s|&nbsp;", "", body):
                blocks.append(("html", f"<p>{body}</p>"))
            for i in imgs:
                f = file_of(i)
                if f:
                    blocks.append(("fig", f, ""))
            return
        if name in BLOCK_LIST:
            out = list_html(el)
            if out:
                blocks.append(("html", out))
            return
        if name == "blockquote":
            body = inline(el).strip()
            if body:
                blocks.append(("html", f"<blockquote>{body}</blockquote>"))
            return
        if name == "table":
            if el.find("img") and not el.find(class_="wikitable") and "wikitable" not in cls and len(plain(el)) < 400:
                add_figs([(file_of(i), "") for i in el.find_all("img") if file_of(i)])
                return
            out = table_html(el)
            if out:
                blocks.append(("html", out))
            return
        if name in ("div", "section", "span", "center", "a") and el.find("img") and len(plain(el)) < 200 \
                and not el.find(["p", "table", "ul", "ol", "h2", "h3", "h4"]):
            add_figs(figure_units(el))                       # yalnızca görsel (+ kısa alt yazı) taşıyan kapsayıcı
            return
        if name in ("div", "section", "span", "center", "main", "article", "body", "html", "[document]"):
            for ch in list(el.children):
                handle(ch)

    for ch in list(root.children):
        handle(ch)
    return blocks, info_rows, info_units


# ----------------------------------------------------------------------------- görseller
def accept_image(info):
    meta = info.get("extmetadata") or {}

    def val(k):
        return str((meta.get(k) or {}).get("value", "")).strip()

    lic = val("LicenseShortName")
    if not lic or val("NonFree").lower() in ("true", "1", "yes"):
        return False
    if re.search(r"fair use|non-?free|all rights reserved|telif", lic, re.I):
        return False
    mime = info.get("mime") or ""
    if not mime.startswith("image/") or mime in ("image/vnd.djvu",):
        return False
    return int(info.get("width") or 0) >= MIN_IMG_W


def strip_tags(s):
    s = re.sub(r"</?(?:p|li|ul|ol|dl|dt|dd|div|tr|td|th|table|br|h[1-6]|figure|figcaption|blockquote)\b[^>]*>", " ", s or "")
    return collapse(html.unescape(re.sub(r"<[^>]+>", "", s)))


def credit_html(info):
    meta = info.get("extmetadata") or {}

    def val(k):
        return str((meta.get(k) or {}).get("value", "")).strip()

    who = strip_tags(val("Artist")) or strip_tags(val("Credit")) or "Wikimedia katkıcıları"
    who = who[:140]
    lic, lurl = val("LicenseShortName"), val("LicenseUrl")
    parts = [f"Görsel: {esc(who)}"]
    parts.append(f'<a href="{esc(lurl)}" rel="noopener" target="_blank">{esc(lic)}</a>' if lurl.startswith("http") else esc(lic))
    if info.get("descriptionurl"):
        parts.append(f'<a href="{esc(info["descriptionurl"])}" rel="noopener" target="_blank">Kaynak</a>')
    return "<small>" + " · ".join(parts) + "</small>"


_NOT_LEAD = re.compile(r"bayrak|flag|logo|\barma\b|amblem|coat|seal|harita|\bmap\b|locator|konum|location|simge|icon|sembol|blason",
                       re.I)


def lead_ok(name, info):
    w, h = int(info.get("width") or 0), int(info.get("height") or 1)
    return not _NOT_LEAD.search(name) and info.get("mime") != "image/svg+xml" and 0.5 <= w / max(h, 1) <= 2.5


def figure_html(name, cap_html, info, alt):
    url = info.get("thumburl") or info.get("url")
    w = info.get("thumbwidth") or info.get("width")
    h = info.get("thumbheight") or info.get("height")
    dims = f' width="{int(w)}" height="{int(h)}"' if w and h else ""
    cap = (cap_html + "<br />" if cap_html else "") + credit_html(info)
    return ('<figure style="margin: 1em 0; text-align: center;">'
            f'<a href="{esc(info.get("url") or url)}" rel="noopener" target="_blank">'
            f'<img alt="{esc(alt)}" loading="lazy" src="{esc(url)}"{dims} style="max-width: 100%; height: auto;" /></a>'
            f'<figcaption style="font-size: 90%;">{cap}</figcaption></figure>')


# ----------------------------------------------------------------------------- makale
def wiki_url(title):
    return f"{WIKI_HOST}/wiki/{urllib.parse.quote(title.replace(' ', '_'), safe=':,()_-')}"


def oldid_url(title, revid):
    if not revid:
        return wiki_url(title)
    return f"{WIKI_HOST}/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&oldid={revid}"


def history_url(title):
    return f"{WIKI_HOST}/w/index.php?title={urllib.parse.quote(title.replace(' ', '_'))}&action=history"


def tr_lower(s):
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def display_name(title):
    return re.sub(r"\s*\((?:il|ilçe|şehir|belde|belediye|kasaba)\)$", "", title or "", flags=re.I).strip()


def feed_title(group, name, rows):
    name = display_name(name)
    if group == "il":
        t = f"{name} İli: Tarih, Coğrafya, Nüfus ve Kültür"
    elif group == "ilce":
        il = next((v for k, v in rows if k and tr_lower(k) in ("il", "ili", "bağlı olduğu il", "bulunduğu il")), "")
        t = (f"{name} ({il}) İlçesi" if il else f"{name} İlçesi") + ": Tarih, Coğrafya, Nüfus ve Kültür"
    else:
        t = name
    return t if len(t) <= 120 else name


def block_chars(blocks):
    return sum(len(strip_tags(b[1])) for b in blocks if b[0] == "html")


def page_props(parsed):
    raw = parsed.get("properties") or {}
    return set(raw) if isinstance(raw, dict) else {p.get("name") for p in raw if isinstance(p, dict)}


def parsed_title(parsed, fallback):
    t = html.unescape(collapse(re.sub(r"<[^>]+>", "", parsed.get("displaytitle") or "")))
    return t or parsed.get("title") or fallback


def fetch_sub(api, title, level, ctx, log):
    """'Ana madde' bağlantısındaki maddeyi blok listesi olarak getirir; uygun değilse None."""
    if title.casefold() in ctx["seen"] or len(ctx["sources"]) >= MAX_SUB or ctx["chars"] >= TOTAL_MAX_CHARS:
        return None
    ctx["seen"].add(title.casefold())
    try:
        parsed = api.parse(title)
    except WikiMissing:
        return None
    except WikiError as e:
        log(f"::warning::ayrıntılı madde alınamadı ({title}): {e}")
        return None
    wiki_title = parsed.get("title") or title
    redirected_to_seen = wiki_title.casefold() != title.casefold() and wiki_title.casefold() in ctx["seen"]
    if "disambiguation" in page_props(parsed) or redirected_to_seen:
        return None
    ctx["seen"].add(wiki_title.casefold())
    real = parsed_title(parsed, wiki_title)
    sub, _rows, units = sanitize(parsed.get("text") or "", real)
    sub = [b for b in sub if b[0] != "main"]                      # iç içe takip yok
    if block_chars(sub) < SUB_MIN_CHARS:
        return None
    top = min(4, level + 1)
    out = [("h", top, real),
           ("html", f'<p><i>Ayrıntılı madde: <a href="{esc(wiki_url(wiki_title))}" rel="noopener" target="_blank">'
                    f"{esc(real)}</a></i></p>")]
    out += [("fig", f, cap) for f, cap in units[:3]]
    used = 0
    for b in sub:
        if b[0] == "h":
            if used > SUB_MAX_CHARS:
                break
            out.append(("h", min(4, level + b[1]), b[2]))
            continue
        if b[0] == "html":
            if used > SUB_MAX_CHARS * 1.5:              # bütçe aşıldı: ilk blok her zaman girer, sonrası kesilir
                break
            used += len(strip_tags(b[1]))
        out.append(b)
    ctx["chars"] += used
    ctx["sources"].append({"title": wiki_title, "name": real, "oldid": oldid_url(wiki_title, parsed.get("revid"))})
    return out


def expand_main(api, blocks, self_titles, log):
    """'Ana madde: X' dipnotu olan bölümün sonuna X maddesinin tam metnini ekler. -> (bloklar, kaynaklar)"""
    ctx = {"seen": {t.casefold() for t in self_titles}, "sources": [], "chars": block_chars(blocks)}
    out, pending, cur = [], [], 2

    def flush(min_level):
        keep = []
        for lvl, titles in pending:
            if lvl >= min_level:
                for t in titles:
                    sub = fetch_sub(api, t, lvl, ctx, log)
                    if sub:
                        out.extend(sub)
            else:
                keep.append((lvl, titles))
        pending[:] = keep

    for b in blocks:
        if b[0] == "h":
            flush(b[1])
            cur = b[1]
            out.append(b)
        elif b[0] == "main":
            pending.append((cur, b[1]))
        else:
            out.append(b)
    flush(0)
    return out, ctx["sources"]


def build_article(api, title, group, now, log=print):
    """-> (rec, body) ya da (None, neden)."""
    parsed = api.parse(title)
    if "disambiguation" in page_props(parsed):
        return None, "anlam_ayrimi"
    wiki_title = parsed.get("title") or title
    real_title = parsed_title(parsed, wiki_title)
    pageid, revid = parsed.get("pageid"), parsed.get("revid")
    if not pageid:
        return None, "sayfa_yok"
    blocks, rows, info_units = sanitize(parsed.get("text") or "", real_title)
    if block_chars(blocks) < MIN_TEXT_CHARS:
        return None, "taslak"
    sources = []
    if FOLLOW_MAIN:
        blocks, sources = expand_main(api, blocks, {wiki_title, real_title, title}, log)

    files = [u[0] for u in info_units] + [b[1] for b in blocks if b[0] == "fig"]
    infos = api.image_info(files[: MAX_IMAGES * 2]) if files else {}
    used, count = set(), 0

    def render_fig(f, cap, alt):
        nonlocal count
        k = fkey(f)
        info = infos.get(k)
        if not info or k in used or count >= MAX_IMAGES or not accept_image(info):
            return None
        used.add(k)
        count += 1
        return info, figure_html(f, cap, info, alt or real_title)

    # kapak görseli: fotoğraf benzeri ilk görsel (bayrak/logo/harita değil); yoksa ilk geçerli görsel
    lead, lead_info = "", None
    cands = list(info_units) + [(b[1], b[2]) for b in blocks if b[0] == "fig"]
    valid = [(f, cap) for f, cap in cands if infos.get(fkey(f)) and accept_image(infos[fkey(f)])]
    pick = next(((f, cap) for f, cap in valid if lead_ok(f, infos[fkey(f)])), valid[0] if valid else None)
    if pick:
        r = render_fig(pick[0], pick[1], real_title)
        if r:
            lead_info, lead = r

    first_h = next((i for i, b in enumerate(blocks) if b[0] == "h"), len(blocks))
    t = esc(real_title)
    out = [("t", lead)] if lead else []

    def emit(items):
        for b in items:
            if b[0] == "h":
                out.append(("h", b[1], f"<h{b[1]}>{esc(b[2])}</h{b[1]}>"))
            elif b[0] == "html":
                out.append(("t", b[1]))
            elif b[0] == "fig":
                r = render_fig(b[1], b[2], strip_tags(b[2]))
                if r:
                    out.append(("t", r[1]))

    emit(blocks[:first_h])

    # künye (bilgi kutusu)
    coords = api.coordinates(wiki_title)
    lines = []
    for label, val in rows:
        lines.append(f"<b>— {esc(val)} —</b>" if label is None else f"<b>{esc(label)}:</b> {esc(val)}")
    if coords:
        lat, lon = coords
        lines.append(f'<b>Koordinatlar:</b> {lat:.5f}, {lon:.5f} (<a href="https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}'
                     f'#map=12/{lat}/{lon}" rel="noopener" target="_blank">haritada aç</a>)')
    if lines:
        out.append(("h", 2, f"<h2>{t} Künyesi</h2>"))
        out.append(("t", "<p>" + "<br />".join(lines) + "</p>"))
    extra_heading = bool(lines)
    for f, cap in info_units:                                   # bilgi kutusundaki diğer görseller (bayrak, harita, logo...)
        r = render_fig(f, cap, strip_tags(cap) or real_title)
        if r:
            if not extra_heading:
                out.append(("h", 2, f"<h2>{t} Görselleri</h2>"))
                extra_heading = True
            out.append(("t", r[1]))

    emit(blocks[first_h:])

    # boş başlıkları ayıkla
    final, items = [], out
    for i, it in enumerate(items):
        if it[0] == "h":
            lvl, j, has = it[1], i + 1, False
            while j < len(items):
                if items[j][0] == "h" and items[j][1] <= lvl:
                    break
                if items[j][0] == "t":
                    has = True
                    break
                j += 1
            if not has:
                continue
            final.append(it[2])
        else:
            final.append(it[1])

    link = wiki_url(wiki_title)
    note = ("<hr />"
            f'<p><small>Bu makale Vikipedi\'deki <a href="{esc(link)}" rel="noopener" target="_blank">“{t}”</a> maddesinden '
            f'alınmıştır (<a href="{esc(oldid_url(wiki_title, revid))}" rel="noopener" target="_blank">kullanılan sürüm</a>). '
            f'Madde metni <a href="{ATTRIBUTION_URL}" rel="noopener" target="_blank">Creative Commons '
            f'Atıf-AynıLisanslaPaylaş 4.0</a> lisansı altındadır; yazarlar için '
            f'<a href="{esc(history_url(wiki_title))}" rel="noopener" target="_blank">sürüm geçmişine</a> bakın. '
            "Metin bu sayfaya uygun biçimde düzenlenmiştir. Görsellerin yazar ve lisans bilgileri her görselin altındadır.")
    if sources:
        note += (" Bu makale ayrıca aynı lisansla şu Vikipedi maddelerinden alınan bölümleri içerir: "
                 + ", ".join(f'<a href="{esc(x["oldid"])}" rel="noopener" target="_blank">{esc(x["name"])}</a>' for x in sources) + ".")
    final.append(note + "</small></p>")
    body = "\n".join(final) + "\n"

    lead_p = next((b[1] for b in blocks if b[0] == "html" and b[1].startswith("<p>")), "")
    desc = shorten(strip_tags(lead_p) or real_title)
    stamp = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    gdef = next(g for g in GROUPS if g["key"] == group)
    rec = {
        "id": f"yer-{pageid}", "pageid": pageid, "title": feed_title(group, real_title, rows), "wiki_title": wiki_title,
        "group": group, "v": BUILD_VERSION, "pub": stamp(now), "date": now.strftime("%Y-%m-%d"), "revid": revid,
        "link": link, "description": desc, "categories": [gdef["label"], "Vikipedi"],
        "image": ({"url": lead_info.get("thumburl") or lead_info.get("url"),
                   "width": int(lead_info.get("thumbwidth") or lead_info.get("width") or 0),
                   "height": int(lead_info.get("thumbheight") or lead_info.get("height") or 0)} if lead_info else None),
        "images": count, "subs": len(sources), "content_file": f"data/content/{pageid}.html",
    }
    return rec, body


def shorten(text, limit=155):
    t = collapse(text)
    if len(t) <= limit:
        return t
    return t[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-–—") + "…"


# ----------------------------------------------------------------------------- RSS
def _dt(iso):
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def rfc822(dt):
    return format_datetime(dt.astimezone(timezone.utc), usegmt=False).replace("-0000", "+0000")


def cdata(s):
    return "<![CDATA[" + xml_clean(s).replace("]]>", "]]]]><![CDATA[>") + "]]>"


def item_xml(r, body):
    cats = "".join(f"      <category>{escape(xml_clean(c))}</category>\n" for c in r["categories"])
    img = r.get("image")
    media = (f"      <media:content url={quoteattr(img['url'])} medium=\"image\""
             + (f" width=\"{img['width']}\" height=\"{img['height']}\"" if img.get("width") else "") + " />\n") if img else ""
    return ("    <item>\n"
            f"      <title>{escape(xml_clean(r['title']))}</title>\n"
            f"      <link>{escape(r['link'])}</link>\n"
            f"      <guid isPermaLink=\"false\">{escape(r['id'])}</guid>\n"
            f"      <pubDate>{rfc822(_dt(r['pub']))}</pubDate>\n"
            "      <dc:creator>Vikipedi katkıcıları</dc:creator>\n"
            f"{cats}"
            f"      <description>{escape(xml_clean(r['description']))}</description>\n"
            f"{media}"
            f"      <content:encoded>{cdata(body)}</content:encoded>\n"
            "    </item>\n")


def build_rss(items_xml, now):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:media="http://search.yahoo.com/mrss/">\n  <channel>\n'
            f"    <title>{escape(SITE_TITLE)}</title>\n    <link>{escape(SITE_URL)}/</link>\n"
            f"    <description>{escape(SITE_DESC)}</description>\n    <language>tr</language>\n"
            f"    <copyright>{escape(COPYRIGHT)}</copyright>\n"
            f"    <lastBuildDate>{rfc822(now)}</lastBuildDate>\n    <ttl>720</ttl>\n"
            "    <generator>yerlerrss (GitHub Actions, Vikipedi)</generator>\n"
            f'    <atom:link href="{escape(SITE_URL)}/rss.xml" rel="self" type="application/rss+xml" />\n'
            + "".join(items_xml) + "  </channel>\n</rss>\n")


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def write_feed(root, articles, now, log=print):
    ordered = sorted(articles, key=lambda a: (a["pub"], a["id"]), reverse=True)
    latest = ordered[:FEED_ITEMS] if FEED_ITEMS > 0 else ordered
    items, size, limit = [], 0, FEED_MAX_MB * 1024 * 1024
    for r in latest:
        try:
            with open(os.path.join(root, r["content_file"]), encoding="utf-8") as f:
                body = f.read()
        except OSError:
            log(f"::warning::içerik dosyası eksik, RSS'e eklenmedi: {r['content_file']}")
            continue
        x = item_xml(r, body)
        if items and limit and size + len(x.encode("utf-8")) > limit:
            log(f"::notice::rss.xml boyut sınırı ({FEED_MAX_MB} MB): daha eski öğeler çıkarıldı")
            break
        items.append(x)
        size += len(x.encode("utf-8"))
    if not items:
        log("::warning::RSS'e eklenecek içerik yok; rss.xml yazılmadı")
        return 0
    write_text(os.path.join(root, "rss.xml"), build_rss(items, now))
    return len(items)


# ----------------------------------------------------------------------------- kalıcı kayıt
class StoreError(RuntimeError):
    pass


def _path(root, name):
    return os.path.join(root, "data", name)


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def store_load(root, log=print):
    p = _path(root, "index.json")
    for cand in (p, p + ".bak"):
        if os.path.exists(cand):
            try:
                d = _read_json(cand)
                if not (isinstance(d, dict) and isinstance(d.get("articles"), list)):
                    raise ValueError
                if cand != p:
                    log("::warning::index.json okunamadı, .bak yedeğinden devam ediliyor")
                if not isinstance(d.get("skips"), dict):
                    d["skips"] = {}
                return d
            except (OSError, ValueError):
                continue
    if os.path.exists(p) or os.path.exists(p + ".bak"):
        raise StoreError("data/index.json bozuk ve yedek okunamadı")
    return {"version": 1, "articles": [], "skips": {}}


def store_save(root, data, backup=True):
    p = _path(root, "index.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if backup and os.path.exists(p):
        try:
            _read_json(p)
            shutil.copyfile(p, p + ".bak")
        except (OSError, ValueError):
            pass
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def pool_load(root, now, force=False):
    p = _path(root, "pool.json")
    try:
        d = _read_json(p)
        built = datetime.strptime(d["built"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if not force and now - built < timedelta(days=POOL_TTL_DAYS) and any(d.get("groups", {}).values()):
            return d
    except (OSError, ValueError, KeyError):
        pass
    return None


# ----------------------------------------------------------------------------- akış
def select(pool, known_titles, skips, cap):
    """Gruplar arasında sırayla (round-robin) yeni aday seçer."""
    queues = []
    for g in GROUPS:
        q = [t for t in pool["groups"].get(g["key"], [])
             if t.casefold() not in known_titles and skips.get(t, {}).get("n", 0) < MAX_SKIP_ATTEMPTS]
        queues.append([(t, g["key"]) for t in q])
    out = []
    while any(queues) and (not cap or len(out) < cap):
        for q in queues:
            if q and (not cap or len(out) < cap):
                out.append(q.pop(0))
    return out


def run(root=None, api=None, now=None, limit=None, force_pool=False, log=print):
    root = root or SITE_ROOT
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    api = api or Api()
    data = store_load(root, log)
    arts, skips = data["articles"], data["skips"]
    known_ids = {a["pageid"] for a in arts}
    known_titles = {a["wiki_title"].casefold() for a in arts} | {a["title"].casefold() for a in arts}

    pool = pool_load(root, now, force_pool)
    errors = []
    if pool is None:
        try:
            groups, report = discover(api, log)
            pool = {"built": now.strftime("%Y-%m-%d"), "groups": groups, "report": report}
            if any(groups.values()):
                write_text(_path(root, "pool.json"), json.dumps(pool, ensure_ascii=False))
        except WikiError as e:
            errors.append(str(e))
            log(f"::warning::aday havuzu çıkarılamadı: {e}")
            pool = {"built": "", "groups": {}, "report": {}}
    todo = select(pool, known_titles, skips, PER_RUN if limit is None else limit)
    log(f"aday havuzu: {sum(len(v) for v in pool['groups'].values())} | yayımlanmış: {len(arts)} | işlenecek: {len(todo)}")

    new, streak, first = [], 0, True
    for title, group in todo:
        try:
            rec, extra = build_article(api, title, group, now + timedelta(seconds=len(new)), log)
        except WikiMissing as e:
            skips[title] = {"n": 99, "r": "yok"}
            log(f"- madde bulunamadı: {title}")
            continue
        except WikiError as e:
            log(f"::warning::madde alınamadı ({title}): {e}")
            errors.append(str(e))
            streak += 1
            if streak >= 5:
                log("::warning::ardışık API hatası: üretim durduruldu, kalanlar sonraki çalışmada işlenecek")
                break
            continue
        except Exception as e:                        # beklenmeyen biçim: tek madde tüm üretimi durdurmasın
            log(f"::warning::madde işlenemedi ({title}): {type(e).__name__}: {e}")
            skips[title] = {"n": skips.get(title, {}).get("n", 0) + 1, "r": "hata"}
            continue
        streak = 0
        if rec is None:
            skips[title] = {"n": 99 if extra == "anlam_ayrimi" else skips.get(title, {}).get("n", 0) + 1, "r": extra}
            log(f"- atlandı ({extra}): {title}")
            continue
        if rec["pageid"] in known_ids:
            skips[title] = {"n": 99, "r": "tekrar"}
            log(f"- zaten var (yönlendirme): {title}")
            continue
        write_text(os.path.join(root, rec["content_file"]), extra)
        arts.append(rec)
        new.append(rec)
        known_ids.add(rec["pageid"])
        known_titles |= {rec["wiki_title"].casefold(), rec["title"].casefold()}
        skips.pop(title, None)
        store_save(root, data, backup=first)
        first = False
        log(f"+ [{group}] {rec['title']}  görsel={rec['images']}")

    old = (now - timedelta(days=CONTENT_KEEP_DAYS)).strftime("%Y-%m-%d")
    for r in arts:
        if r["date"] < old:
            try:
                os.remove(os.path.join(root, r["content_file"]))
            except OSError:
                pass
    in_feed = write_feed(root, arts, now, log)
    store_save(root, data)
    log(f"ÖZET yeni={len(new)} rss_öğe={in_feed} toplam_kayıt={len(arts)} api_çağrısı={api.calls}")
    return {"new": len(new), "in_feed": in_feed, "errors": errors, "pool": sum(len(v) for v in pool["groups"].values())}


def kontrol(api=None, log=print):
    api = api or Api()
    _, report = discover(api, log)
    log("\n=== KATEGORİ KONTROL RAPORU ===")
    for k, r in report.items():
        log(f"[{k}] {r['etiket']}: toplam aday {r['toplam']}")
        for f in r["bulunan"]:
            log(f"    ✓ Kategori:{f['kategori']} -> {f['madde']} madde")
        for n in r["not"]:
            log(f"    ! {n}")
        if r["örnek"]:
            log("    örnek: " + ", ".join(r["örnek"]))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Vikipedi yer/il/ilçe RSS üretici")
    ap.add_argument("--root", default=SITE_ROOT)
    ap.add_argument("--count", type=int, help="bu çalışmada en fazla yeni makale (0 = sınırsız)")
    ap.add_argument("--kontrol", action="store_true", help="yalnızca kategorileri doğrula ve raporla")
    ap.add_argument("--havuzu-yenile", action="store_true", help="aday havuzunu zorla yeniden çıkar")
    a = ap.parse_args(argv)
    try:
        if a.kontrol:
            rep = kontrol()
            return 0 if any(r["toplam"] for r in rep.values()) else 1
        res = run(root=a.root, limit=a.count, force_pool=a.havuzu_yenile)
    except (WikiError, StoreError) as e:
        print(f"::error::{e}")
        return 1
    if res["pool"] == 0:
        print("::error::Aday havuzu boş: kategori adları bulunamadı. `--kontrol` ile raporu görün: " + "; ".join(res["errors"]))
        return 1
    if res["in_feed"] == 0:
        print("::error::RSS'e eklenecek makale yok: " + "; ".join(res["errors"] or ["uygun madde bulunamadı"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
