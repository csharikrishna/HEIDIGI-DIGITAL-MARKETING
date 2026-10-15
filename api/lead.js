"use strict";
/* Serverless enquiry endpoint (Vercel Node function). Secrets come from environment variables only:
   RESEND_API_KEY, LEAD_TO_EMAIL, LEAD_FROM_EMAIL, SITE_ORIGIN (e.g. https://heidigi.com), optional TURNSTILE_SECRET. */
const crypto = require("crypto");
const L = require("../assets/js/lead.js");
const SERVICES = require("../content/services.json");
const BUDGETS = ["", "Under ₹10,000", "₹10,000 to ₹25,000", "₹25,000 to ₹50,000", "Above ₹50,000"];
const MAX = { name: 100, phone: 30, email: 120, company: 120, other: 120, message: 1500 };
const WINDOW_MS = 10 * 60 * 1000, LIMIT = 5, hits = new Map();   // best effort: memory is per serverless instance

function send(res, status, error) { res.statusCode = status; res.setHeader("Content-Type", "application/json"); res.end(JSON.stringify(error ? { ok: false, error } : { ok: true })); }
function clientIp(req) {
  const real = String(req.headers["x-real-ip"] || "").trim();
  if (real) return real;
  // Vercel appends the connection address to X-Forwarded-For; prefer the last hop, not a caller-supplied first entry.
  const chain = String(req.headers["x-forwarded-for"] || "").split(",").map(x => x.trim()).filter(Boolean);
  return chain[chain.length - 1] || (req.socket && req.socket.remoteAddress) || "unknown";
}
function limited(key) {
  const now = Date.now(), a = (hits.get(key) || []).filter(t => now - t < WINDOW_MS);
  if (a.length >= LIMIT) { hits.set(key, a); return true; }
  a.push(now); hits.set(key, a);
  if (hits.size > 5000) for (const [k, v] of hits) if (!v.some(t => now - t < WINDOW_MS)) hits.delete(k);
  return false;
}
async function rateLimited(ip, env) {
  const base = String(env.UPSTASH_REDIS_REST_URL || "").replace(/\/$/, "");
  const token = String(env.UPSTASH_REDIS_REST_TOKEN || "");
  if (base && token) {
    try {
      const u = new URL(base);
      if (u.protocol !== "https:") throw new Error("Upstash URL must use HTTPS");
      const hash = crypto.createHash("sha256").update(String(ip)).digest("hex").slice(0, 32);
      const bucket = Math.floor(Date.now() / WINDOW_MS);
      const key = "heidigi:lead:" + hash + ":" + bucket;
      const r = await fetch(base + "/pipeline", {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify([["INCR", key], ["EXPIRE", key, String(Math.ceil(WINDOW_MS / 1000) + 30)]])
      });
      if (!r.ok) throw new Error("Upstash rate-limit HTTP " + r.status);
      const result = await r.json();
      const count = Number(result && result[0] && result[0].result);
      if (!Number.isFinite(count)) throw new Error("Invalid Upstash rate-limit response");
      return count > LIMIT;
    } catch (e) {
      console.error("distributed rate limit unavailable; using per-instance fallback");
    }
  }
  return limited(ip);
}
async function verifyTurnstile(token, ip) {
  if (!token) return false;
  try {
    const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: new URLSearchParams({ secret: process.env.TURNSTILE_SECRET, response: token, remoteip: ip }) });
    return (await r.json()).success === true;
  } catch (e) { return false; }
}
module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  const env = process.env;
  if (req.method !== "POST") { res.setHeader("Allow", "POST"); return send(res, 405, "method_not_allowed"); }
  if (!env.RESEND_API_KEY || !env.LEAD_TO_EMAIL || !env.LEAD_FROM_EMAIL || !env.SITE_ORIGIN) return send(res, 503, "not_configured");
  if (req.headers.origin !== env.SITE_ORIGIN) return send(res, 403, "forbidden_origin");
  if (!String(req.headers["content-type"] || "").toLowerCase().includes("application/json")) return send(res, 415, "unsupported_type");
  const contentLength = Number(req.headers["content-length"] || 0);
  if (Number.isFinite(contentLength) && contentLength > 8192) return send(res, 413, "too_large");
  let b = req.body; try { if (typeof b === "string") b = JSON.parse(b); } catch (e) { return send(res, 400, "bad_json"); }
  if (!b || typeof b !== "object" || Array.isArray(b) || JSON.stringify(b).length > 8192) return send(res, 413, "too_large");
  if (b.website || typeof b.elapsed !== "number" || b.elapsed < 3000) return send(res, 400, "rejected");
  const v = {};
  for (const k of ["name", "phone", "email", "company", "service", "other", "budget", "message"]) {
    const x = b[k] === undefined || b[k] === null ? "" : b[k];
    if (typeof x !== "string" || (MAX[k] && x.length > MAX[k])) return send(res, 422, "invalid_" + k);
    if (k === "email" && /[\r\n]/.test(x)) return send(res, 422, "invalid_email");
    v[k] = x.trim();
  }
  if (v.service !== "other" && !Object.prototype.hasOwnProperty.call(SERVICES, v.service)) return send(res, 422, "invalid_service");
  if (!BUDGETS.includes(v.budget)) return send(res, 422, "invalid_budget");
  if (Object.keys(L.validate(v)).length) return send(res, 422, "invalid_fields");
  const ip = clientIp(req);
  if (await rateLimited(ip, env)) { res.setHeader("Retry-After", "600"); return send(res, 429, "rate_limited"); }
  if (env.TURNSTILE_SECRET && !(await verifyTurnstile(b.ts, ip))) return send(res, 400, "spam_check_failed");
  const name = v.service === "other" ? "Other" : SERVICES[v.service], text = L.message(v, name) + "\n\n(Sent from the Hei Digi website enquiry form)";
  try {
    const r = await fetch("https://api.resend.com/emails", { method: "POST", headers: { Authorization: "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ from: env.LEAD_FROM_EMAIL, to: [env.LEAD_TO_EMAIL], subject: "New website enquiry: " + name, text }, v.email ? { reply_to: v.email } : {})) });
    if (!r.ok) { console.error("lead email provider status", r.status); return send(res, 502, "delivery_failed"); }
  } catch (e) { console.error("lead email provider unreachable"); return send(res, 502, "delivery_failed"); }
  return send(res, 200);
};
