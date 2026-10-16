#!/usr/bin/env python3
"""Run every check and write reports/quality-report.md. Exit code 1 if any CRITICAL step fails.  python3 tools/run_all.py"""
import hashlib, json, shutil, subprocess, sys, time
from pathlib import Path
R = Path(__file__).resolve().parent.parent; (R/"reports").mkdir(exist_ok=True)
def tree():
    h = hashlib.sha1()
    for f in sorted(R.rglob("*")):
        if f.is_file() and not any(x in f.parts for x in ("reports", "node_modules", ".git", "__pycache__", ".lighthouseci", ".vercel")) and not f.name.startswith("_browser_"): h.update(f.relative_to(R).as_posix().encode() + f.read_bytes())
    return h.hexdigest()
steps = []  # (name, critical, status, seconds, tail)
def run(name, cmd, critical=True):
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=R, capture_output=True, text=True, timeout=60)
        out = (p.stdout + p.stderr).strip().splitlines()
        ok = p.returncode == 0
        steps.append((name, critical, "PASS" if ok else "FAIL", round(time.time() - t, 1), "\n".join(out[-6:])))
        return ok
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
        steps.append((name, critical, "FAIL", round(time.time() - t, 1), (out + "\nCommand timed out after 60 seconds")[-2500:]))
        return False
before = tree(); run("Rebuild from source (build.py)", [sys.executable, "build.py"])
after = tree(); steps.append(("Generated files are up to date (rebuild changed nothing)", True, "PASS" if before == after else "FAIL", 0, "commit the rebuilt files" if before != after else "no text file changed"))
run("Static audit (tools/audit.py)", [sys.executable, "tools/audit.py"])
run("Optional build modes and CSP (tools/test_build_modes.py)", [sys.executable, "tools/test_build_modes.py"])
run("Form logic (tools/test_lead.js)", ["node", "tools/test_lead.js"])
run("Enquiry API (tools/test_api.js)", ["node", "tools/test_api.js"])
run("JavaScript syntax", [sys.executable, "-c", "import sys, subprocess, glob; errs = []; [errs.append(f'{f}: {p.stderr.strip()}\\n') for f in sorted(glob.glob('assets/js/*.js') + glob.glob('api/*.js')) for p in [subprocess.run(['node', '--check', f], capture_output=True, text=True)] if p.returncode != 0]; (sys.stderr.write(''.join(errs)) if errs else None); sys.exit(1 if errs else 0)"])
run("Internal link crawl (tools/crawl_links.py)", [sys.executable, "tools/crawl_links.py"])
try:
    browser_probe = subprocess.run([sys.executable, "-c", "from playwright.sync_api import sync_playwright as s;p=s().start();p.chromium.launch().close();p.stop()"], capture_output=True, timeout=8)
    have_pw = browser_probe.returncode == 0
except subprocess.TimeoutExpired:
    have_pw = False
if have_pw:
    run("Browser tests: pages, nav, form, no-JS, reduced motion (tools/browser_test.py)", [sys.executable, "tools/browser_test.py"])
    run("Browser tests: CSP, consent, enquiry endpoint, keyboard (tools/browser_features.py)", [sys.executable, "tools/browser_features.py"])
    run("Local performance probe (informational, not Lighthouse)", [sys.executable, "tools/perf_probe.py"], critical=False)
else: steps.append(("Browser tests", False, "SKIP", 0, "Playwright browser could not launch in this environment. Browser interaction assertions were not run here. GitHub Actions installs Chromium and executes these same tests."))
cfg = json.loads((R/"site.config.json").read_text(encoding="utf-8")); lim = []
if not shutil.which("lighthouse") and not shutil.which("lhci"): lim.append("Lighthouse is not installed in this environment, so no Lighthouse scores were produced here (CI job `lighthouse` runs it).")
lim.append("Tests run against a local server, not the live domain: HTTPS, redirects, real response headers, HSTS and compression are untested until deployed.")
if not (R/"assets/fonts/inter.woff2").exists(): lim.append("Bundled WOFF2 font files are not present. The current build uses the system-font fallback and does not request Google Fonts. To add branded Inter/Sora fonts, run `python3 tools/fetch_fonts.py` once on a machine with internet access, then rebuild.")
if not cfg.get("leadEndpoint"): lim.append("Lead endpoint is off (WhatsApp/email only). The serverless function is unit-tested with a mocked email provider, never with real credentials.")
if not (cfg["analytics"]["ga4"] or cfg["analytics"]["plausibleDomain"]): lim.append("Analytics is off, so real GA4/Plausible delivery is untested (consent logic is tested with the request mocked).")
lim.append("This run only checks source/build in the available environment. Browser UI tests are skipped if Playwright cannot launch Chromium; GitHub Actions installs Chromium and runs them. Safari/Firefox, screen-reader and real-device tests are not included.")
crit = [s for s in steps if s[1] and s[2] == "FAIL"]
passed = sum(1 for s in steps if s[2] == "PASS"); failed = sum(1 for s in steps if s[2] == "FAIL"); skipped = sum(1 for s in steps if s[2] == "SKIP")
status = "FAILED" if crit else ("PASSED WITH SKIPS" if skipped else "PASSED")
md = ["# Quality report", "", f"Result: **{status}** ({passed} passed, {failed} failed, {skipped} skipped)", "", "| Step | Critical | Result | Seconds |", "|---|---|---|---|"]
md += [f"| {n} | {'yes' if c else 'no'} | {st} | {t} |" for n, c, st, t, _ in steps]
md += ["", "## Details (last lines of each step)"] + [f"**{n}**\n```\n{tail}\n```" for n, _, _, _, tail in steps]
md += ["", "## Environment limitations", ""] + [f"- {x}" for x in lim]
(R/"reports/quality-report.md").write_text("\n".join(md) + "\n", encoding="utf-8"); print("\n".join(md[:4 + len(steps) + 2])); print("\nLimitations:"); [print(" -", x) for x in lim]
sys.exit(1 if crit else 0)
