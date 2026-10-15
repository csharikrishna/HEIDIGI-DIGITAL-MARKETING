"""Crawl the built site over HTTP: every internal page, link, script, stylesheet, image, font and sitemap URL must return 200. python3 tools/crawl_links.py"""
import re, sys, urllib.request, urllib.error
from html.parser import HTMLParser
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from _server import serve, R
serve(8133, csp=False); B = "http://127.0.0.1:8133"
def get(u):
    try:
        with urllib.request.urlopen(B + u) as r: return r.status, r.read().decode("utf-8", "ignore") if "text" in r.headers.get("Content-Type", "") or "javascript" in r.headers.get("Content-Type", "") else ""
    except urllib.error.HTTPError as e: return e.code, ""
class L(HTMLParser):
    def __init__(s): super().__init__(); s.u = set()
    def handle_starttag(s, t, a):
        a = dict(a)
        for k in ("href", "src"):
            if k in a and a[k].startswith("/"): s.u.add(a[k].split("#")[0])
        if "srcset" in a: s.u.update(x.strip().split(" ")[0] for x in a["srcset"].split(","))
seen, todo, bad = set(), ["/"], []
sm = re.findall(r"<loc>https?://[^/]+(/[^<]*)</loc>", (R/"sitemap.xml").read_text()); todo += sm
while todo:
    u = todo.pop()
    if u in seen or not u: continue
    seen.add(u); code, body = get(u)
    if code != 200: bad.append((u, code)); continue
    if u.endswith("/") or u.endswith(".html"):
        p = L(); p.feed(body); todo += [x for x in p.u if x not in seen]
    if u.endswith(".css"): todo += [m for m in re.findall(r"url\((/[^)]+?)\)", body)]
code, _ = get("/definitely-not-a-page/"); 
print(f"crawled {len(seen)} URLs; {len(bad)} broken; unknown URL returns {code}")
[print(" BROKEN", u, c) for u, c in bad]; sys.exit(1 if bad or code != 404 else 0)
