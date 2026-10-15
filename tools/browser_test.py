"""Browser test (needs playwright + chromium): python3 tools/browser_test.py"""
import json, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent)); from _server import serve
from pathlib import Path
from playwright.sync_api import sync_playwright
R = Path(__file__).resolve().parent.parent
srv = serve(8123)
B = "http://127.0.0.1:8123"; res = []; 
def ck(c, m): res.append((bool(c), m))
with sync_playwright() as p:
    br = p.chromium.launch()
    for name, vp in (("mobile", {"width": 390, "height": 844}), ("desktop", {"width": 1366, "height": 800})):
        ctx = br.new_context(viewport=vp, is_mobile=name == "mobile"); pg = ctx.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
        bad = []; pg.on("response", lambda r: bad.append(r.url) if r.status >= 400 and "127.0.0.1" in r.url else None)
        for path in ["/", "/services/", "/services/meta-ads/", "/404.html"]:
            pg.goto(B + path, wait_until="load"); 
            ck(pg.evaluate("document.documentElement.scrollWidth <= innerWidth+1"), f"{name} {path}: no horizontal overflow")
        ck(not [e for e in errs if "fonts.g" not in e and "ERR_" not in e], f"{name}: console errors {errs}")
        ck(not bad, f"{name}: 4xx {bad}")
        pg.goto(B + "/"); pg.screenshot(path=f"/tmp/{name}_home.png"); 
        if name == "mobile":
            ck(pg.evaluate("document.getElementById('nav').hasAttribute('inert')"), "mobile: nav inert when closed")
            pg.click("#burger"); ck(pg.evaluate("document.getElementById('burger').getAttribute('aria-expanded')") == "true" and pg.evaluate("!document.getElementById('nav').hasAttribute('inert')"), "mobile: menu opens")
            pg.screenshot(path="/tmp/mobile_menu.png"); pg.keyboard.press("Escape")
            ck(pg.evaluate("document.activeElement.id") == "burger" and pg.evaluate("!document.body.classList.contains('open')"), "mobile: Escape closes and returns focus")
            pg.click("#burger"); pg.click("#nav a[href='/#services']".replace("#services", "#about")); pg.wait_for_timeout(400)
            ck(pg.evaluate("!document.body.classList.contains('open')"), "mobile: link click closes menu")
        # form
        pg.goto(B + "/?service=branding#contact"); ck(pg.eval_on_selector("#f-service", "e=>e.value") == "branding", f"{name}: service preselected from URL")
        ck(pg.is_hidden("#other-wrap"), f"{name}: Other field hidden by default")
        pg.select_option("#f-service", "other"); ck(pg.is_visible("#other-wrap"), f"{name}: Other field shows")
        pg.evaluate("window.__opened=[];window.open=function(u){if(u&&String(u).indexOf('wa.me')>-1)window.__opened.push(u);return null}")
        pg.click("#lead button[type=submit]"); ck(pg.evaluate("window.__opened.length") == 0, f"{name}: invalid form does not open WhatsApp")
        ck(pg.inner_text("#e-name") and pg.inner_text("#e-phone") and pg.inner_text("#e-other"), f"{name}: inline errors shown")
        ck(pg.evaluate("document.activeElement.id") == "f-name", f"{name}: focus moves to first error")
        pg.fill("#f-name", "Ravi"); pg.fill("#f-phone", "98765 43210"); pg.fill("#f-email", "ravi@example.com"); pg.fill("#f-company", "Test Co"); pg.fill("#f-other", "Podcast editing"); pg.select_option("#f-budget", index=2); pg.fill("#f-msg", "Hello")
        pg.click("#lead button[type=submit]"); o = pg.evaluate("window.__opened")
        ck(len(o) == 1 and o[0].startswith("https://wa.me/919705570007?text="), f"{name}: WhatsApp URL opened")
        txt = __import__("urllib.parse").parse.unquote(o[0].split("text=")[1]) if o else ""
        ck(all(k in txt for k in ("Ravi", "Test Co", "ravi@example.com", "Other: Podcast editing", "Budget", "Hello")), f"{name}: message has all fields")
        ck("does not store" in pg.inner_text("#status") and "mailto:" in pg.inner_html("#status"), f"{name}: honest status + fallbacks")
        # tracking
        pg.evaluate("window.dataLayer.length=0"); pg.click("a[href^='tel:'] >> nth=0"); ck(True, "")
        # no-JS content
        c2 = br.new_context(java_script_enabled=False, viewport=vp); p2 = c2.new_page(); p2.goto(B + "/")
        ck(p2.is_visible("text=Metro Steel >> nth=0") and p2.is_visible("#about h2") and p2.is_visible("#faq summary >> nth=0"), f"{name}: content visible with JS disabled")
        ck(p2.get_attribute("#lead", "method") == "post" and p2.is_disabled("#lead button[type=submit]"), f"{name}: no-JS form cannot submit personal data as a GET URL")
        ck(p2.evaluate("document.documentElement.scrollWidth <= innerWidth+1"), f"{name}: no-JS no overflow"); p2.screenshot(path=f"/tmp/{name}_nojs.png"); c2.close()
        # reduced motion
        c3 = br.new_context(reduced_motion="reduce", viewport=vp); p3 = c3.new_page(); p3.goto(B + "/")
        ck(p3.evaluate("getComputedStyle(document.querySelector('.track')).animationName") == "none", f"{name}: marquee animation off in reduced motion"); c3.close()
        # perf-ish
        m = pg.evaluate("performance.getEntriesByType('navigation')[0].toJSON()"); ck(True, "")
        ctx.close()
    # services page nav back to home sections
    ctx = br.new_context(viewport={"width": 1366, "height": 800}); pg = ctx.new_page(); pg.goto(B + "/services/meta-ads/"); pg.click("header nav a[href='/#clients']"); pg.wait_for_load_state("load"); pg.wait_for_timeout(1500)
    ck(pg.url.endswith("/#clients") and pg.evaluate("document.getElementById('clients').getBoundingClientRect().top < 200"), "service page -> home section navigation")
    br.close()
bad = [m for ok, m in res if not ok]; print(f"{sum(1 for ok,m in res if ok and m)} browser checks passed; {len(bad)} failed"); [print(" FAIL", m) for m in bad]; sys.exit(1 if bad else 0)
