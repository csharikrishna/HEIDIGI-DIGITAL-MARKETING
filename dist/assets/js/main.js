(function () {
  "use strict";
  var CFG = window.HEIDIGI_CONFIG || {}, D = window.HEIDIGI_DATA || {}, doc = document;
  var $ = function (s, r) { return (r || doc).querySelector(s); }, $$ = function (s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); };

  /* ---- analytics: off until configured in site.config.json AND the visitor accepts ---- */
  var KEY = "hd_consent", configured = !!(CFG.ga4 || CFG.plausible), granted = false;
  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  function getC() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function setC(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  function loadAnalytics() {
    if (granted) return; granted = true;
    if (CFG.ga4 && /^G-[A-Z0-9]+$/.test(CFG.ga4)) { var g = doc.createElement("script"); g.async = true; g.src = "https://www.googletagmanager.com/gtag/js?id=" + CFG.ga4; doc.head.appendChild(g); gtag("js", new Date()); gtag("config", CFG.ga4, { anonymize_ip: true }); }
    if (CFG.plausible) { var p = doc.createElement("script"); p.defer = true; p.setAttribute("data-domain", CFG.plausible); p.src = "https://plausible.io/js/script.js"; doc.head.appendChild(p); }
  }
  function clearGA() {
    var exp = "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/", h = location.hostname;
    doc.cookie.split(";").forEach(function (c) { var n = c.split("=")[0].trim(); if (n.indexOf("_ga") === 0) { doc.cookie = n + exp; [h, "." + h, "." + h.replace(/^www\./, "")].forEach(function (d) { doc.cookie = n + exp + "; domain=" + d; }); } });
    if (CFG.ga4) window["ga-disable-" + CFG.ga4] = true;
  }
  function track(name, params) {
    if (!granted) return; params = params || {}; params.page = location.pathname;
    try { if (CFG.ga4) gtag("event", name, params); if (window.plausible) window.plausible(name, { props: params }); } catch (e) {}
  }
  function showBanner(focus) {
    var old = $("#consent"); if (old) old.remove();
    var b = doc.createElement("div"); b.id = "consent"; b.setAttribute("role", "region"); b.setAttribute("aria-label", "Analytics consent");
    var copy = doc.createElement("p");
    copy.appendChild(doc.createTextNode("We would like to use analytics to see which pages and contact buttons are used. It stays off unless you accept. "));
    var privacy = doc.createElement("a"); privacy.href = "/privacy/"; privacy.textContent = "Privacy Policy"; copy.appendChild(privacy);
    var actions = doc.createElement("div");
    [["denied", "Decline"], ["granted", "Accept analytics"]].forEach(function (item) {
      var button = doc.createElement("button"); button.type = "button"; button.setAttribute("data-v", item[0]); button.textContent = item[1]; actions.appendChild(button);
    });
    b.appendChild(copy); b.appendChild(actions);
    b.addEventListener("click", function (e) {
      var v = e.target.getAttribute && e.target.getAttribute("data-v"); if (!v) return;
      var was = granted; setC(v); b.remove();
      if (v === "granted") loadAnalytics(); else { clearGA(); if (was) location.reload(); }
    });
    doc.body.appendChild(b); if (focus) $("button", b).focus();
  }
  if (configured) {
    var c0 = getC(); if (c0 === "granted") loadAnalytics(); else if (c0 !== "denied") showBanner(false);
    var slot = $("#consent-slot"); if (slot) {
      slot.appendChild(doc.createTextNode(" · "));
      var settings = doc.createElement("button"); settings.type = "button"; settings.className = "linkbtn"; settings.textContent = "Privacy settings";
      settings.addEventListener("click", function () { showBanner(true); }); slot.appendChild(settings);
    }
  }
  doc.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a,button"); if (!a) return;
    var h = a.getAttribute("href") || "";
    if (h.indexOf("tel:") === 0) track("phone_click");
    else if (h.indexOf("wa.me") > -1) track("whatsapp_click", { cta: a.getAttribute("data-cta") || "" });
    else if (h.indexOf("mailto:") === 0) track("email_click");
    if (a.getAttribute("data-cta")) track("cta_click", { cta: a.getAttribute("data-cta") });
  });

  /* ---- mobile navigation ---- */
  var nav = $("#nav"), burger = $("#burger"), mq = window.matchMedia ? matchMedia("(max-width:960px)") : { matches: false };
  function isOpen() { return doc.body.classList.contains("open"); }
  function sync() { if (!nav) return; var hide = mq.matches && !isOpen(); if (hide) nav.setAttribute("inert", ""); else nav.removeAttribute("inert"); }
  function setMenu(open, back) {
    doc.body.classList.toggle("open", open); burger.setAttribute("aria-expanded", String(open)); burger.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    sync(); if (open) { var f = $("a", nav); if (f) f.focus(); } else if (back) burger.focus();
  }
  if (nav && burger) {
    sync(); if (mq.addEventListener) mq.addEventListener("change", function () { setMenu(false); });
    burger.addEventListener("click", function () { setMenu(!isOpen()); });
    nav.addEventListener("click", function (e) { if (e.target.closest("a")) setMenu(false); });
    doc.addEventListener("click", function (e) { if (isOpen() && !e.target.closest("header")) setMenu(false); });
    doc.addEventListener("keydown", function (e) {
      if (!isOpen()) return;
      if (e.key === "Escape") { setMenu(false, true); return; }
      if (e.key === "Tab") {
        var f = [burger].concat($$("a", nav)), i = f.indexOf(doc.activeElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); } else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
      }
    });
  }

  /* ---- header state + active section (homepage only) ---- */
  var hdr = $("#hdr"), spy = $$('main section[id]'), links = $$('#nav a[href^="/#"]'), tick = false;
  function onScroll() {
    tick = false; if (hdr && !hdr.classList.contains("solid") || hdr && hdr.dataset.fixed) hdr.classList.toggle("scrolled", scrollY > 30);
    if (!doc.getElementById("home")) return;
    var cur = "", y = scrollY + 120; spy.forEach(function (s) { if (s.offsetTop <= y) cur = s.id; });
    links.forEach(function (l) { var on = l.getAttribute("href") === "/#" + cur; l.classList.toggle("on", on); if (on) l.setAttribute("aria-current", "location"); else l.removeAttribute("aria-current"); });
  }
  addEventListener("scroll", function () { if (!tick) { tick = true; requestAnimationFrame(onScroll); } }, { passive: true }); onScroll();

  /* ---- reveal: one observer, only if the page opted in via the rv-on class ---- */
  if (doc.documentElement.classList.contains("rv-on")) {
    try {
      var io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }); }, { threshold: 0.12 });
      $$(".rv").forEach(function (el) { io.observe(el); });
    } catch (err) { doc.documentElement.classList.remove("rv-on"); }
  }

  /* ---- portfolio filters (static HTML already lists everything) ---- */
  var fbar = $("#filters"), figs = $$("#portfolio .wk");
  if (fbar && figs.length) {
    var cats = ["All"].concat((D.categories || []).filter(function (c) { return figs.some(function (f) { return f.dataset.cat === c; }); }));
    cats.forEach(function (c, i) {
      var button = doc.createElement("button"); button.type = "button"; button.setAttribute("aria-pressed", String(i === 0)); button.textContent = c; fbar.appendChild(button);
    }); fbar.hidden = false;
    fbar.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return; var c = b.textContent, n = 0;
      $$("button", fbar).forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      figs.forEach(function (f) { var show = c === "All" || f.dataset.cat === c; f.hidden = !show; if (show) n++; });
      $("#wk-empty").hidden = n > 0;
    });
  }

  /* ---- enquiry form: server endpoint when configured, otherwise WhatsApp ---- */
  var form = $("#lead");
  if (form) {
    var el = function (n) { return form.elements.namedItem(n); }, val = function (n) { var f = el(n); return f ? f.value : ""; };
    var other = $("#other-wrap"), svc = el("service"), status = $("#status"), btn = $("button[type=submit]", form), started = Date.now(), tsToken = "", useApi = !!CFG.leadEndpoint;
    /* The submit control starts disabled in HTML so no-JS submissions cannot leak form fields into a GET URL. Enable it only when the required client modules are ready. */
    if (!window.HEIDIGI_CONFIG || !window.HeiLead) {
      status.textContent = "The enquiry form could not load. Please contact us directly using the details below.";
      return;
    }
    btn.disabled = false;
    function toggleOther() { other.hidden = svc.value !== "other"; }
    var q = new URLSearchParams(location.search).get("service");
    if (q && CFG.services && (CFG.services[q] || q === "other")) svc.value = q;
    svc.addEventListener("change", toggleOther); toggleOther();
    if (useApi && CFG.turnstileSiteKey && $("#ts")) {
      window.hdTs = function () { try { window.turnstile.render("#ts", { sitekey: CFG.turnstileSiteKey, callback: function (t) { tsToken = t; }, "expired-callback": function () { tsToken = ""; } }); } catch (e) {} };
      var ts = doc.createElement("script"); ts.async = true; ts.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=hdTs"; doc.head.appendChild(ts);
    }
    function appendSafeLink(parent, label, href, newTab) {
      var a = doc.createElement("a"); a.textContent = label; a.href = href;
      if (newTab) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
      parent.appendChild(a); return a;
    }
    function appendFallbackLinks(wa, mail) {
      status.appendChild(doc.createTextNode(" Please use ")); appendSafeLink(status, "WhatsApp", wa, true);
      status.appendChild(doc.createTextNode(", ")); appendSafeLink(status, "call us", "tel:" + CFG.phone, false);
      status.appendChild(doc.createTextNode(" or ")); appendSafeLink(status, "email us", mail, false);
      status.appendChild(doc.createTextNode("."));
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault(); status.textContent = "";
      var v = { name: val("name"), phone: val("phone"), email: val("email"), company: val("company"), service: val("service"), other: val("other"), budget: val("budget"), message: val("message") };
      var errs = HeiLead.validate(v), first = null;
      ["name", "phone", "email", "other"].forEach(function (k) {
        var f = el(k), m = $("#e-" + k); if (!f || !m) return;
        m.textContent = errs[k] || ""; if (errs[k]) { f.setAttribute("aria-invalid", "true"); first = first || f; } else f.removeAttribute("aria-invalid");
      });
      if (first) { first.focus(); status.textContent = "Please fix the highlighted fields."; return; }
      var name = CFG.services && CFG.services[v.service] || "Other", text = HeiLead.message(v, name), wa = HeiLead.waUrl(CFG.phone, text);
      var mail = "mailto:" + CFG.email + "?subject=" + encodeURIComponent("Enquiry: " + name) + "&body=" + encodeURIComponent(text);
      track("form_submit_valid", { service: v.service });
      if (!useApi) {
        window.open(wa, "_blank", "noopener");
        status.textContent = "WhatsApp should open with your message. Nothing is sent until you press Send there, and this website does not store your entry. If WhatsApp did not open, ";
        appendSafeLink(status, "open it here", wa, true); status.appendChild(doc.createTextNode(" or "));
        appendSafeLink(status, "email us instead", mail, false); status.appendChild(doc.createTextNode("."));
        return;
      }
      if (CFG.turnstileSiteKey && !tsToken) { status.textContent = "Please complete the spam check, then send again."; return; }
      btn.disabled = true; btn.setAttribute("aria-busy", "true"); status.textContent = "Sending your enquiry...";
      var payload = Object.assign({}, v, { website: val("website"), elapsed: Date.now() - started, ts: tsToken });
      fetch(CFG.leadEndpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok && j && j.ok === true, status: r.status }; }, function () { return { ok: false, status: r.status }; }); })
        .then(function (res) {
          btn.disabled = false; btn.removeAttribute("aria-busy");
          if (res.ok) {
            track("lead_sent", { service: v.service }); form.reset(); toggleOther(); started = Date.now();
            status.textContent = "Thank you. Your enquiry was sent to Hei Digi and we will contact you using the details you gave. For anything urgent you can also ";
            appendSafeLink(status, "message us on WhatsApp", wa, true); status.appendChild(doc.createTextNode("."));
          } else {
            status.textContent = res.status === 429 ? "Too many attempts from your connection. Please wait a few minutes." : "We could not send your enquiry, so we have not received it.";
            appendFallbackLinks(wa, mail);
          }
          if (window.turnstile && tsToken) { try { window.turnstile.reset(); } catch (e) {} tsToken = ""; }
        })
        .catch(function () { btn.disabled = false; btn.removeAttribute("aria-busy"); status.textContent = "We could not reach our server, so your enquiry has not been sent."; appendFallbackLinks(wa, mail); });
    });
  }
})();
