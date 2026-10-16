"""Tiny static server for tests. Applies the REAL generated security headers (from _headers) so CSP violations show up as console errors."""
import http.server, threading, functools, re
from pathlib import Path
R = Path(__file__).resolve().parent.parent
def hdrs():
    out = []
    for ln in (R/"_headers").read_text(encoding="utf-8").split("\n/assets")[0].splitlines()[2:]:
        k, v = [x.strip() for x in ln.split(":", 1)]
        if k == "Content-Security-Policy": v = v.replace("; upgrade-insecure-requests", "")  # local http would otherwise be upgraded
        out.append((k, v))
    return out
def serve(port, csp=True, root=R):
    H = hdrs()
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(s, *a, **k): super().__init__(*a, directory=str(root), **k)
        def log_message(s, *a): pass
        def end_headers(s):
            if csp:
                for k, v in H: s.send_header(k, v)
            super().end_headers()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv
