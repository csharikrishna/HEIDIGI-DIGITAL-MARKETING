#!/usr/bin/env python3
"""One-time: download Inter and Sora (latin, variable woff2) from Google Fonts into assets/fonts/ so the site can self-host them.
Run once with internet access, then `python3 build.py`. The build detects the files and switches to self-hosted fonts automatically
(preload + fonts.css, and the CSP drops fonts.googleapis.com / fonts.gstatic.com). Both fonts are SIL Open Font License."""
import re, urllib.request
from pathlib import Path
R = Path(__file__).resolve().parent.parent; (R/"assets/fonts").mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read()
for name, q in (("inter", "Inter:wght@400..600"), ("sora", "Sora:wght@600..700")):
    css = get(f"https://fonts.googleapis.com/css2?family={q}&display=swap").decode()
    m = re.search(r"/\* latin \*/\s*@font-face\s*\{[^}]*?url\((https://[^)]+\.woff2)\)", css)
    if not m: raise SystemExit(f"could not find latin woff2 for {name}")
    data = get(m.group(1)); (R/f"assets/fonts/{name}.woff2").write_bytes(data); print(name, len(data), "bytes")
