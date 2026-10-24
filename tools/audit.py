#!/usr/bin/env python3
"""Audit the actual deploy output (`dist/`), not generated working copies in the source tree."""
import json, re, sys, xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
from PIL import Image
R = Path(__file__).resolve().parent.parent
PUBLIC = R / "dist"
C = json.loads((R / "site.config.json").read_text(encoding="utf-8"))
DOM = C["domain"].rstrip("/")
VOID = {"meta","link","img","input","br","hr","source","path","rect","stop","circle","area","embed","wbr"}
fails=[]; passes=0

def ok(cond, message):
    global passes
    if cond: passes += 1
    else: fails.append(message)

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.ids=[]; self.headings=[]; self.imgs=[]; self.links=[]; self.resources=[]
        self.canon=[]; self.ld=[]; self.title=""; self.desc=""; self.cur=None; self.buf=""; self.errors=[]; self.noindex=False; self.og={}; self.text=[]; self.geo={}
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag not in VOID: self.stack.append(tag)
        if "id" in a: self.ids.append(a["id"])
        if tag in ("h1","h2","h3","h4"): self.headings.append(int(tag[1]))
        if tag=="img": self.imgs.append(a)
        if tag=="a" and "href" in a: self.links.append(a["href"])
        if tag in ("script","img","video","source","iframe") and a.get("src"): self.resources.append(a["src"])
        if tag=="link" and a.get("href"):
            rel=(a.get("rel") or "").lower()
            if rel=="canonical": self.canon.append(a["href"])
            if rel in ("stylesheet","icon","manifest","apple-touch-icon") or a.get("as") in ("font","image"): self.resources.append(a["href"])
        if tag=="meta":
            if a.get("name")=="description": self.desc=a.get("content","")
            if a.get("name")=="robots": self.noindex="noindex" in a.get("content","")
            if (a.get("property") or "").startswith("og:"): self.og[a["property"]]=a.get("content","")
            if a.get("name") in ("geo.region", "geo.placename", "geo.position", "ICBM"): self.geo[a["name"]]=a.get("content","")
        if tag=="script" and a.get("type")=="application/ld+json": self.cur="ld"; self.buf=""
        if tag=="title": self.cur="title"; self.buf=""
    def handle_endtag(self, tag):
        if tag in VOID: return
        if self.stack and self.stack[-1]==tag: self.stack.pop()
        else: self.errors.append(f"unbalanced </{tag}> stack={self.stack[-3:]}")
        if self.cur and tag in ("script","title"):
            if self.cur=="ld": self.ld.append(self.buf)
            else: self.title=self.buf
            self.cur=None
    def handle_data(self, data):
        if self.cur: self.buf += data
        if self.cur != "ld": self.text.append(data)

def public_target(url):
    """Map a same-site absolute/relative URL path to a dist target."""
    raw=urlsplit(url)
    path=unquote(raw.path or "/")
    if raw.netloc and raw.netloc.lower() != urlsplit(DOM).netloc.lower(): return None
    if not path.startswith("/"): return None
    if path=="/": target=PUBLIC/"index.html"
    else:
        direct=PUBLIC/path.lstrip("/")
        if direct.is_file(): target=direct
        elif path.endswith("/"): target=PUBLIC/path.lstrip("/")/"index.html"
        else:
            page=PUBLIC/path.lstrip("/")/"index.html"
            target=page if page.is_file() else direct
    return target

def exists(url):
    target=public_target(url)
    return bool(target and target.exists() and target.is_file())

ok(PUBLIC.exists(), "dist/ deploy output is missing; run python3 build.py")
try:
    vercel=json.loads((R/"vercel.json").read_text(encoding="utf-8")); ok(vercel.get("outputDirectory")=="dist", "Vercel outputDirectory must be dist")
except Exception as e:
    vercel={}; ok(False, f"vercel.json invalid: {e}")
for secret_path in ("build.py","site.config.json","content/services.py","content/services.json","content/extended_content.py","content/legal.py","tools/audit.py","tools/run_all.py","DEPLOY.md","AUDIT-REPORT.md","DEEP-AUDIT-REPORT.md","reports/quality-report.md"):
    ok(not (PUBLIC/secret_path).exists(), f"private source leaked into dist: {secret_path}")

pages=sorted(PUBLIC.rglob("*.html"))
try:
    root=ET.parse(PUBLIC/"sitemap.xml").getroot()
    sm_entries=root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")
    sm=[x.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}loc","") for x in sm_entries]
    dates=[x.findtext("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod","") for x in sm_entries]
    ok(len(sm)==len(set(sm)), "sitemap contains duplicate URLs")
    ok(all(re.fullmatch(r"\d{4}-\d{2}-\d{2}",d or "") for d in dates), "sitemap lastmod has an invalid date")
    ok(all(u.startswith(DOM+"/") for u in sm), "sitemap has a URL outside the configured HTTPS domain")
except Exception as e:
    sm=[]; dates=[]; ok(False, f"sitemap.xml invalid: {e}")

canonicals=set(); titles={}; descriptions={}; parsers={}
for f in pages:
    rel=f.relative_to(PUBLIC).as_posix(); p=Parser()
    try: p.feed(f.read_text(encoding="utf-8")); p.close()
    except Exception as e: fails.append(f"{rel}: HTML parse exception {e}"); continue
    parsers[rel]=p
    ok(not p.errors and not p.stack, f"{rel}: unbalanced HTML {p.errors[:2]} {p.stack[-3:]}")
    ok(len(p.ids)==len(set(p.ids)), f"{rel}: duplicate IDs")
    ok(p.h1 if False else p.headings.count(1)==1, f"{rel}: must have exactly one H1 (found {p.headings.count(1)})")
    ok(all(b-a<=1 for a,b in zip(p.headings,p.headings[1:])), f"{rel}: heading levels skip {p.headings}")
    for img in p.imgs:
        ok(img.get("alt") is not None and img.get("width") and img.get("height"), f"{rel}: image requires alt, width and height: {img.get('src','(no src)')}")
        if img.get("src") and img["src"].startswith("/"): ok(exists(img["src"]), f"{rel}: missing image {img['src']}")
        if img.get("loading") not in ("lazy",None): ok(img.get("fetchpriority")=="high", f"{rel}: only LCP image may be eager/high priority")
    for l in p.links:
        if l.startswith("/"): ok(exists(l), f"{rel}: broken internal link {l}")
        if l.startswith((".","../")): ok(False, f"{rel}: relative path {l}")
        if l.startswith("#") and l!="#": ok(f'id="{l[1:]}"' in f.read_text(encoding="utf-8"), f"{rel}: missing local anchor {l}")
    for res in p.resources:
        if res.startswith("/"): ok(exists(res), f"{rel}: missing asset {res}")
    if rel=="404.html":
        ok(p.noindex and not p.canon, "404 must be noindex and have no canonical")
        continue
    ok(bool(p.geo.get("geo.region")), f"{rel}: missing geo.region")
    ok(bool(p.geo.get("geo.placename")), f"{rel}: missing geo.placename")
    ok(bool(p.geo.get("geo.position")), f"{rel}: missing geo.position")
    ok(bool(p.geo.get("ICBM")), f"{rel}: missing ICBM")
    ok(p.title.startswith("") and 50<=len(p.title)<=60, f"{rel}: title length {len(p.title)} (must be 50-60)")
    ok(140<=len(p.desc)<=155, f"{rel}: description length {len(p.desc)} (must be 140-155)")
    ok(p.title not in titles, f"{rel}: duplicate title also in {titles.get(p.title)}")
    ok(p.desc not in descriptions, f"{rel}: duplicate description also in {descriptions.get(p.desc)}")
    titles[p.title]=rel; descriptions[p.desc]=rel
    ok(len(p.canon)==1, f"{rel}: expected exactly one self-canonical")
    if p.canon:
        c=p.canon[0]; canonicals.add(c)
        ok(c.startswith(DOM+"/"), f"{rel}: canonical is not on configured domain")
        ok(p.og.get("og:url")==c, f"{rel}: og:url must match canonical")
        if rel=="index.html": exp=DOM+"/"
        elif rel.endswith("index.html"): exp=DOM+"/"+rel[:-10].rstrip("/")+"/"
        else: exp=DOM+"/"+rel
        ok(c==exp, f"{rel}: canonical {c} != {exp}")
    og=p.og.get("og:image","")
    imfile=public_target(og) if og.startswith(DOM) else None
    try: im_ok=bool(imfile and imfile.is_file() and Image.open(imfile).size==(1200,630))
    except Exception: im_ok=False
    ok(im_ok, f"{rel}: og:image missing or not 1200x630")
    text=" ".join(p.text)
    for block in p.ld:
        try: obj=json.loads(block)
        except Exception as e: ok(False, f"{rel}: invalid JSON-LD: {e}"); continue
        ok(True,"JSON-LD valid")
        blocks=obj if isinstance(obj,list) else [obj]
        for node in blocks:
            if isinstance(node,dict) and node.get("@type")=="FAQPage":
                qns=[x.get("name","") for x in node.get("mainEntity",[]) if isinstance(x,dict)]
                ok(bool(qns) and all(q in text for q in qns), f"{rel}: FAQ schema does not match visible FAQs")
            if isinstance(node, dict) and node.get("@type") == "ProfessionalService":
                geo_node = node.get("geo", {})
                ok(isinstance(geo_node, dict) and geo_node.get("@type") == "GeoCoordinates" and "latitude" in geo_node and "longitude" in geo_node, f"{rel}: ProfessionalService schema missing valid GeoCoordinates")

ok(set(sm)==canonicals, f"sitemap/canonical mismatch ({len(set(sm)^canonicals)} differing URLs)")
for url in sm: ok(exists(url), f"sitemap URL missing from dist: {url}")
rb=(PUBLIC/"robots.txt").read_text(encoding="utf-8")
ok("User-agent: *" in rb and "Allow: /" in rb and "Sitemap: "+DOM+"/sitemap.xml" in rb, "robots.txt missing allow rule or sitemap")
ok((PUBLIC/".well-known/security.txt").exists(), "security.txt is missing")
ok((PUBLIC/"llms.txt").exists(), "llms.txt is missing from dist")
ok((PUBLIC/"llms-full.txt").exists(), "llms-full.txt is missing from dist")
ok((PUBLIC/".well-known/ai-catalog.json").exists(), ".well-known/ai-catalog.json is missing from dist")
cat_p = PUBLIC/".well-known/ai-catalog.json"
if cat_p.exists():
    try:
        cat_data = json.loads(cat_p.read_text(encoding="utf-8"))
        ok(cat_data.get("specVersion") == "1.0", "ai-catalog.json missing or invalid specVersion")
        entries = cat_data.get("entries", [])
        ok(isinstance(entries, list) and len(entries) > 0, "ai-catalog.json entries must be non-empty list")
        urn_pat = re.compile(r"^urn:air:[a-zA-Z0-9.-]+(:[a-zA-Z0-9._-]+)+$")
        valid_media = {
            "application/ai-catalog+json",
            "application/agent-card+json",
            "application/a2a-agent-card+json",
            "application/mcp-server-card+json",
            "application/agent-skills+zip",
            "application/agent-skills+gzip",
            'text/markdown; profile="urn:air:agent-skills"',
            "application/ai-registry",
            "application/ai-registry+json"
        }
        for e in entries:
            ident = e.get("identifier", "")
            ok(bool(urn_pat.match(ident)), f"ai-catalog entry '{ident}' does not match ARD RFC 8141 pattern")
            ok(e.get("type") in valid_media, f"ai-catalog entry '{ident}' media type '{e.get('type')}' not standard")
            queries = e.get("representativeQueries", [])
            ok(isinstance(queries, list) and 2 <= len(queries) <= 5, f"ai-catalog entry '{ident}' missing 2-5 representativeQueries")
            ok(all(isinstance(q, str) and q.strip() for q in queries), f"ai-catalog entry '{ident}' representativeQueries must be non-empty strings")
            ok(bool(e.get("displayName")), f"ai-catalog entry '{ident}' missing displayName")
            ok(bool(e.get("url")), f"ai-catalog entry '{ident}' missing url")
            ok(bool(e.get("description")), f"ai-catalog entry '{ident}' missing description")
    except Exception as ex:
        ok(False, f"ai-catalog.json failed ARD validation: {ex}")
style_css = (R/"assets/css/style.css").read_text(encoding="utf-8")
ok("#075e54" in style_css.lower(), "wa-float dark green WCAG AA contrast color not found in style.css")
ok(not re.search(r"\.wa-float\s*\{[^}]*background:\s*#128c7e", style_css, re.I), "wa-float still uses low-contrast #128c7e in style.css")
ok((PUBLIC/"favicon.ico").exists(), "favicon.ico is missing from dist")
ok((PUBLIC/"assets/favicon-32x32.png").exists(), "assets/favicon-32x32.png is missing from dist")
ok((PUBLIC/"assets/favicon-16x16.png").exists(), "assets/favicon-16x16.png is missing from dist")
ok((PUBLIC/"assets/favicon-48x48.png").exists(), "assets/favicon-48x48.png is missing from dist")
ok((PUBLIC/"assets/favicon-96x96.png").exists(), "assets/favicon-96x96.png is missing from dist")
llms_txt = (PUBLIC/"llms.txt").read_text(encoding="utf-8")
ok(not re.search(r"\{[UC]", llms_txt), "llms.txt contains un-evaluated template syntax")
llms_full = (PUBLIC/"llms-full.txt").read_text(encoding="utf-8")
ok(not re.search(r"\{[UC]", llms_full), "llms-full.txt contains un-evaluated template syntax")
# No inline scripts/styles: the generated site keeps a strict self-only CSP.
# DOM updates must use textContent/createElement; user-entered form data is never interpolated into HTML strings.
for js in sorted((R / "assets/js").glob("*.js")):
    source = js.read_text(encoding="utf-8")
    ok(not re.search(r"\b(?:innerHTML|outerHTML|insertAdjacentHTML|document\.write)\b", source), f"{js.relative_to(R)}: unsafe HTML string insertion API present")
for rel,p in parsers.items():
    src=(PUBLIC/rel).read_text(encoding="utf-8")
    ok(not re.search(r"<script(?![^>]*type=[\"']application/ld\+json[\"'])[^>]*>\s*[^<\s]",src,re.I), f"{rel}: inline JavaScript conflicts with CSP")
    ok(not re.search(r"\sstyle\s*=",src,re.I), f"{rel}: inline style conflicts with CSP")
# Contrast checks for the current design tokens.
def lum(h):
    h=h.lstrip("#"); rgb=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    conv=lambda c: c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
    r,g,b=[conv(x) for x in rgb]; return .2126*r+.7152*g+.0722*b
def cr(a,b):
    x,y=sorted((lum(a),lum(b)),reverse=True); return (x+.05)/(y+.05)
for fg,bg,label in [("#4A5878","#F6F9FF","body/ice"),("#4A5878","#EAF0FB","body/mist"),("#4A5878","#FFFFFF","body/card"),("#2F5BEA","#FFFFFF","link/white"),("#FFFFFF","#2F5BEA","button/blue"),("#0A1633","#F6F9FF","heading/ice"),("#0A1633","#FFFFFF","heading/white"),("#FFFFFF","#0B1F4D","footer/white")]:
    ok(cr(fg,bg)>=4.5, f"contrast {label}: {cr(fg,bg):.2f}:1")
# Service FAQ is visible by generator construction, count confirmed in the service template source.
# No fake reviews/ratings. Search code output for AggregateRating.
allpublic="\n".join(f.read_text(encoding="utf-8",errors="ignore") for f in pages if f.is_file())
ok('"AggregateRating"' not in allpublic and "aggregateRating" not in allpublic, "fake AggregateRating must not be published")
print(f"{passes} checks passed, {len(fails)} failed")
for x in fails: print(" FAIL",x)
sys.exit(1 if fails else 0)
