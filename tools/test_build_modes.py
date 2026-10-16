#!/usr/bin/env python3
"""Exercise optional production configuration and check generated CSPs."""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns(".git", "__pycache__", "reports", ".lighthouseci", "node_modules", ".vercel")

def fail(msg):
    print("FAIL", msg)
    raise SystemExit(1)

print("[modes] preparing temp project", flush=True)
with tempfile.TemporaryDirectory(prefix="heidigi-build-modes-") as td:
    project = Path(td) / "project"
    shutil.copytree(ROOT, project, ignore=IGNORE)
    print("[modes] copied project", flush=True)
    cfg_path = project / "site.config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    # Ensure audit rules follow the configured host rather than a baked-in production domain.
    cfg["domain"] = "https://www.heidigi-audit.example"
    cfg["turnstileSiteKey"] = "test-public-site-key"
    cfg["leadEndpoint"] = "/api/lead"
    cfg["analytics"]["ga4"] = "G-TEST1234"
    cfg["analytics"]["plausibleDomain"] = "analytics.example.com"
    cfg["hstsMaxAge"] = 300
    cfg_path.write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8")
    print("[modes] building alternate domain", flush=True)
    run = subprocess.run([sys.executable, "build.py"], cwd=project, capture_output=True, text=True, timeout=90)
    print("[modes] alternate build finished", flush=True)
    if run.returncode:
        fail("alternate build failed: " + (run.stdout + run.stderr)[-1200:])
    print("[modes] running alternate audit", flush=True)
    audit = subprocess.run([sys.executable, "tools/audit.py"], cwd=project, capture_output=True, text=True, timeout=30)
    print("[modes] alternate audit finished", flush=True)
    if audit.returncode:
        fail("custom-domain static audit failed: " + (audit.stdout + audit.stderr)[-1200:])

    # Parse both host configurations and require the same CSP.
    headers = (project / "_headers").read_text(encoding="utf-8")
    csp_line = next((x.split(":", 1)[1].strip() for x in headers.splitlines() if x.strip().startswith("Content-Security-Policy:")), None)
    vercel = json.loads((project / "vercel.json").read_text(encoding="utf-8"))
    vc_headers = vercel["headers"][0]["headers"]
    vc_csp = next((h["value"] for h in vc_headers if h["key"] == "Content-Security-Policy"), None)
    if not csp_line or csp_line != vc_csp:
        fail("Netlify/Cloudflare and Vercel CSP output differs")
    directives = {chunk.split(" ", 1)[0]: chunk.split(" ")[1:] for chunk in csp_line.split("; ") if " " in chunk}
    origin = "https://challenges.cloudflare.com"
    for key in ("script-src", "connect-src", "frame-src"):
        if origin not in directives.get(key, []):
            fail(f"Turnstile origin missing from {key}")
    if "https://www.googletagmanager.com" not in directives.get("script-src", []):
        fail("GA4 script origin missing from script-src")
    if "https://plausible.io" not in directives.get("script-src", []):
        fail("Plausible script origin missing from script-src")
    if not any(h.get("key") == "Strict-Transport-Security" and h.get("value") == "max-age=300" for h in vc_headers):
        fail("configured HSTS not present in Vercel headers")
    html = (project / "index.html").read_text(encoding="utf-8")
    if '<form id="lead" method="post" novalidate>' not in html or '<div id="ts"></div>' not in html:
        fail("configured lead form does not have POST fallback and Turnstile container")
    print("build modes: custom domain, Turnstile, GA4, Plausible, HSTS and form output passed")
