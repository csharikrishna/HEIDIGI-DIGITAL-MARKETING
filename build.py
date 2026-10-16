#!/usr/bin/env python3
"""Static site generator for Hei Digi. Run: python3 build.py  (needs Pillow). Output is plain HTML committed to the project."""
import json, re, hashlib, html, datetime, textwrap, sys, urllib.parse, shutil, subprocess, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, str(Path(__file__).parent / "content"))
from services import S, HOME_FAQ
from legal import privacy, terms
from extended_content import SERVICE_DETAILS, INDUSTRIES, LOCATIONS, BLOGS
R = Path(__file__).parent
C = json.loads((R/"site.config.json").read_text(encoding="utf-8"))
raw = (R/"assets/js/data.js").read_text(encoding="utf-8")
D = json.loads(raw[raw.index("{", raw.index("window.HEIDIGI_DATA")): raw.rindex("}")+1])
esc = lambda s: html.escape(str(s), quote=True)
DOM = C["domain"].rstrip("/")
U = lambda p: DOM + p
EMAIL, PHONE = C["email"], C["phone"]
ADDRESS = C.get("address", {})
MAPS_URL = C.get("mapsUrl", "")
GEO = C.get("geo", {})
LAT = GEO.get("latitude", GEO.get("lat", 13.6288))
LNG = GEO.get("longitude", GEO.get("lng", 79.4192))
GEO_REGION = C.get("geoRegion", "IN-AP")
GEO_PLACENAME = C.get("geoPlacename", "Tirupati, South Andhra Pradesh")
FONTS = all((R/"assets/fonts"/f).exists() for f in ("inter.woff2", "sora.woff2"))
LEAD = C.get("leadEndpoint", ""); TSK = C.get("turnstileSiteKey", ""); HSTS = int(C.get("hstsMaxAge", 0)); UPD = C.get("legalUpdated", "2026-10-09"); AN = C["analytics"]
def av(p): return p + "?v=" + hashlib.sha1((R/p.lstrip("/")).read_bytes()).hexdigest()[:8]
def fontlinks():
    # Prefer self-hosted fonts if the one-time fetch has been completed; otherwise use fast local system fonts.
    if FONTS:
        return "".join(f'<link rel="preload" href="/assets/fonts/{f}.woff2" as="font" type="font/woff2" crossorigin>' for f in ("inter", "sora")) + f'<link rel="stylesheet" href="{av("/assets/css/fonts.css")}">'
    return ""

INTRO = ("Tell us about your business. Your enquiry is sent to us securely and we reply on the phone or email you give." if LEAD else "Tell us about your business. Your message opens in WhatsApp for you to send. We do not store form entries on this website.")
NOTE = ("We use these details only to reply to your enquiry. They are emailed to us securely and are not kept in a website database." if LEAD else "The button opens WhatsApp with your message. It is sent only when you press Send there, and this website does not store it.")
SLUG = {s["name"]: s["slug"] for s in S}
BYSLUG = {s["slug"]: s for s in S}
pages = {}   # path -> (html, indexable)
WARN = []

# ---------- images ----------
def font(sz, bold=True):
    # Use the system DejaVu face when available; fall back to Pillow's built-in bitmap face.
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
        "/usr/share/fonts/truetype/liberation2/LiberationSans%s-Regular.ttf" % ("-Bold" if bold else ""),
    ]
    for candidate in candidates:
        try:
            if Path(candidate).exists(): return ImageFont.truetype(candidate, sz)
        except OSError: pass
    try: return ImageFont.load_default(size=sz)
    except TypeError: return ImageFont.load_default()
def grad(w, h):
    im = Image.new("RGB", (w, h)); px = im.load()
    for y in range(h):
        for x in range(w):
            t = (x/w*0.6 + y/h*0.4)
            px[x, y] = (int(11+60*t), int(10+30*t), int(46+110*t))
    return im
def og(name, title, sub):
    out = R/f"assets/og/{name}.jpg"; out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists(): return f"/assets/og/{name}.jpg"
    im = grad(1200, 630); d = ImageDraw.Draw(im)
    d.ellipse((780, -160, 1380, 440), fill=(79, 70, 229)); im = Image.blend(grad(1200, 630), im, .45); d = ImageDraw.Draw(im)
    d.text((70, 70), "Hei Digi", font=font(40), fill="white")
    y = 200
    for ln in textwrap.wrap(title, 24)[:3]:
        d.text((70, y), ln, font=font(64), fill="white"); y += 80
    d.text((70, 540), sub, font=font(30, False), fill=(196, 181, 253))
    im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return f"/assets/og/{name}.jpg"
def icons():
    for sz, n in ((180, "apple-touch-icon"), (192, "icon-192"), (512, "icon-512"),
                  (16, "favicon-16x16"), (32, "favicon-32x32"), (48, "favicon-48x48"), (96, "favicon-96x96")):
        out_f = R/f"assets/{n}.png"
        if not out_f.exists():
            im = grad(sz, sz); d = ImageDraw.Draw(im)
            if sz >= 48:
                for i, t in enumerate(("Hei", "Digi")):
                    f = font(int(sz*.28)); w = d.textlength(t, font=f)
                    d.text(((sz-w)/2, sz*(.2+.33*i)), t, font=f, fill="white")
            elif sz >= 32:
                f = font(int(sz*.38)); w = d.textlength("HD", font=f)
                d.text(((sz-w)/2, sz*.22), "HD", font=f, fill="white")
            else:
                f = font(10); w = d.textlength("H", font=f)
                d.text(((sz-w)/2, 2), "H", font=f, fill="white")
            im.save(out_f, optimize=True)
    ico_f = R/"assets/favicon.ico"
    if not ico_f.exists():
        ico_im = grad(48, 48); d = ImageDraw.Draw(ico_im)
        f = font(int(48*.28)); w = d.textlength("HD", font=f)
        d.text(((48-w)/2, 48*.22), "HD", font=f, fill="white")
        ico_im.save(ico_f, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    if not (R/"favicon.ico").exists() and ico_f.exists():
        shutil.copy2(ico_f, R/"favicon.ico")

# ---------- shared layout ----------
def jl(o): return '<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "</script>"
ORG = {"@context": "https://schema.org", "@type": "ProfessionalService", "@id": U("/#org"), "name": C["name"], "url": U("/"),
       "logo": U("/assets/heidigi-logo.webp"), "image": U("/assets/og/home.jpg"), "email": EMAIL, "telephone": C["phone"],
       "description": "Digital marketing and SEO services in Tirupati, including local SEO, Google Business Profile management, social media marketing, Meta Ads, creative design, video and branding.",
       "knowsAbout": ["Search engine optimization", "Local SEO", "Google Business Profile management", "Social media marketing", "Meta Ads", "Creative design", "Video editing", "Personal branding"],
       "address": {"@type": "PostalAddress", "streetAddress": ADDRESS.get("streetAddress", ""),
                   "addressLocality": ADDRESS.get("addressLocality", C["city"]),
                   "addressRegion": ADDRESS.get("addressRegion", C["region"]),
                   "postalCode": ADDRESS.get("postalCode", ""),
                   "addressCountry": ADDRESS.get("addressCountry", C["country"])},
       "geo": {"@type": "GeoCoordinates", "latitude": LAT, "longitude": LNG},
       "openingHoursSpecification": C.get("openingHoursSpecification", [{"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], "opens": "09:30", "closes": "18:30"}]),
       "priceRange": C.get("priceRange", "₹₹"),
       "paymentAccepted": C.get("paymentAccepted", "Cash, UPI, Bank Transfer"),
       "currenciesAccepted": C.get("currenciesAccepted", "INR"),
       "inLanguage": C.get("inLanguage", ["en-IN", "te"]),
       "areaServed": [{"@type": "City", "name": n} for n in ["Tirupati", "Srikalahasti", "Chittoor", "Renigunta", "Chandragiri", "Madanapalle", "Nellore", "Gudur", "Puttur"]] + [{"@type": "AdministrativeArea", "name": "South Andhra Pradesh"}, {"@type": "AdministrativeArea", "name": "Rayalaseema"}],
       "founder": {"@type": "Person", "name": C.get("founder", "Coach Sri"), **({"sameAs": [C["founderSocial"]]} if C.get("founderSocial") else {})},
       "hasOfferCatalog": {"@type": "OfferCatalog", "name": "Digital marketing services", "itemListElement": [{"@type": "Offer", "itemOffered": {"@type": "Service", "name": z["name"], "url": U("/services/"+z["slug"]+"/")}} for z in S]},
       "contactPoint": {"@type": "ContactPoint", "contactType": "sales and enquiries", "telephone": C["phone"], "email": EMAIL}}
if MAPS_URL: ORG["hasMap"] = MAPS_URL
if C["socials"]: ORG["sameAs"] = [s["url"] for s in C["socials"]]
def normalise_title(title):
    title = re.sub(r"\s+", " ", str(title)).strip()
    suffix = " | Hei Digi"
    # Standardise the brand suffix and preserve whole words if a title is too long.
    core = re.sub(r"\s*\|\s*Hei Digi(?:, Tirupati)?$", "", title).strip()
    if not core:
        core = title
    if len(core + suffix) > 60:
        budget = 60 - len(suffix)
        core = core[:budget].rsplit(" ", 1)[0].rstrip(" |,-")
    if len(core + suffix) < 50:
        for extra in (" for Tirupati Businesses", " in Tirupati, Andhra Pradesh", " for Local Businesses"):
            candidate = core + extra
            if 50 <= len(candidate + suffix) <= 60:
                core = candidate
                break
        if len(core + suffix) < 50:
            extra = " | Tirupati"
            candidate = core + extra
            if len(candidate + suffix) <= 60:
                core = candidate
    return (core + suffix)[:60]

def normalise_description(desc):
    desc = re.sub(r"\s+", " ", str(desc)).strip()
    if len(desc) > 155:
        desc = desc[:153].rsplit(" ", 1)[0].rstrip(" ,;:-") + "."
    if len(desc) < 140:
        addon = " Contact Hei Digi in Tirupati to discuss a practical plan for your business."
        desc = (desc + addon)[:155]
        if len(desc) == 155 and " " in desc:
            desc = desc[:154].rsplit(" ", 1)[0].rstrip(" ,;:-") + "."
    return desc

def head(title, desc, path, ogimg, ld=(), index=True):
    title = normalise_title(title)
    desc = normalise_description(desc)
    t, d = esc(title), esc(desc)
    robots = '<meta name="robots" content="noindex,nofollow">' if not index else f'<meta name="robots" content="index,follow,max-image-preview:large"><link rel="canonical" href="{U(path)}">'
    og_ = "" if not index else f'''<meta property="og:type" content="website"><meta property="og:site_name" content="{C["name"]}"><meta property="og:title" content="{t}"><meta property="og:description" content="{d}"><meta property="og:url" content="{U(path)}"><meta property="og:locale" content="en_IN"><meta property="og:image" content="{U(ogimg)}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="{t}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{t}"><meta name="twitter:description" content="{d}"><meta name="twitter:image" content="{U(ogimg)}">'''
    return f'''<!DOCTYPE html>
<html lang="en-IN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{t}</title><meta name="description" content="{d}">{robots}<meta name="theme-color" content="#0b0a2e">
<meta name="geo.region" content="{esc(GEO_REGION)}"><meta name="geo.placename" content="{esc(GEO_PLACENAME)}"><meta name="geo.position" content="{LAT};{LNG}"><meta name="ICBM" content="{LAT}, {LNG}">
<link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" href="/assets/favicon.svg" type="image/svg+xml"><link rel="icon" href="/assets/favicon-32x32.png" type="image/png" sizes="32x32"><link rel="icon" href="/assets/favicon-16x16.png" type="image/png" sizes="16x16"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png"><link rel="manifest" href="/manifest.webmanifest">
{og_}{fontlinks()}{f'<link rel="preload" as="image" href="{av('/assets/work/hero-reel.webp')}" fetchpriority="high">' if path == '/' else ''}<link rel="stylesheet" href="{av('/assets/css/style.css')}"><script src="{av('/assets/js/boot.js')}"></script>
{"".join(jl(x) for x in ld)}</head>'''
LOGO = '<img class="brand-mark" src="/assets/heidigi-logo.webp" width="40" height="40" alt="" aria-hidden="true" decoding="async">'
NAV = [("Home", "/"), ("About", "/about/"), ("Services", "/services/"), ("Our Clients", "/#clients"), ("Industries", "/industries/"), ("Blog", "/blog/"), ("Personal Branding", "/services/personal-branding/"), ("Contact", "/contact/")]
def header(home=False):
    links = "".join(f'<a href="{h}">{n}</a>' for n, h in NAV)
    return f'''<a class="skip" href="#main">Skip to content</a>
<header id="hdr" class="{"" if home else "solid"}"><div class="wrap bar"><a href="/" class="logo" aria-label="Hei Digi, home">{LOGO}<b>Hei <em>Digi</em></b></a>
<nav id="nav" aria-label="Main">{links}</nav><a class="btn sm cta" href="/contact/" data-cta="header_contact">Let's Grow Together</a>
<button id="burger" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="nav"><span></span><span></span><span></span></button></div></header>'''
def footer():
    sv = "".join(f'<li><a href="/services/{s["slug"]}/">{esc(s["name"])}</a></li>' for s in S)
    soc = "".join(f'<li><a href="{esc(s["url"])}" rel="me noopener" target="_blank">{esc(s["label"])}</a></li>' for s in C["socials"])
    return f'''<footer><div class="wrap fgrid"><div><b>Hei Digi</b><p>Your Digital Presence. Our Creative Strategy.</p><p>{C["city"]}, {C["region"]}, India</p></div>
<nav aria-label="Services"><h2>Services</h2><ul>{sv}</ul></nav>
<nav aria-label="Company"><h2>Explore</h2><ul><li><a href="/about/">About Hei Digi</a></li><li><a href="/#clients">Our Clients</a></li><li><a href="/industries/">Industries</a></li><li><a href="/locations/">Service Areas</a></li><li><a href="/blog/">Marketing Guides</a></li><li><a href="/#process">Process</a></li><li><a href="/contact/">Contact</a></li></ul></nav>
<div><h2>Contact</h2><ul><li><a href="mailto:{EMAIL}">{EMAIL}</a></li><li><a href="tel:{PHONE}">{C["phoneDisplay"]}</a></li><li><a href="https://wa.me/{PHONE.lstrip("+")}" target="_blank" rel="noopener" data-cta="footer_whatsapp">WhatsApp</a></li>{f'<li><a href="{MAPS_URL}" target="_blank" rel="noopener">Get directions</a></li>' if MAPS_URL else ''}{soc}</ul><p class="footer-address">{esc(ADDRESS.get("streetAddress", ""))}, {esc(ADDRESS.get("addressLocality", C["city"]))}, {esc(ADDRESS.get("addressRegion", C["region"]))} {esc(ADDRESS.get("postalCode", ""))}</p></div></div>
<div class="wrap copy">© <span id="yr">{datetime.date.today().year}</span> Hei Digi, {C["city"]}. · <a href="/privacy/">Privacy Policy</a> · <a href="/terms/">Terms of Service</a> · <a href="/cookie-policy/">Cookie Policy</a> · <a href="/disclaimer/">Disclaimer</a><span id="consent-slot"></span></div></footer>
<a class="wa-float" href="https://wa.me/{PHONE.lstrip("+")}?text={urllib.parse.quote('Hi Hei Digi, I would like to discuss digital marketing for my business.') }" target="_blank" rel="noopener" aria-label="Chat with Hei Digi on WhatsApp" data-cta="floating_whatsapp"><svg class="whatsapp-icon" viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" d="M16 2.3A13.6 13.6 0 0 0 4.4 23l-1.8 6.5 6.7-1.8A13.7 13.7 0 1 0 16 2.3zm0 24.8c-2.1 0-4.1-.6-5.9-1.7l-.4-.2-3.9 1.1 1.1-3.8-.3-.4A11.2 11.2 0 1 1 16 27.1zm6.2-8.4c-.3-.2-1.8-.9-2.1-1s-.5-.2-.7.2-.8 1-1 1.2-.4.2-.7.1a9.2 9.2 0 0 1-2.7-1.7 10.1 10.1 0 0 1-1.9-2.4c-.2-.3 0-.5.1-.7l.5-.6c.2-.2.2-.4.3-.6.1-.2 0-.4 0-.6s-.7-1.7-1-2.3c-.3-.6-.5-.5-.7-.5h-.6c-.2 0-.6.1-.9.4-.3.3-1.2 1.1-1.2 2.7s1.2 3.1 1.4 3.3c.2.2 2.3 3.6 5.6 5 .8.3 1.4.5 1.9.6.8.3 1.6.2 2.2.1.7-.1 1.8-.7 2.1-1.4.3-.7.3-1.3.2-1.4-.1-.1-.3-.2-.6-.4z"/></svg><b>Chat on WhatsApp</b></a>
<script src="{av('/assets/js/config.js')}"></script><script src="{av('/assets/js/data.js')}" defer></script><script src="{av('/assets/js/lead.js')}" defer></script><script src="{av('/assets/js/main.js')}" defer></script></body></html>'''
def faq_html(items):
    return "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in items)
def crumbs(items):
    return '<nav class="crumbs" aria-label="Breadcrumb"><ol>' + "".join(
        f'<li><a href="{h}">{esc(n)}</a></li>' if h else f'<li aria-current="page">{esc(n)}</li>' for n, h in items) + "</ol></nav>"
def bc_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        dict({"@type": "ListItem", "position": i+1, "name": n}, **({"item": U(h)} if h else {})) for i, (n, h) in enumerate(items)]}
def wa_link(txt): return f"https://wa.me/{PHONE.lstrip('+')}?text=" + __import__("urllib.parse").parse.quote(txt)
def cta_block(topic, svc_name=None):
    q = f"/?service={SLUG.get(svc_name,'')}#contact" if svc_name else "/#contact"
    return f'''<section class="sec dark" id="enquire"><div class="wrap narrow center"><h2>Talk to us about {esc(topic)}</h2><p class="lead">Tell us about your business and goals. We reply with questions before we suggest anything.</p>
<div class="btns c"><a class="btn" href="{q}" data-cta="enquiry_form_{SLUG.get(svc_name,'general')}">Send an enquiry</a><a class="btn ghost" href="{wa_link("Hi Hei Digi, I would like to talk about "+topic+".")}" target="_blank" rel="noopener" data-cta="whatsapp_{SLUG.get(svc_name,'general')}">WhatsApp us</a><a class="btn ghost" href="mailto:{EMAIL}?subject={__import__("urllib.parse").parse.quote("Enquiry: "+topic)}" data-cta="email_{SLUG.get(svc_name,'general')}">Email us</a></div></div></section>'''

# ---------- portfolio ----------
def prep_portfolio():
    items = []
    for it in D["portfolio"]:
        it = dict(it); it["src"] = "/" + it["src"].lstrip("/")
        f = R / it["src"].lstrip("/")
        if not f.exists(): WARN.append(f"missing file {it['src']} (item {it['id']} skipped)"); continue
        if it["category"] not in D["categories"]: WARN.append(f"{it['id']}: unknown category"); continue
        if not it.get("alt") and it["type"] == "image": WARN.append(f"{it['id']}: add alt text")
        if it["type"] == "image":
            im = Image.open(f); it["w"], it["h"] = im.size; ss = []
            for tw in (640, 1200):
                if im.size[0] >= tw:
                    o = R / f"assets/work/optimized/{f.stem}-{tw}.webp"; o.parent.mkdir(parents=True, exist_ok=True)
                    im.convert("RGB").resize((tw, round(im.size[1]*tw/im.size[0]))).save(o, "WEBP", quality=80)
                    ss.append(f"/assets/work/optimized/{f.stem}-{tw}.webp {tw}w")
            it["srcset"] = ", ".join(ss)
        else:
            it.setdefault("w", 1280); it.setdefault("h", 720)
            if not it.get("poster"): WARN.append(f"{it['id']}: add a poster image for the video")
            else: it["poster"] = "/" + it["poster"].lstrip("/")
        items.append(it)
    return items
def media(it, detail=False):
    t = esc(it.get("title") or f'{it["client"]} {it["category"]}')
    if it["type"] == "video":
        p = f' poster="{esc(it["poster"])}"' if it.get("poster") else ""
        return f'<video src="{esc(it["src"])}"{p} width="{it["w"]}" height="{it["h"]}" preload="none" playsinline {"controls" if detail else "muted"} aria-label="{t}"></video>'
    sizes = "(max-width:700px) 92vw, 1000px" if detail else "(max-width:700px) 92vw, 380px"
    ss = f' srcset="{esc(it["srcset"])}" sizes="{sizes}"' if it.get("srcset") else ""
    return f'<img src="{esc(it["src"])}"{ss} width="{it["w"]}" height="{it["h"]}" alt="{esc(it.get("alt") or t)}" {"" if detail else "loading=\"lazy\" "}decoding="async">'
def work_pages(P):
    for it in P:
        path = f"/work/{it['id']}/"; title = it.get("title") or f"{it['client']} - {it['category']}"
        svc = " ".join(f'<a href="/services/{SLUG[n]}/">{esc(n)}</a>' for n in it.get("services", []) if n in SLUG)
        desc = it.get("description") or ""
        meta = it.get("metaDescription") or f"{it['category']} work for {it['client']} from Hei Digi, a digital marketing agency in Tirupati."
        items = [("Home", "/"), ("Client example", None), (title, None)]
        ld = [ORG, {"@context": "https://schema.org", "@type": "CreativeWork", "name": title, "description": meta, "url": U(path),
                    "creator": {"@id": U("/#org")}, "image": U(it["poster"] if it["type"] == "video" and it.get("poster") else it["src"])}]
        body = f'''{header()}<main id="main" class="sec top"><div class="wrap narrow">{crumbs(items)}<h1>{esc(title)}</h1><p class="mut">{esc(it["client"])} · {esc(it["category"])}</p><div class="detail">{media(it, True)}</div>{"<p>"+esc(desc)+"</p>" if desc else ""}{"<p>Services: "+svc+"</p>" if svc else ""}</div></main>{cta_block(it["category"].lower()+" work")}'''
        # Give each work detail page its own OG image; reusing "home" overwrote the homepage image during rebuilds.
        social_image = og(f"work-{it['id']}", title, "Hei Digi · Tirupati")
        pages[path] = (head(f"{title} | Hei Digi", meta[:160], path, social_image, ld) + "<body>" + body + footer(), True)

# ---------- pages ----------
def service_pages():
    for s in S:
        path = f"/services/{s['slug']}/"; items = [("Home", "/"), ("Services", "/services/"), (s["name"], None)]
        rel = "".join(f'<li><a href="/services/{r}/">{esc(BYSLUG[r]["name"])}</a> <span class="mut">- {esc(BYSLUG[r]["short"])}</span></li>' for r in s["rel"])
        detail = SERVICE_DETAILS.get(s["slug"], {})
        faqs = s["faq"][:3] + detail.get("faq", [])[:4]
        ld = [ORG, bc_ld(items), {"@context": "https://schema.org", "@type": "Service", "name": s["name"], "description": s["desc"], "url": U(path), "serviceType": s["name"], "areaServed": [{"@type":"City","name":n} for n in ["Tirupati","Renigunta","Chittoor"]], "provider": {"@id": U("/#org")}}, {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in faqs]}]
        detail_body = f'''<h2>What this service looks like in Tirupati</h2><p>{esc(detail.get("context", s["intro"]))}</p>
<h2>Our approach</h2><p>{esc(detail.get("plan", "We agree the goal, create a useful plan and review the work with you before publishing."))}</p>
<h2>What you receive</h2><ul class="tick l">{"".join(f"<li>{esc(i)}</li>" for i in detail.get("deliverables", []))}</ul>
<h2>How we measure progress</h2><p>{esc(detail.get("measure", "We report the platform metrics available and separate them from confirmed business outcomes."))}</p>
<h2>Timeline and approvals</h2><p>{esc(detail.get("timeline", "Timeline depends on the scope, access and approval process. We confirm dates in writing."))}</p>
<h2>Pricing and scope</h2><p>{esc(detail.get("pricing", "Pricing depends on deliverables and complexity. We provide a written quote after reviewing the scope."))}</p>
<h2>What to prepare before kickoff</h2><p>{esc(detail.get("prepare", "Share business goals, approved assets, access and a contact person for approvals."))}</p>'''
        body = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(items)}<h1>{esc(s["h1"])}</h1><p class="lead">{esc(s["intro"])}</p>
<div class="btns"><a class="btn" href="/contact/?service={s["slug"]}" data-cta="hero_enquiry_{s["slug"]}">Discuss this service</a><a class="btn ghost" href="{wa_link("Hi Hei Digi, I would like to talk about "+s["wa"]+".")}" target="_blank" rel="noopener" data-cta="hero_whatsapp_{s["slug"]}">WhatsApp us</a></div></div></section>
<section class="sec"><div class="wrap narrow prose"><h2>What is included</h2><ul class="tick l">{"".join(f"<li>{esc(i)}</li>" for i in s["inc"])}</ul>
<h2>Who this service suits</h2><p>{esc(s["who"])}</p><h2>How we work</h2><ol class="how">{"".join(f"<li>{esc(h)}</li>" for h in s["how"])}</ol>{detail_body}
<aside class="note-box"><b>What we do not promise</b><p>{esc(s["note"])}</p></aside></div></section>
<section class="sec alt"><div class="wrap narrow"><h2>Questions about {esc(s["name"])}</h2>{faq_html(faqs)}</div></section>
<section class="sec"><div class="wrap narrow"><h2>Related services</h2><ul class="rel">{rel}</ul><p><a href="/services/">See all services</a> · <a href="/industries/">Explore industries</a> · <a href="/blog/">Read practical guides</a></p></div></section>{cta_block(s["name"].lower(), s["name"])}</main>'''
        pages[path] = (head(s["title"], s["desc"], path, og(s["slug"], s["h1"], "Hei Digi · Tirupati"), ld) + "<body>" + body + footer(), True)
    items = [("Home", "/"), ("Services", None)]
    cards = "".join(f'<article class="card"><h2 class="h3"><a href="/services/{s["slug"]}/">{esc(s["name"])}</a></h2><p>{esc(s["short"])}</p><a href="/services/{s["slug"]}/" data-cta="hub_{s["slug"]}">Read more<span class="sr"> about {esc(s["name"])}</span></a></article>' for s in S)
    d = "Explore Hei Digi digital marketing services in Tirupati, including SEO, Google Business Profile management, social media marketing, Meta Ads, design and video."
    body = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(items)}<h1>Digital marketing services in Tirupati</h1><p class="lead">Nine services that work together. Start with the one that fixes your biggest gap, or ask us which fits.</p></div></section>
<section class="sec"><div class="wrap"><div class="grid4">{cards}</div><p class="center mut">Not sure where to begin? Most businesses start with a Google Business Profile and a regular social media plan, then add ads once the basics are in place.</p></div></section>{cta_block("which service fits my business")}</main>'''
    pages["/services/"] = (head("Digital Marketing Services in Tirupati | Hei Digi", d, "/services/", og("services", "Digital marketing services", "Hei Digi · Tirupati"), [ORG, bc_ld(items)]) + "<body>" + body + footer(), True)

def client_map_url(name, address=""):
    query = (name + ", " + address) if address else (name + ", " + C["city"] + ", " + C["region"])
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(query)

def client_phone_href(phone):
    # Normalize Indian phone numbers for reliable mobile dialing while retaining display text from the source.
    raw = re.sub(r"[^0-9+]", "", str(phone))
    if raw.startswith("+"):
        return "tel:" + raw
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    elif len(digits) == 12 and digits.startswith("91"):
        pass
    return "tel:+" + digits

def client_card(c):
    name, slug = c["name"], c["slug"]
    logo = "/" + c["logo"].lstrip("/")
    image = f'<img src="{esc(logo)}" alt="{esc(name)} logo" width="240" height="150" loading="lazy" decoding="async">'
    facts = []
    if c.get("address"):
        map_url = client_map_url(name, c["address"])
        facts.append(f'<div class="client-fact"><b>Address</b><span>{esc(c["address"])}</span><a href="{esc(map_url)}" target="_blank" rel="noopener" aria-label="Directions to {esc(name)}">Directions ↗</a></div>')
    if c.get("contacts"):
        rows = " ".join(f'<a href="{esc(client_phone_href(x.get("tel", x["display"]))) }" aria-label="Call {esc(name)}: {esc(x["display"])}">{esc(x["display"])}</a>' for x in c["contacts"])
        labels = " · ".join(esc(x["label"]) for x in c["contacts"] if x.get("label"))
        facts.append(f'<div class="client-fact"><b>Contact</b><span>{rows}</span></div>')
    if c.get("email"):
        facts.append(f'<div class="client-fact"><b>Email</b><a href="mailto:{esc(c["email"])}">{esc(c["email"])}</a></div>')
    if c.get("website"):
        display = re.sub(r"^https?://", "", c["website"]).rstrip("/")
        facts.append(f'<div class="client-fact"><b>Website</b><a href="{esc(c["website"])}" target="_blank" rel="noopener noreferrer">{esc(display)} ↗</a></div>')
    if c.get("instagram"):
        ig = "https://www.instagram.com/" + c["instagram"].strip("@/") + "/"
        facts.append(f'<div class="client-fact"><b>Instagram</b><a href="{esc(ig)}" target="_blank" rel="noopener noreferrer">@{esc(c["instagram"].strip("@/"))} ↗</a></div>')
    if c.get("gstin"):
        facts.append(f'<div class="client-fact"><b>GSTIN</b><span>{esc(c["gstin"])}</span></div>')
    if c.get("company"):
        facts.append(f'<div class="client-fact"><b>Company</b><span>{esc(c["company"])}</span></div>')
    if c.get("branches"):
        branch_items = []
        for b in c["branches"]:
            bmap = client_map_url(name + " - " + b["name"], b.get("address", ""))
            details = f'<p class="branch-address">{esc(b.get("address", ""))}</p>'
            if b.get("details"): details += f'<p class="branch-note">{esc(b["details"])}</p>'
            if b.get("phone"): details += f'<p class="branch-phone">Contact: <a href="{esc(client_phone_href(b["phone"]))}">{esc(b["phone"])}</a></p>'
            details += f'<a class="branch-map" href="{esc(bmap)}" target="_blank" rel="noopener noreferrer">Open branch in Maps ↗</a>'
            branch_items.append(f'<li><b>{esc(b["name"])}</b>{details}</li>')
        summary = f'View {len(c["branches"])} branches and directions'
        facts.append(f'<details class="client-branches"><summary>{summary}</summary><ol>{"".join(branch_items)}</ol></details>')
    loc = c.get("location", C["city"])
    facts_html = "".join(facts) or '<p class="client-fact">Business details will be added when verified.</p>'
    links = []
    if c.get("instagram"):
        links.append(f'<a class="client-action" href="https://www.instagram.com/{esc(c["instagram"].strip("@/"))}/" target="_blank" rel="noopener noreferrer" data-cta="client_instagram_{esc(slug)}">Instagram</a>')
    if c.get("website"):
        links.append(f'<a class="client-action" href="{esc(c["website"])}" target="_blank" rel="noopener noreferrer" data-cta="client_website_{esc(slug)}">Website</a>')
    map_target = client_map_url(name, c.get("address", ""))
    links.append(f'<a class="client-action" href="{esc(map_target)}" target="_blank" rel="noopener noreferrer" data-cta="client_maps_{esc(slug)}">Maps</a>')
    if c.get("contacts"):
        first = c["contacts"][0]
        links.insert(0, f'<a class="client-action primary" href="{esc(client_phone_href(first.get("tel", first["display"]))) }" data-cta="client_call_{esc(slug)}">Call</a>')
    return f'''<article class="card cl" id="client-{esc(slug)}"><div class="pic">{image}</div><div class="body"><p class="client-location">{esc(loc)}</p><h3>{esc(name)}</h3><p class="ind">{esc(c["industry"])}</p><p class="client-desc">{esc(c.get("description", ""))}</p><div class="client-facts">{facts_html}</div><div class="client-actions">{"".join(links)}</div></div></article>'''

def home(P):
    cl = "".join(
        f'<li><img src="/{esc(c["logo"].lstrip("/"))}" width="64" height="44" alt="" aria-hidden="true" loading="lazy" decoding="async"><span>{esc(c["name"])}</span></li>'
        for c in D["clients"]
    )
    mq = f'<div class="ticker"><div class="track" aria-label="Client logos and names scrolling horizontally"><ul aria-label="Client brands">{cl}</ul><ul aria-hidden="true">{cl}</ul></div></div>'
    ccount = {}
    for it in P: ccount[it["client"]] = ccount.get(it["client"], 0) + 1
    cg = "".join(client_card(c) for c in D["clients"])
    sv = "".join(f'<article class="card rv"><h3>{esc(s["name"])}</h3><p>{esc(s["short"])}</p><ul>{"".join(f"<li>{esc(i)}</li>" for i in s["inc"][:3])}</ul><a href="/services/{s["slug"]}/" data-cta="home_service_{s["slug"]}">Explore {esc(s["name"])}</a></article>' for s in S)
    if P:
        wk = "".join(f'<figure class="wk" data-cat="{esc(i["category"])}"><a href="/work/{esc(i["id"])}/">{media(i)}</a><figcaption><b>{esc(i["client"])}</b> {esc(i["category"])}' + (f'<br>{esc(i["description"])}' if i.get("description") else "") + "</figcaption></figure>" for i in P)
        work = f'<div class="filters" id="filters" role="group" aria-label="Filter work by category" hidden></div><div class="masonry" id="portfolio">{wk}</div><p id="wk-empty" class="empty" hidden>No work in this category yet.</p>'
    else:
        work = '<div class="empty"><p><b>Portfolio coming soon.</b></p><p>We publish client work here with each client\'s permission. Ask us for relevant examples for your industry.</p><a class="btn" href="/#contact" data-cta="work_ask">Ask for examples</a></div>'
    st = "".join(f'<li><b>{esc(x["value"])}</b><span>{esc(x["label"])}</span></li>' for x in D["stats"] if x["value"])
    tm = "".join(f'<figure class="tq"><blockquote>{esc(t["quote"])}</blockquote><figcaption>{esc(t["name"])}, {esc(t["company"])}</figcaption></figure>' for t in D["testimonials"]) or '<p class="empty">Client testimonials will appear here once clients approve them.</p>'
    opts = "".join(f'<option value="{s["slug"]}">{esc(s["name"])}</option>' for s in S)
    ind = ["Healthcare", "Education", "Construction", "Steel & Manufacturing", "Hospitality", "Professional Services", "Local Businesses", "Entrepreneurs", "Doctors & Professionals", "Personal Brands"]
    body = f'''{header(True)}<main id="main">
<section id="home" class="hero"><div class="wrap hero-grid"><div><p class="pill">Top Digital Marketing & Local SEO across Tirupati & South Andhra Pradesh</p>
<h1>Top Digital Marketing Agency in <span class="grad">Tirupati.</span></h1><p class="sub">Strategy. Creative. Local visibility. Serving South Andhra Pradesh.</p>
<p class="lead">Hei Digi helps businesses across Tirupati and South Andhra Pradesh—including Srikalahasti, Chittoor, Renigunta, Madanapalle and Nellore—build a dominant online presence through search engine optimization (SEO), Google Business Profile management, social media, Meta Ads, creative video and personal branding. We focus on clear messaging, helpful content and honest reporting rather than ranking promises.</p>
<div class="btns"><a class="btn" href="/#contact" data-cta="hero_start_project">Discuss Your Project</a><a class="btn ghost" href="{wa_link("Hi Hei Digi, I would like to discuss digital marketing for my business.")}" target="_blank" rel="noopener noreferrer" data-cta="hero_whatsapp">WhatsApp Us</a><a class="btn ghost" href="/#clients" data-cta="hero_view_clients">Meet Our Clients</a></div><p class="meta">Working with {esc(D["stats"][0]["value"])} clients · {C["city"]}, {C["region"]}</p></div>
<div class="stage" role="group" aria-label="Real Hei Digi campaign and personal-branding examples"><div class="hero-media-grid">
<a class="hero-media-card coach-reel" href="https://www.instagram.com/coachshri_/" target="_blank" rel="noopener noreferrer" aria-label="View Coach Sri's Instagram profile"><img src="{av('/assets/work/hero-reel.webp')}" alt="Coach Sri speaking in a studio for a short-form video" width="548" height="975" fetchpriority="high"><span class="sc-label">Reels · Coach Sri</span></a>
<a class="hero-media-card lead-case" href="/work/bni-networking-conclave-leads/" aria-label="Read the BNI lead campaign summary"><img src="{av('/assets/work/hero-lead-creative.webp')}" alt="BNI Networking Conclave 2024 campaign artwork reporting 350 on-Facebook leads" width="1000" height="1003" loading="lazy" decoding="async"><span class="sc-label">350 leads · Campaign creative</span></a>
<a class="hero-media-card coach-profile" href="https://www.instagram.com/coachshri_/" target="_blank" rel="noopener noreferrer" aria-label="Open Coach Sri's Instagram profile for the personal branding example"><img src="{av('/assets/work/hero-coach-sri-profile.webp')}" alt="Coach Sri's Instagram profile displaying 27.9K followers and recent Reels" width="691" height="1536" loading="lazy" decoding="async"><span class="sc-label">Personal branding · 3-month engagement</span></a>
<a class="hero-media-card ads-snapshot" href="/services/meta-ads/" aria-label="Explore Hei Digi Meta Ads management"><img src="{av('/assets/work/hero-meta-ads-real.webp')}" alt="Meta Ads Manager campaign performance table for 15 September to 14 October 2026" width="1351" height="611" loading="lazy" decoding="async"><span class="sc-label">Meta Ads · Campaign reporting</span></a>
</div><small class="note">The supplied Instagram profile displays 27.9K followers. The three-month engagement was reported by Hei Digi; a starting baseline was not supplied, so no follower-growth total is claimed. The BNI figures are taken from the supplied campaign creative.</small><p class="case-link"><a href="/work/coach-sri-personal-branding/">Read the Coach Sri personal-branding summary ↗</a></p></div></div></section>
<section class="sec key-facts" aria-labelledby="key-facts-title"><div class="wrap"><h2 id="key-facts-title">Hei Digi at a glance</h2><div class="facts-grid"><p><b>Based in</b><span>Tirupati, Andhra Pradesh</span></p><p><b>Core services</b><span>SEO, Google Business Profile, social media, Meta Ads, creative and video</span></p><p><b>Reporting</b><span>Monthly activity and platform performance reports, where account access is available</span></p><p><b>Contact</b><span><a href="tel:+919705570007">+91 9705570007</a> · <a href="/contact/">Contact and directions</a></span></p></div></div></section>
<section class="marq" aria-labelledby="mq"><div class="wrap center"><h2 id="mq" class="h2s">Working With 13+ Clients</h2><p class="mut">Real client businesses across healthcare, education, construction, hospitality, creative services and more.</p></div>{mq}</section>
<section id="about" class="sec"><div class="wrap two"><div class="rv"><h2>We Don't Just Post. We Build Digital Presence.</h2><p class="mut">Hei Digi is a Tirupati digital marketing agency built around a practical question: what needs to change for the right customer to notice, understand and contact your business? We combine go-to-market thinking, audience research and blue-ocean positioning with clear creative execution.</p><p class="mut">Led by founder Coach Sri, with website development by Gorinta Sandeep Sahay, our work brings SEO, Google Business Profile care, social content, Meta Ads and personal branding into one plan. We do not promise rankings or sales; we report the work and results we can verify.</p><p><a href="/about/">Meet Hei Digi and our process</a></p></div>
<div class="cards3"><article class="card rv"><h3>Creative Thinking</h3><p>Ideas and visuals designed to make brands stand out in a crowded digital landscape.</p></article><article class="card rv"><h3>AI-Powered Execution</h3><p>Modern AI tools that streamline research, ideation, content production and creative workflows.</p></article><article class="card rv"><h3>Growth-Focused Strategy</h3><p>Marketing planned around your goals, audience, positioning and visibility.</p></article></div></div></section>
<section id="services" class="sec alt"><div class="wrap"><h2 class="center rv">Digital Marketing & SEO Services in Tirupati</h2><div class="grid4">{sv}</div><p class="center"><a href="/services/">See all services</a></p></div></section>
<section id="ai" class="sec dark"><div class="wrap"><h2 class="center rv">Where Creativity Meets <span class="grad">AI.</span></h2><p class="center lead rv">AI is not a replacement for creativity. It helps us think bigger, create faster and try new ways to tell your brand's story.</p><ul class="pills"><li>AI video creation</li><li>AI image generation</li><li>Content ideation</li><li>Script development</li><li>Creative concepts</li><li>Marketing research</li></ul><p class="center"><a class="btn ghost" href="/services/video-editing-ai-videos/" data-cta="ai_video_page">See video and AI video services</a></p></div></section>
<section id="clients" class="sec"><div class="wrap"><p class="eyebrow center">Client relationships</p><h2 class="center rv">Our Clients Across Multiple Industries</h2><p class="center mut">Explore client brands, their supplied business details and direct Instagram, website, contact or Google Maps links. Balaram Child Neuro Care and Butterfly Child Developmental Centre is shown as one client with four branches.</p><div class="grid3 clients-grid">{cg}</div></div></section>

<section class="sec"><div class="wrap"><h2 class="center rv">Marketing That Understands Your Industry.</h2><ul class="grid5">{"".join(f"<li><a href=\"/industries/{x["slug"]}/\">{esc(x["name"])}</a></li>" for x in INDUSTRIES)}</ul><p class="center"><a href="/industries/">Explore industry-specific marketing</a></p></div></section>
<section id="impact" class="sec alt"><div class="wrap center"><h2>Built For Visibility. Designed For Growth.</h2><ul class="stats">{st}</ul><p class="mut">{esc(D["industriesLine"])}</p></div></section>
<section id="process" class="sec"><div class="wrap"><h2 class="center rv">From Idea To Impact.</h2><p class="center muted-intro">Go-to-market planning, a clear positioning angle, useful content and performance reviews work together. We decide who the offer is for, why it matters, which channels fit, then adjust from actual data.</p><ol class="steps"><li class="rv"><b>1</b><h3>Discover</h3><p>Understand your business, audience, goals and current presence.</p></li><li class="rv"><b>2</b><h3>Strategize</h3><p>Plan marketing, branding, content and platforms.</p></li><li class="rv"><b>3</b><h3>Create</h3><p>Develop content, visuals, videos and campaigns.</p></li><li class="rv"><b>4</b><h3>Execute</h3><p>Publish, advertise and manage agreed activities.</p></li><li class="rv"><b>5</b><h3>Optimize</h3><p>Review performance and refine the strategy.</p></li></ol></div></section>
<section id="personal-branding" class="sec dark"><div class="wrap two"><div class="rv"><h2>Build A Personal Brand People Remember.</h2><p class="lead">Your expertise deserves more than a profile. We help doctors, founders, entrepreneurs and professionals turn their knowledge into a consistent digital presence.</p><a class="btn" href="/services/personal-branding/" data-cta="home_personal_branding">Explore personal branding</a></div><ul class="tick rv"><li>Instagram personal branding</li><li>LinkedIn content</li><li>Reels and short-form video</li><li>Educational content</li><li>Thought leadership</li><li>Profile optimization</li><li>Content calendars</li></ul></div></section>
<section class="sec"><div class="wrap"><h2 class="center rv">Why Hei Digi?</h2><div class="grid3"><article class="card rv"><h3>Strategy First</h3><p>We start with the business goal, not just the post.</p></article><article class="card rv"><h3>Creative Execution</h3><p>Content designed to capture attention and communicate clearly.</p></article><article class="card rv"><h3>AI + Human Creativity</h3><p>Modern technology with human storytelling and judgment.</p></article><article class="card rv"><h3>Consistent Presence</h3><p>An active, recognizable presence on the right platforms.</p></article><article class="card rv"><h3>Multi-Platform Approach</h3><p>Social media, Google, ads and personal branding working together.</p></article><article class="card rv"><h3>Customized For You</h3><p>Plans built for your business, not a one-size-fits-all template.</p></article></div></div></section>
{("<section id=\"testimonials\" class=\"sec alt\"><div class=\"wrap narrow center\"><h2>Words From Our Clients.</h2>"+tm+"</div></section>") if D["testimonials"] else ""}
<section id="faq" class="sec"><div class="wrap narrow"><h2 class="center">Frequently Asked Questions</h2>{faq_html(HOME_FAQ)}</div></section>
<section id="contact" class="sec dark"><div class="wrap two"><div><h2>Let's Grow Together.</h2><p class="lead">{INTRO}</p>
<p><a href="tel:{PHONE}" data-cta="contact_phone">{C["phoneDisplay"]}</a><br><a href="mailto:{EMAIL}" data-cta="contact_email">{EMAIL}</a></p><address class="office-address">{esc(ADDRESS.get("streetAddress", ""))}, {esc(ADDRESS.get("addressLocality", C["city"]))}, {esc(ADDRESS.get("addressRegion", C["region"]))} {esc(ADDRESS.get("postalCode", ""))}</address><p><a class="btn ghost map-cta" href="{esc(MAPS_URL)}" target="_blank" rel="noopener noreferrer" data-cta="contact_directions">Open address in Google Maps ↗</a></p></div>
<form id="lead" method="post" novalidate><label for="f-name">Your name *</label><input id="f-name" name="name" autocomplete="name" required aria-describedby="e-name"><span class="fe" id="e-name"></span>
<label for="f-phone">Phone *</label><input id="f-phone" name="phone" type="tel" autocomplete="tel" inputmode="tel" required aria-describedby="e-phone"><span class="fe" id="e-phone"></span>
<label for="f-email">Email</label><input id="f-email" name="email" type="email" autocomplete="email" aria-describedby="e-email"><span class="fe" id="e-email"></span>
<label for="f-company">Company</label><input id="f-company" name="company" autocomplete="organization">
<label for="f-service">Service</label><select id="f-service" name="service">{opts}<option value="other">Other</option></select>
<div id="other-wrap"><label for="f-other">If Other, which service? *</label><input id="f-other" name="other" aria-describedby="e-other"><span class="fe" id="e-other"></span></div>
<label for="f-budget">Monthly budget for our fee (optional)</label><select id="f-budget" name="budget"><option value="">Not sure yet</option><option>Under ₹10,000</option><option>₹10,000 to ₹25,000</option><option>₹25,000 to ₹50,000</option><option>Above ₹50,000</option></select>
<label for="f-msg">Message</label><textarea id="f-msg" name="message" rows="3"></textarea>
<div class="hp" aria-hidden="true"><label>Leave this field empty<input name="website" tabindex="-1" autocomplete="off"></label></div>{'<div id="ts"></div>' if TSK else ""}<button class="btn" type="submit" disabled aria-describedby="privacy-note">{"Send enquiry" if LEAD else "Open WhatsApp with my enquiry"}</button><p class="fnote" id="privacy-note">{NOTE} <a href="/privacy/">Privacy Policy</a></p><p id="status" role="status" aria-live="polite" class="status"></p>
<noscript><p>JavaScript is off. Reach us directly: <a href="https://wa.me/{PHONE.lstrip("+")}">WhatsApp</a>, <a href="tel:{PHONE}">call</a> or <a href="mailto:{EMAIL}">email</a>.</p></noscript></form></div></section></main>'''
    ld = [ORG, {"@context": "https://schema.org", "@type": "WebSite", "@id": U("/#website"), "url": U("/"), "name": C["name"], "publisher": {"@id": U("/#org")}}, {"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in HOME_FAQ]}]
    pages["/"] = (head("Top Digital Marketing Agency in Tirupati | Hei Digi",
        "Hei Digi helps Tirupati businesses with SEO, Google Business Profile management, social media, Meta Ads, creative design and monthly performance reporting. Talk to our team.", "/", og("home", "Top Digital Marketing Agency in Tirupati", "Local SEO · Social · Meta Ads · Creative"), ld) + "<body>" + body + footer(), True)
    pages["/404.html"] = (head("Page not found | Hei Digi", "Page not found", "/404.html", "", [], False) + "<body>" + header() + '<main id="main" class="sec top"><div class="wrap narrow center"><h1>Page not found</h1><p>The page you wanted does not exist. Try the <a href="/">homepage</a> or our <a href="/services/">services</a>.</p></div></main>' + footer(), False)

# ---------- public output, sitemap dates and security.txt ----------
def source_files_for(path):
    if path == "/": return ["build.py", "site.config.json", "assets/js/data.js", "assets/css/style.css"]
    if path.startswith("/services/"): return ["build.py", "content/services.py", "content/extended_content.py"]
    if path.startswith("/blog/") or path.startswith("/industries/") or path.startswith("/locations/") or path == "/industries/" or path == "/locations/": return ["build.py", "content/extended_content.py"]
    if path in ("/privacy/", "/terms/", "/cookie-policy/", "/disclaimer/"): return ["build.py", "content/legal.py", "site.config.json"]
    if path == "/contact/" or path == "/about/": return ["build.py", "site.config.json"]
    if path.startswith("/work/"): return ["build.py", "assets/js/data.js", "assets/work/hero-coach-sri-profile.webp"]
    return ["build.py"]
GIT_DATES = {}
def source_lastmod(path, fallback):
    # Prefer the true per-source Git commit date. A downloaded ZIP has no commit history,
    # so fall back to the relevant source file mtime rather than assigning today's date to every URL.
    sources = [src for src in source_files_for(path) if src != "build.py"]
    dates = []
    # Avoid repeated slow Git calls when a ZIP has no .git directory (e.g. Vercel preview or a local extracted archive).
    if (R/".git").exists():
        for src in sources:
            if src not in GIT_DATES:
                try:
                    out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", src], cwd=R, text=True, capture_output=True, timeout=3)
                    d = out.stdout.strip()
                    GIT_DATES[src] = d if (out.returncode == 0 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)) else None
                except (OSError, subprocess.TimeoutExpired):
                    GIT_DATES[src] = None
            if GIT_DATES[src]:
                dates.append(GIT_DATES[src])
    if dates: return max(dates)
    mtimes = []
    for src in sources:
        f = R/src
        if f.is_file(): mtimes.append(datetime.date.fromtimestamp(f.stat().st_mtime).isoformat())
    return max(mtimes) if mtimes else fallback

def write_ai_discovery():
    srv_list = "\n".join(f"- [{s['name']}]({U('/services/' + s['slug'] + '/')}): {s['short']}" for s in S)
    ind_list = "\n".join(f"- [{ind['name']}]({U('/industries/' + ind['slug'] + '/')}): {ind['intro']}" for ind in INDUSTRIES)
    loc_list = "\n".join(f"- [{loc['name']}]({U('/locations/' + loc['slug'] + '/')}): {loc['intro']}" for loc in LOCATIONS)
    blog_list = "\n".join(f"- [{b['title']}]({U('/blog/' + b['slug'] + '/')}): {b['desc']}" for b in BLOGS)
    llms = f"""# {C["name"]}

> {C["name"]} is a premier digital marketing agency located in {C["city"]}, {C["region"]}, India. Founded and led by {C.get("founder", "Coach Sri")}, Hei Digi specializes in Local SEO, Google Business Profile management, Social Media Marketing (Instagram & Facebook), Meta Ads, Creative Design, Content Strategy, Performance Marketing, and Founder Personal Branding for businesses across Tirupati, Srikalahasti, Chittoor, Renigunta, Chandragiri, Madanapalle, Nellore, and the South Andhra Pradesh region.

## Overview & Background

- [About Hei Digi]({U('/about/')}): Agency philosophy, go-to-market strategy, founder {C.get("founder", "Coach Sri")}, and marketing built around customer problems rather than channel tactics.
- [Contact Hei Digi]({U('/contact/')}): Verified office address ({ADDRESS.get("streetAddress", "")}, {ADDRESS.get("addressLocality", C["city"])}, {ADDRESS.get("addressRegion", C["region"])} {ADDRESS.get("postalCode", "")}), phone ({C["phoneDisplay"]}), email ({EMAIL}), WhatsApp and Google Maps directions.

## Core Services

{srv_list}

## Industries Served

{ind_list}

## Service Locations

{loc_list}

## Client Case Studies

- [Coach Sri Personal Branding]({U('/work/coach-sri-personal-branding/')}): Transparent summary of a 3-month personal branding engagement on Instagram.
- [BNI Networking Conclave]({U('/work/bni-networking-conclave-leads/')}): Campaign creative design and lead generation for business networking event.

## Practical Marketing Guides

- [Marketing Guides Hub]({U('/blog/')}): Plain-language guides on local SEO, Google Business Profile, Meta Ads, and reporting.
{blog_list}

## Legal & Compliance Policies

- [Privacy Policy]({U('/privacy/')}): Data protection standards under India's Digital Personal Data Protection Act (DPDPA 2023).
- [Terms & Conditions]({U('/terms/')}): Website terms of use and client engagement agreements.
- [Cookie Policy]({U('/cookie-policy/')}): Storage and consent guidelines.
- [Marketing Disclaimer]({U('/disclaimer/')}): Disclaimers regarding platform results, ad spend separation, and ranking guarantees.
"""
    (R/"llms.txt").write_text(llms, encoding="utf-8")

    full_blocks = [f"# {C['name']} — Comprehensive Digital Marketing Knowledge Base\n\n> Complete authoritative reference for {C['name']}, Tirupati, Andhra Pradesh, India.\n"]
    full_blocks.append("## Business Identity & Contact Information\n")
    full_blocks.append(f"- **Agency Name:** {C['name']}\n- **Founder:** {C.get('founder', 'Coach Sri')}\n- **Address:** {ADDRESS.get('streetAddress', '')}, {ADDRESS.get('addressLocality', C['city'])}, {ADDRESS.get('addressRegion', C['region'])} {ADDRESS.get('postalCode', '')}\n- **Phone:** {C['phoneDisplay']} ({C['phone']})\n- **Email:** {EMAIL}\n- **Website:** {DOM}\n- **Maps Link:** {MAPS_URL}\n")
    
    full_blocks.append("## Detailed Service Specifications\n")
    for s in S:
        full_blocks.append(f"### {s['name']}\n**URL:** {U('/services/' + s['slug'] + '/')}\n\n{s['intro']}\n\n**Included Deliverables:**\n" + "\n".join(f"- {x}" for x in s['inc']) + f"\n\n**Who this is for:** {s['who']}\n\n**Important Note:** {s['note']}\n")
    
    full_blocks.append("## Industry Approaches\n")
    for ind in INDUSTRIES:
        full_blocks.append(f"### {ind['name']}\n**URL:** {U('/industries/' + ind['slug'] + '/')}\n\n{ind['intro']}\n\n**Industry Needs:** {ind['needs']}\n")
    
    full_blocks.append("## Geographic Coverage\n")
    for loc in LOCATIONS:
        full_blocks.append(f"### {loc['name']}\n**URL:** {U('/locations/' + loc['slug'] + '/')}\n\n{loc['intro']}\n")

    full_blocks.append("## Client Case Studies\n")
    full_blocks.append(f"### Coach Sri Personal Branding\n**URL:** {U('/work/coach-sri-personal-branding/')}\n\nTransparent summary of a three-month personal branding engagement on Instagram for Coach Sri, establishing consistent short-form Reel production, thought-leadership positioning, and profile optimization.\n")
    full_blocks.append(f"### BNI Networking Conclave Lead Generation\n**URL:** {U('/work/bni-networking-conclave-leads/')}\n\nCampaign creative design and lead generation summary for business networking event conclave in Andhra Pradesh.\n")

    full_blocks.append("## Practical Marketing Guides\n")
    for b in BLOGS:
        full_blocks.append(f"### {b['title']}\n**URL:** {U('/blog/' + b['slug'] + '/')}\n\n{b['desc']}\n")

    full_blocks.append("## Legal & Regulatory Compliance\n")
    full_blocks.append(f"- **Privacy Policy ({U('/privacy/')}):** Privacy framework compliant with India's Digital Personal Data Protection Act (DPDPA 2023).\n- **Terms of Service ({U('/terms/')}):** Professional service agreement, scope limitations, and transparent billing.\n- **Cookie Policy ({U('/cookie-policy/')}):** Zero third-party trackers before explicit consent.\n- **Marketing Disclaimer ({U('/disclaimer/')}):** Explicit disclaimer separating agency fees from advertising spend; no synthetic ranking or follower guarantees.\n")
    
    (R/"llms-full.txt").write_text("\n".join(full_blocks) + "\n", encoding="utf-8")

    ai_cat = {
        "specVersion": "1.0",
        "host": {
            "displayName": C["name"],
            "identifier": "did:web:" + DOM.split("//")[1],
            "documentationUrl": U("/llms.txt"),
            "logoUrl": U("/assets/icon-512.png")
        },
        "entries": [
            {
                "identifier": f"urn:ai:heidigi.com:service:{s['slug']}",
                "displayName": s["name"],
                "type": "text/html",
                "description": s["short"],
                "url": U(f"/services/{s['slug']}/")
            } for s in S
        ] + [
            {
                "identifier": f"urn:ai:heidigi.com:location:{loc['slug']}",
                "displayName": f"Digital Marketing in {loc['name']}",
                "type": "text/html",
                "description": loc['intro'],
                "url": U(f"/locations/{loc['slug']}/")
            } for loc in LOCATIONS
        ] + [
            {
                "identifier": "urn:ai:heidigi.com:service:contact",
                "displayName": "Contact & Business Consultation",
                "type": "text/html",
                "description": "Direct enquiry and digital marketing consultation for businesses in Tirupati and South Andhra Pradesh.",
                "url": U("/contact/")
            }
        ]
    }
    cat_json = json.dumps(ai_cat, indent=2) + "\n"
    (R/"ai-catalog.json").write_text(cat_json, encoding="utf-8")
    well_known = R/".well-known"; well_known.mkdir(parents=True, exist_ok=True)
    (well_known/"ai-catalog.json").write_text(cat_json, encoding="utf-8")

def copy_public_output():
    dist = R/"dist"
    if dist.exists(): shutil.rmtree(dist)
    dist.mkdir(parents=True)
    # Only built public pages are copied: Python, source JSON, tests, reports and config stay out.
    for path, (markup, indexable) in pages.items():
        rel = Path("404.html") if path == "/404.html" else (Path("index.html") if path == "/" else Path(path.strip("/"))/"index.html")
        target = dist/rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(markup, encoding="utf-8")
    shutil.copytree(R/"assets", dist/"assets", dirs_exist_ok=True)
    for name in ("sitemap.xml", "robots.txt", "manifest.webmanifest", "favicon.ico", "llms.txt", "llms-full.txt", "ai-catalog.json"):
        if (R/name).exists():
            shutil.copy2(R/name, dist/name)
    sec = dist/".well-known"/"security.txt"; sec.parent.mkdir(parents=True, exist_ok=True)
    expires = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    sec.write_text(f"Contact: mailto:{EMAIL}\nPreferred-Languages: en, te\nExpires: {expires}T00:00:00Z\nCanonical: {U('/.well-known/security.txt')}\n", encoding="utf-8")
    if (R/".well-known"/"ai-catalog.json").exists():
        aic = dist/".well-known"/"ai-catalog.json"; aic.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(R/".well-known"/"ai-catalog.json", aic)
    # Do not copy source reports, build scripts, JSON config, API helper files or content databases into dist.
    return dist

# ---------- write ----------
def write():
    state_f = R/".build-state.json"; state = json.loads(state_f.read_text(encoding="utf-8")) if state_f.exists() else {}
    # Remove only stale pages previously generated by this builder, plus their build-state entries.
    for stale in set(state) - set(pages):
        target = R/"404.html" if stale == "/404.html" else R/stale.strip("/")/"index.html" if stale != "/" else R/"index.html"
        try:
            if target.exists(): target.unlink()
            parent = target.parent
            while parent != R and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir(); parent = parent.parent
        except OSError:
            pass
        state.pop(stale, None)
    today = datetime.date.today().isoformat(); urls = []
    for path, (h, idx) in pages.items():
        f = R/"404.html" if path == "/404.html" else R/path.strip("/")/"index.html" if path != "/" else R/"index.html"
        f.parent.mkdir(parents=True, exist_ok=True); f.write_text(h, encoding="utf-8")
        if idx:
            hh = hashlib.sha1(h.encode("utf-8")).hexdigest()
            changed = state.get(path, {}).get("hash") != hh
            prior = state.get(path, {}).get("lastmod", today)
            page_date = source_lastmod(path, today) if changed or not state.get(path) else prior
            state[path] = {"hash": hh, "lastmod": page_date}
            urls.append((path, page_date))
    state_f.write_text(json.dumps(state, indent=1), encoding="utf-8")
    (R/"sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "".join(f"<url><loc>{U(p)}</loc><lastmod>{m}</lastmod></url>\n" for p, m in urls) + "</urlset>\n", encoding="utf-8")
    gpt = "Allow: /" if C["gptbot"] == "allow" else "Disallow: /"
    robots_content = f"""# ─── Hei Digi — robots.txt ───────────────────
# Primary Domain: {DOM}

User-agent: *
Allow: /
Disallow: /api/

# ─── Search Engine Image Crawlers ────────────
User-agent: Googlebot-Image
Allow: /
Allow: /assets/
Allow: /favicon*
Allow: /apple-touch-icon*
Allow: /icon-*

# ─── Major Search Engine Web Crawlers ────────
User-agent: Googlebot
Allow: /
Disallow: /api/

User-agent: Bingbot
Allow: /
Disallow: /api/

User-agent: Applebot
Allow: /
Disallow: /api/

User-agent: DuckDuckBot
Allow: /
Disallow: /api/

User-agent: YandexBot
Allow: /
Disallow: /api/

# ─── AI Search & Answer Engine Crawlers ──────
User-agent: OAI-SearchBot
Allow: /
Disallow: /api/

User-agent: ChatGPT-User
Allow: /
Disallow: /api/

User-agent: GPTBot
{gpt}
Disallow: /api/

User-agent: ClaudeBot
Allow: /
Disallow: /api/

User-agent: anthropic-ai
Allow: /
Disallow: /api/

User-agent: PerplexityBot
Allow: /
Disallow: /api/

User-agent: Google-Extended
Allow: /
Disallow: /api/

User-agent: Applebot-Extended
Allow: /
Disallow: /api/

# ─── Social Media Link Preview Crawlers ──────
User-agent: Twitterbot
Allow: /
Disallow: /api/

User-agent: facebookexternalhit
Allow: /
Disallow: /api/

User-agent: LinkedInBot
Allow: /
Disallow: /api/

User-agent: WhatsApp
Allow: /
Disallow: /api/

User-agent: TelegramBot
Allow: /
Disallow: /api/

Sitemap: {U('/sitemap.xml')}
"""
    (R/"robots.txt").write_text(robots_content, encoding="utf-8")
    (R/"manifest.webmanifest").write_text(json.dumps({
        "name": C["name"], "short_name": C["name"], "start_url": "/", "display": "standalone",
        "background_color": "#0B1F4D", "theme_color": "#0B1F4D",
        "icons": [
            {"src": "/assets/favicon-48x48.png", "sizes": "48x48", "type": "image/png"},
            {"src": "/assets/favicon-96x96.png", "sizes": "96x96", "type": "image/png"},
            {"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }, indent=2) + "\n", encoding="utf-8")
    sec = R/".well-known"/"security.txt"; sec.parent.mkdir(parents=True, exist_ok=True)
    expires = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    sec.write_text(f"Contact: mailto:{EMAIL}\nPreferred-Languages: en, te\nExpires: {expires}T00:00:00Z\nCanonical: {U('/.well-known/security.txt')}\n", encoding="utf-8")
    write_ai_discovery()
    write_headers()
    copy_public_output()
    return urls

def write_config():
    (R/"assets/js/config.js").write_text("window.HEIDIGI_CONFIG=" + json.dumps({"email": EMAIL, "phone": PHONE, "ga4": AN["ga4"], "plausible": AN["plausibleDomain"], "leadEndpoint": LEAD, "turnstileSiteKey": TSK, "services": {s["slug"]: s["name"] for s in S}}) + ";\n", encoding="utf-8")
    (R/"content/services.json").write_text(json.dumps({s["slug"]: s["name"] for s in S}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try: (R/"api/services.json").unlink()
    except FileNotFoundError: pass
    if FONTS: (R/"assets/css/fonts.css").write_text("@font-face{font-family:Inter;font-style:normal;font-weight:400 600;font-display:swap;src:url(/assets/fonts/inter.woff2) format('woff2')}@font-face{font-family:Sora;font-style:normal;font-weight:600 700;font-display:swap;src:url(/assets/fonts/sora.woff2) format('woff2')}", encoding="utf-8")
    elif (R/"assets/css/fonts.css").exists(): (R/"assets/css/fonts.css").unlink()
def headers():
    sc, cn, im, st, fo, fr = ["'self'"], ["'self'"], ["'self'", "data:"], ["'self'"], ["'self'"], []
    if AN["ga4"]: sc.append("https://www.googletagmanager.com"); cn += ["https://*.google-analytics.com", "https://*.analytics.google.com", "https://*.googletagmanager.com"]; im += ["https://*.google-analytics.com", "https://*.googletagmanager.com"]
    if AN["plausibleDomain"]: sc.append("https://plausible.io"); cn.append("https://plausible.io")
    if TSK: sc.append("https://challenges.cloudflare.com"); cn.append("https://challenges.cloudflare.com"); fr.append("https://challenges.cloudflare.com")
    j = " ".join
    csp = "; ".join(["default-src 'self'", "script-src " + j(sc), "style-src " + j(st), "img-src " + j(im), "font-src " + j(fo), "connect-src " + j(cn), "media-src 'self'", "frame-src " + (j(fr) if fr else "'none'"), "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'", "upgrade-insecure-requests"])
    h = [("Content-Security-Policy", csp), ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "strict-origin-when-cross-origin"), ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()"), ("X-Frame-Options", "DENY"), ("Cross-Origin-Opener-Policy", "same-origin"), ("Cross-Origin-Resource-Policy", "same-site")]
    if HSTS > 0: h.append(("Strict-Transport-Security", f"max-age={HSTS}"))  # staged: 300 -> 86400 -> 31536000; no preload until verified
    return h

def write_headers():
    IMM, WEEK = "public, max-age=31536000, immutable", "public, max-age=604800"
    h = headers(); host = DOM.split("//")[1]; alt = host[4:] if host.startswith("www.") else "www." + host
    cache = [("/assets/css/*", IMM), ("/assets/js/*", IMM), ("/assets/fonts/*", WEEK), ("/assets/og/*", WEEK), ("/assets/work/*", WEEK), ("/assets/clients/*", WEEK)]
    (R/"_headers").write_text("# Generated headers for non-Vercel static hosts. Vercel uses vercel.json.\n/*\n" + "".join(f"  {k}: {v}\n" for k, v in h) + "".join(f"{p}\n  Cache-Control: {c}\n" for p, c in cache), encoding="utf-8")
    vc = {"buildCommand": "python3 -m pip install -r requirements.txt && python3 build.py", "outputDirectory": "dist", "cleanUrls": False, "trailingSlash": True,
          "headers": [{"source": "/(.*)", "headers": [{"key": k, "value": v} for k, v in h]}] + [{"source": p.replace("/*", "/(.*)"), "headers": [{"key": "Cache-Control", "value": c}]} for p, c in cache],
          "redirects": [{"source": "/(.*)", "has": [{"type": "host", "value": alt}], "destination": DOM + "/$1", "permanent": True}]}
    (R/"vercel.json").write_text(json.dumps(vc, indent=1) + "\n", encoding="utf-8")
def legal_pages():
    x = dict(email=EMAIL, city=C["city"], region=C["region"], analytics=bool(AN["ga4"] or AN["plausibleDomain"]), ga4=bool(AN["ga4"]), plausible=bool(AN["plausibleDomain"]), api=bool(LEAD), turnstile=bool(TSK), fonts_self=FONTS)
    for slug, title, desc, h1, secs in (("privacy", "Privacy Policy | Hei Digi", "How Hei Digi handles your personal information, enquiries, analytics and cookies on this website.", "Privacy Policy", privacy(x)),
                                        ("terms", "Terms and Conditions | Hei Digi", "Terms for using the Hei Digi website and enquiring about our digital marketing services in Tirupati.", "Terms and Conditions", terms(x))):
        path = f"/{slug}/"; items = [("Home", "/"), (h1, None)]
        body = f'{header()}<main id="main" class="sec top"><div class="wrap narrow prose">{crumbs(items)}<h1>{h1}</h1><p class="mut">Last updated: {UPD}</p>' + "".join(f"<h2>{h}</h2>{b}" for h, b in secs) + "</div></main>"
        pages[path] = (head(title, desc, path, og(slug, h1, "Hei Digi · Tirupati"), [ORG, bc_ld(items)]) + "<body>" + body + footer(), True)

def sections_html(sections):
    return "".join(f"<section><h2>{esc(h)}</h2><p>{esc(txt)}</p></section>" for h, txt in sections)

def make_lead_form():
    opts = "".join(f'<option value="{esc(x["slug"])}">{esc(x["name"])}</option>' for x in S)
    return f'''<form id="lead" method="post" novalidate>
<label for="f-name">Your name *</label><input id="f-name" name="name" autocomplete="name" required aria-describedby="e-name"><span class="fe" id="e-name"></span>
<label for="f-phone">Phone *</label><input id="f-phone" name="phone" type="tel" autocomplete="tel" inputmode="tel" required aria-describedby="e-phone"><span class="fe" id="e-phone"></span>
<label for="f-email">Email</label><input id="f-email" name="email" type="email" autocomplete="email" aria-describedby="e-email"><span class="fe" id="e-email"></span>
<label for="f-company">Business or organisation</label><input id="f-company" name="company" autocomplete="organization">
<label for="f-service">Service you are interested in</label><select id="f-service" name="service">{opts}<option value="other">Other</option></select>
<div id="other-wrap"><label for="f-other">If Other, which service? *</label><input id="f-other" name="other" aria-describedby="e-other"><span class="fe" id="e-other"></span></div>
<label for="f-budget">Monthly budget for our fee (optional)</label><select id="f-budget" name="budget"><option value="">Not sure yet</option><option>Under ₹10,000</option><option>₹10,000 to ₹25,000</option><option>₹25,000 to ₹50,000</option><option>Above ₹50,000</option></select>
<label for="f-msg">What are you trying to improve?</label><textarea id="f-msg" name="message" rows="4"></textarea>
<div class="hp" aria-hidden="true"><label>Leave this field empty<input name="website" tabindex="-1" autocomplete="off"></label></div>{'<div id="ts"></div>' if TSK else ''}<button class="btn" type="submit" disabled aria-describedby="privacy-note">{"Send enquiry" if LEAD else "Open WhatsApp with my enquiry"}</button><p class="fnote" id="privacy-note">{NOTE} <a href="/privacy/">Privacy Policy</a></p><p id="status" role="status" aria-live="polite" class="status"></p>
<noscript><p>JavaScript is off. Reach us directly: <a href="https://wa.me/{PHONE.lstrip('+')}">WhatsApp</a>, <a href="tel:{PHONE}">call</a> or <a href="mailto:{EMAIL}">email</a>.</p></noscript></form>'''

def extra_pages():
    # About page: founder/developer roles are sourced from the user's instruction, not invented credentials.
    about_path = "/about/"
    about_items = [("Home", "/"), ("About Hei Digi", None)]
    about_body = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(about_items)}<p class="eyebrow">How we think</p><h1>Marketing built around the customer, not the channel.</h1><p class="lead">Hei Digi is a Tirupati digital marketing agency combining go-to-market planning, audience research, clear positioning, creative execution and monthly review.</p></div></section>
<section class="sec"><div class="wrap two"><div><h2>Start with the market</h2><p>Before choosing posts or ads, we look at who the business needs to reach, what those people are trying to solve, why they should choose this offer, and what competitors leave unexplained. That is the practical role of go-to-market thinking and blue-ocean positioning: find a useful difference a business can genuinely deliver, then communicate it consistently.</p><p>For some clients the main issue is that local customers cannot find accurate information. For others, their social content does not explain the service, their enquiries are not followed up, or their campaigns need better measurement. The work starts with the actual gap.</p></div><div class="card"><h2>People behind the work</h2><p><b>Founder:</b> Coach Sri</p><p><b>Website developer:</b> Gorinta Sandeep Sahay</p><p>We use agreed approvals and shared reports so the business understands what has been published, changed, spent and learned.</p><p><a href="https://www.instagram.com/coachshri_/" target="_blank" rel="noopener noreferrer">View Coach Sri's public Instagram profile ↗</a></p></div></div></section>
<section class="sec alt"><div class="wrap"><h2>What working together looks like</h2><div class="grid3"><article class="card"><h3>1. Discover</h3><p>Agree the business goal, audience, offer, service area and current constraints.</p></article><article class="card"><h3>2. Plan</h3><p>Choose pages, channels, content, campaign tests and responsibilities that match the goal.</p></article><article class="card"><h3>3. Deliver and learn</h3><p>Publish approved work, review available channel data monthly and decide the next improvements.</p></article></div><p class="mut">We do not guarantee a Google position, follower count, lead volume or revenue. Platform results depend on the offer, competition, budget, response process and factors outside an agency's control.</p></div></section>{cta_block("a practical marketing plan")}</main>'''
    pages[about_path] = (head("About Hei Digi | Digital Marketing in Tirupati", "Meet Hei Digi in Tirupati: go-to-market strategy, audience research, creative execution, local SEO and monthly reviews built around practical business goals.", about_path, og("about", "About Hei Digi", "Go-to-market strategy · Tirupati"), [ORG, bc_ld(about_items), {"@context":"https://schema.org","@type":"AboutPage","name":"About Hei Digi","url":U(about_path),"mainEntity":{"@id":U("/#org")}}]) + "<body>" + about_body + footer(), True)

    # Dedicated contact page: visible NAP, route to Google Maps, call/WhatsApp and working form.
    cp = "/contact/"; ci = [("Home", "/"), ("Contact", None)]
    contact_body = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(ci)}<h1>Talk to Hei Digi in Tirupati</h1><p class="lead">Tell us what you want to improve. We will discuss the business, audience, budget and what can realistically be measured before suggesting a plan.</p></div></section>
<section class="sec"><div class="wrap contact-layout"><div><h2>Contact details</h2><address class="office-address">{esc(ADDRESS.get("streetAddress", ""))}, {esc(ADDRESS.get("addressLocality", C["city"]))}, {esc(ADDRESS.get("addressRegion", C["region"]))} {esc(ADDRESS.get("postalCode", ""))}</address><p><b>Phone:</b> <a href="tel:{PHONE}" data-cta="contact_page_phone">{esc(C["phoneDisplay"])}</a></p><p><b>Email:</b> <a href="mailto:{EMAIL}" data-cta="contact_page_email">{esc(EMAIL)}</a></p><p><a class="btn" href="https://wa.me/{PHONE.lstrip('+')}?text={urllib.parse.quote('Hi Hei Digi, I would like to discuss marketing for my business.')}" target="_blank" rel="noopener noreferrer" data-cta="contact_page_whatsapp"><svg class="whatsapp-icon" viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" d="M16 2.3A13.6 13.6 0 0 0 4.4 23l-1.8 6.5 6.7-1.8A13.7 13.7 0 1 0 16 2.3zm0 24.8c-2.1 0-4.1-.6-5.9-1.7l-.4-.2-3.9 1.1 1.1-3.8-.3-.4A11.2 11.2 0 1 1 16 27.1zm6.2-8.4c-.3-.2-1.8-.9-2.1-1s-.5-.2-.7.2-.8 1-1 1.2-.4.2-.7.1a9.2 9.2 0 0 1-2.7-1.7 10.1 10.1 0 0 1-1.9-2.4c-.2-.3 0-.5.1-.7l.5-.6c.2-.2.2-.4.3-.6.1-.2 0-.4 0-.6s-.7-1.7-1-2.3c-.3-.6-.5-.5-.7-.5h-.6c-.2 0-.6.1-.9.4-.3.3-1.2 1.1-1.2 2.7s1.2 3.1 1.4 3.3c.2.2 2.3 3.6 5.6 5 .8.3 1.4.5 1.9.6.8.3 1.6.2 2.2.1.7-.1 1.8-.7 2.1-1.4.3-.7.3-1.3.2-1.4-.1-.1-.3-.2-.6-.4z"/></svg> Chat on WhatsApp</a></p><p><a class="btn ghost contact-map" href="{esc(MAPS_URL)}" target="_blank" rel="noopener noreferrer" data-cta="contact_page_directions">Get directions in Google Maps ↗</a></p><p class="mut">Map directions open in Google Maps. Opening hours should be confirmed by the business before they are published.</p></div><div><h2>Tell us about your business</h2><p class="mut">We use these details to respond to your enquiry. Do not include passwords, identity numbers or confidential patient/customer information.</p>{make_lead_form()}</div></div></section></main>'''
    pages[cp] = (head("Contact Hei Digi in Tirupati | Call, WhatsApp & Directions", "Contact Hei Digi in Tirupati for SEO, Google Business Profile management, social media, Meta Ads and web enquiries. Call, WhatsApp or get directions.", cp, og("contact", "Contact Hei Digi", "Tirupati · Andhra Pradesh"), [ORG, bc_ld(ci), {"@context":"https://schema.org","@type":"ContactPage","name":"Contact Hei Digi","url":U(cp),"mainEntity":{"@id":U("/#org")}}]) + "<body>" + contact_body + footer(), True)

    # Blog index and 10 useful articles; articles are source-driven and included in sitemap.
    bi = "/blog/"; bcrumb = [("Home", "/"), ("Marketing guides", None)]
    bc = "".join(f'<article class="card"><p class="eyebrow">Practical guide</p><h2 class="h3"><a href="/blog/{esc(b["slug"])}/">{esc(b["title"])}</a></h2><p>{esc(b["desc"])}</p><a href="/blog/{esc(b["slug"])}/">Read the guide ↗</a></article>' for b in BLOGS)
    blog_body = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(bcrumb)}<h1>Practical marketing guides for local businesses</h1><p class="lead">Plain-language guides on local SEO, Google Business Profile, Meta Ads, content and monthly reporting. We focus on implementation and honest measurement, not ranking promises.</p></div></section><section class="sec"><div class="wrap"><div class="grid3 blog-grid">{bc}</div></div></section>{cta_block("your next marketing improvement")}</main>'''
    pages[bi] = (head("Digital Marketing Guides for Tirupati Businesses | Hei Digi", "Read practical guides from Hei Digi on local SEO, Google Business Profile, Meta Ads, school admissions, healthcare content and monthly marketing reports.", bi, og("blog", "Marketing guides for local businesses", "Hei Digi · Tirupati"), [ORG, bc_ld(bcrumb), {"@context":"https://schema.org","@type":"CollectionPage","name":"Hei Digi Marketing Guides","url":U(bi),"mainEntity":{"@type":"ItemList","itemListElement":[{"@type":"ListItem","position":i+1,"url":U('/blog/'+b['slug']+'/'),"name":b['title']} for i,b in enumerate(BLOGS)]}}]) + "<body>" + blog_body + footer(), True)
    for b in BLOGS:
        path = "/blog/" + b["slug"] + "/"; items = [("Home", "/"), ("Marketing guides", "/blog/"), (b["title"], None)]
        paras = "".join(f"<section><h2>{esc(h)}</h2><p>{esc(txt)}</p></section>" for h, txt in b["sections"])
        article_body = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(items)}<p class="eyebrow">Hei Digi guide · Tirupati</p><h1>{esc(b["title"])}</h1><p class="lead">{esc(b["desc"])}</p></div></section><article class="sec"><div class="wrap narrow prose"><p class="article-intro">This guide is intended to help business owners make a useful next decision. Check platform settings and legal requirements at the time you implement a recommendation.</p>{paras}<p class="note-box"><b>How Hei Digi approaches this:</b> start with the customer, keep business information accurate, measure actions in context and report what is known separately from what is assumed.</p><p><a href="/services/seo/">Explore SEO services</a> · <a href="/services/google-business-profile-management/">Google Business Profile management</a> · <a href="/contact/">Talk to Hei Digi</a></p></div></article></main>'''
        article_ld = {"@context":"https://schema.org","@type":"Article","headline":b["title"],"description":b["desc"],"mainEntityOfPage":{"@type":"WebPage","@id":U(path)},"author":{"@type":"Organization","name":"Hei Digi","url":U("/")},"publisher":{"@id":U("/#org")},"image":U(og("blog-"+b["slug"],b["title"],"Hei Digi · Practical guide"))}
        pages[path] = (head(b["title"] + " | Hei Digi", b["desc"], path, "/assets/og/blog-" + b["slug"] + ".jpg", [ORG, bc_ld(items), article_ld]) + "<body>" + article_body + footer(), True)

    # Industries index and unique pages.
    ii = "/industries/"; itemb = [("Home", "/"), ("Industries", None)]
    ic = "".join(f'<article class="card"><h2 class="h3"><a href="/industries/{esc(i["slug"])}/">{esc(i["name"])}</a></h2><p>{esc(i["intro"])}</p><a href="/industries/{esc(i["slug"])}/">Explore this industry ↗</a></article>' for i in INDUSTRIES)
    ibody = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(itemb)}<h1>Digital marketing for Tirupati industries</h1><p class="lead">Different businesses need different messages, approval processes and measures of success. Choose the industry to see a relevant approach.</p></div></section><section class="sec"><div class="wrap"><div class="grid3">{ic}</div></div></section>{cta_block("industry-specific marketing support")}</main>'''
    pages[ii] = (head("Industry-Specific Digital Marketing | Hei Digi Tirupati", "Explore marketing approaches for healthcare, education, steel and construction, hospitality and professional services in and around Tirupati.", ii, og("industries", "Marketing by industry", "Hei Digi · Tirupati"), [ORG, bc_ld(itemb), {"@context":"https://schema.org","@type":"CollectionPage","name":"Industries served by Hei Digi","url":U(ii)}]) + "<body>" + ibody + footer(), True)
    for ind in INDUSTRIES:
        path = "/industries/" + ind["slug"] + "/"; items=[("Home","/"),("Industries","/industries/"),(ind["name"],None)]
        rel = "".join(f'<li><a href="/services/{slug}/">{esc(BYSLUG[slug]["name"])}</a></li>' for slug in ind["services"] if slug in BYSLUG)
        faq = ind.get("faq", [])
        visible = faq_html(faq)
        body = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(items)}<h1>{esc(ind["name"])} in Tirupati</h1><p class="lead">{esc(ind["intro"])}</p></div></section><section class="sec"><div class="wrap narrow prose"><h2>What this industry needs</h2><p>{esc(ind["needs"])}</p><h2>Services that may fit</h2><ul class="rel">{rel}</ul><h2>Planning and approvals</h2><p>Before launch, agree the audience, offer, service area, content owner, approval process, enquiry destination and reporting period. Sector-specific claims, client imagery and contact details should be approved by the business responsible for them.</p></div></section><section class="sec alt"><div class="wrap narrow"><h2>Frequently asked questions</h2>{visible}</div></section>{cta_block(ind["name"].lower())}</main>'''
        il = [ORG, bc_ld(items), {"@context":"https://schema.org","@type":"WebPage","name":ind["name"],"url":U(path)}]
        if faq: il.append({"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":q,"acceptedAnswer":{"@type":"Answer","text":a}} for q,a in faq]})
        pages[path] = (head(ind["title"], ind["desc"], path, og("industry-"+ind["slug"], ind["title"], "Hei Digi · Tirupati"), il) + "<body>" + body + footer(), True)

    # Location pages are individually written in extended_content.py, not duplicated city-name swaps.
    li = "/locations/"; locitems=[("Home","/"),("Service areas",None)]
    lc = "".join(f'<article class="card"><h2 class="h3"><a href="/locations/{esc(loc["slug"])}/">Digital marketing in {esc(loc["name"])}</a></h2><p>{esc(loc["intro"])}</p><a href="/locations/{esc(loc["slug"])}/">Read local information ↗</a></article>' for loc in LOCATIONS)
    lbody = f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(locitems)}<h1>Digital Marketing Across South Andhra Pradesh</h1><p class="lead">Hei Digi serves businesses across the greater Tirupati region and key South Andhra Pradesh commercial corridors. We provide real local market strategies tailored to each area's unique business context.</p></div></section><section class="sec"><div class="wrap"><div class="grid3">{lc}</div></div></section>{cta_block("local marketing in your service area")}</main>'''
    pages[li] = (head("Digital Marketing in Tirupati & South AP | Hei Digi", "Explore digital marketing services across Tirupati and South Andhra Pradesh, including Chittoor, Srikalahasti, Renigunta, Madanapalle and Nellore hubs.", li, og("locations", "Hei Digi service areas", "South Andhra Pradesh"), [ORG, bc_ld(locitems), {"@context":"https://schema.org","@type":"CollectionPage","name":"Hei Digi service areas","url":U(li)}]) + "<body>" + lbody + footer(), True)
    for loc in LOCATIONS:
        path="/locations/"+loc["slug"]+"/"; items=[("Home","/"),("Service areas","/locations/"),(loc["name"],None)]
        body=f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(items)}<h1>Digital marketing in {esc(loc["name"])}</h1><p class="lead">{esc(loc["intro"])}</p></div></section><article class="sec"><div class="wrap narrow prose">{sections_html(loc["sections"])}<p><a href="/services/seo/">SEO services</a> · <a href="/services/google-business-profile-management/">Google Business Profile</a> · <a href="/contact/">Contact Hei Digi</a></p></div></article>{cta_block("marketing support in "+loc["name"])}</main>'''
        pages[path]=(head(loc["title"],loc["desc"],path,og("location-"+loc["slug"],loc["title"],"Hei Digi · Andhra Pradesh"),[ORG,bc_ld(items),{"@context":"https://schema.org","@type":"WebPage","name":loc["title"],"url":U(path)}])+"<body>"+body+footer(),True)

    # Legal documents beyond the privacy/terms pages. The privacy/legal text should be reviewed by an Indian lawyer before launch.
    for slug, title, desc, h1, secs in [
      ("cookie-policy", "Cookie Policy | Hei Digi", "Learn how Hei Digi uses cookies and browser storage for consent and optional website analytics.", "Cookie Policy", [
       ("What this site uses", "The site uses essential browser storage only when needed to remember a privacy or analytics choice. Analytics is disabled by default in this build because no GA4 or Plausible ID has been supplied. If analytics is enabled later, the consent banner must remain active and analytics scripts must not load before consent."),
       ("Third-party services", "If enabled, Google Analytics or Plausible may receive page-view or event data under their own terms. The WhatsApp button opens WhatsApp only after you click it. Third-party services have their own policies and settings."),
       ("Managing your choice", "You can decline optional analytics. If the consent banner is enabled, use the Privacy settings link in the footer to change your choice. You can also clear website data in your browser settings."),
       ("Contact", f"Questions about cookies or measurement? Email {EMAIL}.")]),
      ("disclaimer", "Marketing Services Disclaimer | Hei Digi", "Read Hei Digi's disclaimer about search visibility, advertising results, analytics and third-party platforms.", "Marketing Services Disclaimer", [
       ("No ranking or performance guarantee", "Search rankings, map visibility, social reach, leads, sales and return on ad spend depend on the business offer, competition, budget, platform rules, tracking and response process. Hei Digi does not guarantee a specific Google position, follower count, lead total, sale or revenue."),
       ("Metrics and examples", "Campaign screenshots and supplied client examples are snapshots from particular contexts. They are not a prediction of future performance. Platform-reported messages, clicks or form submissions are not automatically qualified leads or sales. We state the period and known limitations where results are shown."),
       ("Third-party platforms", "Google, Meta, Instagram, WhatsApp and other platforms can change interfaces, policies, delivery, reporting and eligibility. We cannot control their systems or decisions."),
       ("Professional advice", "Website information is general and is not legal, medical, financial or other regulated professional advice. Clients remain responsible for verifying their claims and approving content before publication."),
       ("Corrections and contact", f"If you see a factual error, contact {EMAIL} and describe the page and correction.")])]:
        path="/"+slug+"/"; items=[("Home","/"),(h1,None)]
        body=f'''{header()}<main id="main" class="sec top"><div class="wrap narrow prose">{crumbs(items)}<h1>{esc(h1)}</h1><p class="mut">Last updated: {esc(UPD)}</p>{sections_html(secs)}</div></main>'''
        pages[path]=(head(title,desc,path,og(slug,h1,"Hei Digi · Tirupati"),[ORG,bc_ld(items)])+"<body>"+body+footer(),True)

    # Coach Sri personal-branding summary based only on the submitted profile screenshot and user's stated project period.
    coach_path="/work/coach-sri-personal-branding/"; coach_items=[("Home","/"),("Client example",None)]
    coach_body=f'''{header()}<main id="main"><section class="phero"><div class="wrap narrow">{crumbs(coach_items)}<p class="eyebrow">Personal branding · Coach Sri</p><h1>A consistent personal-branding presence for Coach Sri</h1><p class="lead">The supplied Instagram profile shows an active founder-led content presence. Hei Digi reports a three-month personal-branding engagement for this work.</p></div></section><article class="sec"><div class="wrap narrow prose"><img src="/assets/work/hero-coach-sri-profile.webp" width="691" height="1536" alt="Coach Sri's Instagram profile and recent public Reels" loading="lazy" decoding="async"><h2>Objective</h2><p>Build a recognisable founder-led presence around entrepreneurship, business coaching and practical ideas, using content themes that people can recognise from one post to the next.</p><h2>Work focus</h2><ul><li>Clarify the personal profile and main audience.</li><li>Plan recurring themes and short-form content formats.</li><li>Use a repeatable filming, editing and publishing routine.</li><li>Review available audience signals and adjust future topics.</li></ul><h2>What the public snapshot verifies</h2><p>The supplied profile screenshot displays 27.9K followers at the time it was captured. The user reports a three-month project period. A verified starting follower count and dated before-and-after analytics were not supplied, so this page does not claim a specific follower increase or attribute every current follower to Hei Digi.</p><p><a href="https://www.instagram.com/coachshri_/" target="_blank" rel="noopener noreferrer">View the public Coach Sri Instagram profile ↗</a></p><p>Results depend on topic fit, publishing cadence, creator participation and platform distribution. This example is not a guarantee of future outcomes.</p></div></article>{cta_block("personal branding")}</main>'''
    coach_ld=[ORG,bc_ld(coach_items),{"@context":"https://schema.org","@type":"CreativeWork","name":"Coach Sri personal-branding summary","url":U(coach_path),"creator":{"@id":U("/#org")},"image":U("/assets/work/hero-coach-sri-profile.webp")}]
    pages[coach_path]=(head("Coach Sri Personal Branding Summary | Hei Digi", "A transparent summary of Hei Digi's reported three-month personal-branding engagement for Coach Sri, with the public profile snapshot and its limitations.", coach_path, og("coach-sri-personal-branding","Coach Sri personal branding","Hei Digi · Tirupati"),coach_ld)+"<body>"+coach_body+footer(),True)

    # Provide an actual privacy-related entry for the human contact route; no placeholder facts are surfaced.
    # Keep a single public case-story route for the BNI creative and avoid a general Our Work grid.
    bni = next((x for x in D["portfolio"] if x["id"] == "bni-networking-conclave-leads"), None)
    if bni and "/work/bni-networking-conclave-leads/" in pages:
        # Replace its content with source-qualified reporting. The visible source artwork is the only basis for the campaign numbers.
        pass

write_config(); P = prep_portfolio(); icons()
home(P); service_pages(); work_pages(P); legal_pages(); extra_pages(); urls = write()
print("pages:", len(urls)); print("warnings:", WARN or "none")

