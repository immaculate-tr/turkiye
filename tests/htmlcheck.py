"""Üretilen makale HTML'i için yapısal (HTML5 / W3C içerik modeli) denetim. Dış araç gerektirmez.

Tam bir doğrulayıcı (Nu / vnu) yerine, bu betiğin ürettiği öğeler için en sık görülen hataları yakalar:
etiket eşleşmesi, yasak iç içelik, tablo/liste/figür yapısı, benzersiz id, çalışan # bağlantıları, nitelikler.
"""
import re
from html.parser import HTMLParser

VOID = {"br", "hr", "img", "col", "meta", "link", "input", "wbr"}
PHRASING = {"a", "b", "i", "em", "strong", "u", "s", "sub", "sup", "small", "abbr", "code", "cite", "q", "mark", "br", "img", "span"}
BLOCKS = {"p", "div", "ul", "ol", "dl", "table", "figure", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "hr"}
ALLOWED_TAGS = PHRASING | BLOCKS | {"li", "dt", "dd", "caption", "colgroup", "col", "thead", "tbody", "tfoot", "tr", "th", "td", "figcaption"}
GLOBAL = {"style", "id", "lang", "title", "class"}
ATTRS = {
    "a": {"href", "rel", "target"}, "img": {"src", "alt", "width", "height", "loading", "decoding", "fetchpriority"},
    "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan", "scope"}, "col": {"span"}, "abbr": set(),
}
PARENTS = {"li": {"ul", "ol"}, "dt": {"dl"}, "dd": {"dl"}, "tr": {"table", "tbody", "thead", "tfoot"},
           "td": {"tr"}, "th": {"tr"}, "caption": {"table"}, "colgroup": {"table"}, "col": {"colgroup"},
           "figcaption": {"figure"}, "tbody": {"table"}, "thead": {"table"}, "tfoot": {"table"}}


class Checker(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.ids, self.hrefs, self.heads = [], [], [], [], []

    def err(self, msg):
        self.errors.append(f"{msg} (satır {self.getpos()[0]})")

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            self.err(f"izin verilmeyen/eski etiket <{tag}>")
        names = [k for k, _ in attrs]
        if len(names) != len(set(names)):
            self.err(f"<{tag}> tekrarlı nitelik")
        for k, v in attrs:
            if k not in GLOBAL and k not in ATTRS.get(tag, set()):
                self.err(f"<{tag}> için geçersiz nitelik '{k}'")
            if k == "id":
                self.ids.append(v)
                if not re.fullmatch(r"[A-Za-z][\w:.-]*", v or ""):
                    self.err(f"geçersiz id '{v}'")
            if k == "href" and (v or "").startswith("#"):
                self.hrefs.append(v[1:])
        d = dict(attrs)
        if tag == "img":
            if not (d.get("alt") or "").strip():
                self.err("<img> alt metni boş")
            for k in ("width", "height"):
                if k in d and not (d[k] or "").isdigit():
                    self.err(f"<img> {k} sayı değil")
            if not (d.get("src") or "").startswith("https://"):
                self.err("<img> src https değil")
        if tag == "a" and any(t == "a" for t, _ in self.stack):
            self.err("<a> içinde <a>")
        if tag in PARENTS:
            parent = self.stack[-1][0] if self.stack else None
            if parent not in PARENTS[tag]:
                self.err(f"<{tag}> yanlış üst öğede ({parent})")
        if tag in BLOCKS and self.stack and self.stack[-1][0] == "p":
            self.err(f"<p> içinde blok öğe <{tag}>")
        if tag in BLOCKS and any(t in PHRASING - {"a"} for t, _ in self.stack):
            self.err(f"satır içi öğe içinde blok öğe <{tag}>")
        if tag == "caption" and self.stack and self.stack[-1][0] == "table":
            if self.stack[-1][1]:
                self.err("<caption> tablonun ilk çocuğu değil")
        if self.stack:
            self.stack[-1][1].append(tag)
        if re.fullmatch(r"h[1-6]", tag):
            self.heads.append(int(tag[1]))
        if tag not in VOID:
            self.stack.append((tag, []))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            self.err(f"</{tag}> eşleşmiyor (açık: {self.stack[-1][0] if self.stack else None})")
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break
            return
        t, kids = self.stack.pop()
        if t == "table" and not any(k == "tr" or k in ("tbody", "thead", "tfoot") for k in kids):
            self.err("<table> satırsız")
        if t == "tr" and not kids:
            self.err("<tr> hücresiz")
        if t in ("ul", "ol") and any(k != "li" for k in kids):
            self.err(f"<{t}> içinde li dışında çocuk")

    def close(self):
        super().close()
        if self.stack:
            self.err(f"kapanmamış etiketler: {[t for t, _ in self.stack]}")
        dup = {i for i in self.ids if self.ids.count(i) > 1}
        if dup:
            self.err(f"tekrarlı id: {sorted(dup)}")
        for h in self.hrefs:
            if h not in self.ids:
                self.err(f"# bağlantısının hedefi yok: #{h}")
        for a, b in zip(self.heads, self.heads[1:]):
            if b > a + 1:
                self.err(f"başlık seviyesi atlıyor: h{a} -> h{b}")


def check(html_text):
    c = Checker()
    c.feed(html_text)
    c.close()
    return c.errors
