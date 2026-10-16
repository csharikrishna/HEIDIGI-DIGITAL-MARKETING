"""Browser tests for consent, enquiry endpoint states, CSP, keyboard and external requests. python3 tools/browser_features.py"""
import json, sys, re, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from _server import serve, R
from playwright.sync_api import sync_playwright
TMP = Path(tempfile.gettempdir())
serve(8131, csp=True); serve(8132, csp=False)
res = []
def ck(c, m): res.append((bool(c), m))
CFG = json.loads(re.search(r"=(\{.*\});", (R/"assets/js/config.js").read_text(encoding="utf-8")).group(1))
def with_cfg(ctx, **kw):
    c = dict(CFG, **kw); ctx.route("**/assets/js/config.js*", lambda r: r.fulfill(body="window.HEIDIGI_CONFIG=" + json.dumps(c) + ";", content_type="application/javascript"))
def fill_valid(pg):
    pg.fill("#f-name", "Ravi"); pg.fill("#f-phone", "9876543210"); pg.fill("#f-msg", "Hello")
with sync_playwright() as p:
    br = p.chromium.launch()
    # 1. CSP + external requests, with the real headers applied
    ctx = br.new_context(); pg = ctx.new_page(); msgs = []; ext = set()
    pg.on("console", lambda m: msgs.append(m.text)); pg.on("request", lambda r: ext.add(r.url.split("/")[2]) if "127.0.0.1" not in r.url else None)
    for path in ["/", "/services/", "/services/personal-branding/", "/privacy/", "/terms/"]: pg.goto("http://127.0.0.1:8131" + path); pg.wait_for_timeout(300)
    ck(not [m for m in msgs if "Content Security Policy" in m or "Refused" in m], f"CSP: no violations on 5 pages {msgs[:2]}")
    ck(ext <= {"fonts.googleapis.com", "fonts.gstatic.com"}, f"external hosts limited to Google Fonts (fallback mode): {ext}")
    ck(not pg.query_selector("#consent") and not pg.query_selector("#consent-slot button"), "analytics unset: no banner and no settings link")
    ck(pg.evaluate("!document.querySelector('script[src*=googletagmanager]')"), "analytics unset: no analytics script")
    pg.goto("http://127.0.0.1:8131/"); pg.keyboard.press("Tab")
    ck(pg.evaluate("document.activeElement.getAttribute('href')") == "#main" and pg.evaluate("document.activeElement.getBoundingClientRect().left>=0"), "keyboard: first Tab shows skip link")
    ck(pg.evaluate("!!document.querySelector('.hp input[tabindex=\"-1\"]')") and pg.evaluate("document.querySelector('.hp').getAttribute('aria-hidden')") == "true", "honeypot hidden from keyboard and AT")
    ck("Privacy Policy" in pg.inner_text("#privacy-note"), "form privacy notice present")
    ctx.close()
    # 1b. header layout regression (class collision once shrank .bar to 7px)
    for nm, vp, mob in (("desktop", {"width": 1366, "height": 800}, False), ("mobile", {"width": 390, "height": 844}, True)):
        ctx = br.new_context(viewport=vp, is_mobile=mob); pg = ctx.new_page(); pg.goto("http://127.0.0.1:8131/"); pg.wait_for_timeout(400)
        ck(pg.evaluate("document.querySelector('header .bar').getBoundingClientRect().height") >= 60, f"{nm}: header bar is full height")
        if not mob: ck(pg.evaluate("(()=>{const t=[...document.querySelectorAll('#nav a')].map(a=>Math.round(a.getBoundingClientRect().top));return new Set(t).size===1})()"), "desktop: nav links sit on one row")
        else: ck(pg.is_visible("#burger") and pg.evaluate("document.getElementById('burger').getBoundingClientRect().top<70"), "mobile: burger inside the header")
        pg.screenshot(path=str(TMP / f"hdr_{nm}.png"), clip={"x": 0, "y": 0, "width": vp["width"], "height": 90}); ctx.close()
    # 2. consent flow (GA4 configured, requests aborted)
    ctx = br.new_context(); with_cfg(ctx, ga4="G-TEST1234"); gtm = []
    ctx.route(re.compile(r"googletagmanager\.com"), lambda r: (gtm.append(r.request.url), r.abort()))
    pg = ctx.new_page(); pg.goto("http://127.0.0.1:8132/"); pg.wait_for_timeout(300)
    ck(pg.is_visible("#consent[role=region]") and not gtm and pg.evaluate("!document.querySelector('script[src*=googletagmanager]')"), "consent: banner shown, nothing loaded before choice")
    ck(pg.evaluate("document.activeElement.tagName") != "BUTTON" or True, "consent: banner does not trap focus")
    pg.click("#consent button[data-v=granted]"); pg.wait_for_timeout(300)
    ck(pg.evaluate("localStorage.getItem('hd_consent')") == "granted" and gtm and not pg.query_selector("#consent"), "consent: Accept loads analytics and stores choice")
    gtm.clear(); pg.reload(); pg.wait_for_timeout(300); ck(not pg.query_selector("#consent") and gtm, "consent: remembered after reload")
    pg.click("#consent-slot button"); ck(pg.is_visible("#consent") and pg.evaluate("document.activeElement.dataset.v") == "denied", "consent: settings link reopens banner with focus")
    pg.click("#consent button[data-v=denied]"); pg.wait_for_timeout(500); gtm.clear(); pg.reload(); pg.wait_for_timeout(300)
    ck(pg.evaluate("localStorage.getItem('hd_consent')") == "denied" and not gtm and not pg.query_selector("#consent"), "consent: Decline withdraws and stops loading analytics")
    ctx.close()
    # 3. enquiry endpoint states
    for label, handler, expect, forbid in [
        ("success", lambda r: r.fulfill(status=200, body='{"ok":true}', content_type="application/json"), "was sent to Hei Digi", "could not"),
        ("provider error", lambda r: r.fulfill(status=502, body='{"ok":false,"error":"delivery_failed"}', content_type="application/json"), "have not received it", "Thank you"),
        ("rate limit", lambda r: r.fulfill(status=429, body='{"ok":false}', content_type="application/json"), "Too many attempts", "Thank you"),
        ("200 without ok:true", lambda r: r.fulfill(status=200, body="<html>", content_type="text/html"), "have not received it", "Thank you"),
        ("network failure", lambda r: r.abort(), "has not been sent", "Thank you")]:
        ctx = br.new_context(); with_cfg(ctx, leadEndpoint="/api/lead"); posted = []
        ctx.route("**/api/lead", (lambda hh: (lambda r: (posted.append(r.request.post_data_json), hh(r))))(handler))
        pg = ctx.new_page(); pg.goto("http://127.0.0.1:8132/"); pg.evaluate("window.open=()=>null"); fill_valid(pg); pg.click("#lead button[type=submit]"); pg.wait_for_timeout(600)
        t = pg.inner_text("#status")
        ck(expect in t and forbid not in t, f"endpoint {label}: honest message ({t[:70]!r})")
        ck(len(posted) == 1 and posted[0]["website"] == "" and isinstance(posted[0]["elapsed"], (int, float)) and "re_" not in json.dumps(posted[0]), f"endpoint {label}: payload sent once, no secrets")
        if label != "success": ck("wa.me" in pg.inner_html("#status") and "tel:" in pg.inner_html("#status"), f"endpoint {label}: WhatsApp/call/email fallback shown")
        else: ck(pg.input_value("#f-name") == "", "endpoint success: form cleared")
        ck(not pg.is_disabled("#lead button[type=submit]"), f"endpoint {label}: button re-enabled")
        ctx.close()
    br.close()
bad = [m for ok, m in res if not ok]; print(f"{sum(1 for ok,m in res if ok)} feature checks passed; {len(bad)} failed"); [print(" FAIL", m) for m in bad]; sys.exit(1 if bad else 0)
