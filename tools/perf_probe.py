"""LOCAL lab measurement (Chromium, localhost, no network throttling). Informational only: NOT Lighthouse and NOT field data. python3 tools/perf_probe.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); from _server import serve, R
from playwright.sync_api import sync_playwright
serve(8134, csp=True); out = {}
OBS = "new Promise(r=>{let lcp=0,cls=0;new PerformanceObserver(l=>{for(const e of l.getEntries())lcp=e.startTime}).observe({type:'largest-contentful-paint',buffered:true});new PerformanceObserver(l=>{for(const e of l.getEntries())if(!e.hadRecentInput)cls+=e.value}).observe({type:'layout-shift',buffered:true});setTimeout(()=>{const f=performance.getEntriesByName('first-contentful-paint')[0];r({fcp:f&&Math.round(f.startTime),lcp:Math.round(lcp),cls:+cls.toFixed(3)})},1500)})"
with sync_playwright() as p:
    br = p.chromium.launch()
    for name, kw in (("mobile", dict(viewport={"width": 390, "height": 844}, is_mobile=True)), ("desktop", dict(viewport={"width": 1366, "height": 800}))):
        for path in ("/", "/services/meta-ads/"):
            ctx = br.new_context(**kw); pg = ctx.new_page(); size = [0]; n = [0]
            def on(r):
                try: size[0] += len(r.body()); n[0] += 1
                except Exception: pass
            pg.on("response", lambda r: on(r) if "127.0.0.1" in r.url else None)
            pg.goto("http://127.0.0.1:8134" + path, wait_until="load"); m = pg.evaluate(OBS); m.update(requests=n[0], kb_uncompressed=round(size[0]/1024, 1))
            out[f"{name} {path}"] = m; ctx.close()
    br.close()
(R/"reports").mkdir(exist_ok=True); (R/"reports/perf-local.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
