// Tests for api/lead.js with a mocked email provider. No network, no real credentials.
const path = require("path"); let fails = 0, calls = [];
const ok = (c, m) => { if (!c) { fails++; console.log("FAIL", m); } };
const ENV = { RESEND_API_KEY: "re_test", LEAD_TO_EMAIL: "to@x.com", LEAD_FROM_EMAIL: "Hei Digi <noreply@x.com>", SITE_ORIGIN: "https://heidigi.com" };
function fresh() { delete require.cache[require.resolve("../api/lead.js")]; return require("../api/lead.js"); }
function call(h, o = {}) {
  return new Promise(async (resolve) => {
    const req = { method: o.method || "POST", headers: Object.assign({ origin: ENV.SITE_ORIGIN, "content-type": "application/json", "x-forwarded-for": o.ip || "1.2.3.4" }, o.headers), body: o.body };
    const res = { headers: {}, setHeader(k, v) { this.headers[k] = v; }, end(b) { resolve({ status: this.statusCode, body: JSON.parse(b), headers: this.headers }); } };
    await h(req, res);
  });
}
const good = () => ({ name: "Ravi", phone: "9876543210", email: "r@x.com", company: "Co", service: "meta-ads", other: "", budget: "", message: "Hello", website: "", elapsed: 9000 });
(async () => {
  global.fetch = async (url, init) => { calls.push({ url, init }); return { ok: true, status: 200, json: async () => ({ success: true }) }; };
  Object.assign(process.env, ENV);
  let h = fresh(), r;
  r = await call(h, { method: "GET" }); ok(r.status === 405, "GET 405");
  for (const k of Object.keys(ENV)) { const v = process.env[k]; delete process.env[k]; h = fresh(); calls = []; r = await call(h, { body: good() }); ok(r.status === 503 && r.body.ok === false && !calls.length, "missing " + k + " -> 503 and no email"); process.env[k] = v; }
  h = fresh();
  r = await call(h, { headers: { origin: "https://evil.example" }, body: good() }); ok(r.status === 403, "foreign origin 403");
  r = await call(h, { headers: { "content-type": "text/plain" }, body: good() }); ok(r.status === 415, "content type 415");
  r = await call(h, { headers: { "content-length": "9000" }, body: good() }); ok(r.status === 413, "oversized content-length 413");
  r = await call(h, { body: Object.assign(good(), { email: "person@example.com\r\nBcc:attacker@example.com" }) }); ok(r.status === 422, "header injection in email rejected");
  r = await call(h, { body: Object.assign(good(), { website: "bot" }) }); ok(r.status === 400, "honeypot 400");
  r = await call(h, { body: Object.assign(good(), { elapsed: 500 }) }); ok(r.status === 400, "too fast 400");
  r = await call(h, { body: Object.assign(good(), { name: "" }) }); ok(r.status === 422, "empty name 422");
  r = await call(h, { body: Object.assign(good(), { phone: "123" }) }); ok(r.status === 422, "bad phone 422");
  r = await call(h, { body: Object.assign(good(), { service: "hack" }) }); ok(r.status === 422, "unknown service 422");
  for (const service of ["constructor", "toString", "__proto__"]) { r = await call(h, { body: Object.assign(good(), { service }) }); ok(r.status === 422, "prototype key rejected: " + service); }
  r = await call(h, { body: Object.assign(good(), { service: "other", other: "" }) }); ok(r.status === 422, "other needs detail");
  r = await call(h, { body: Object.assign(good(), { message: "x".repeat(2000) }) }); ok(r.status === 422, "long message 422");
  r = await call(h, { body: Object.assign(good(), { budget: "free" }) }); ok(r.status === 422, "bad budget 422");
  ok(calls.length === 0, "no email sent for rejected requests");
  r = await call(h, { body: good() });
  ok(r.status === 200 && r.body.ok === true && calls.length === 1, "valid -> 200 and exactly one email");
  const sent = JSON.parse(calls[0].init.body);
  ok(calls[0].url === "https://api.resend.com/emails" && calls[0].init.headers.Authorization === "Bearer re_test" && sent.to[0] === "to@x.com" && sent.reply_to === "r@x.com" && /Meta Ads/.test(sent.subject) && /Ravi/.test(sent.text), "email content and auth");
  ok(!/re_test/.test(JSON.stringify(r.body)), "secret not in response");
  global.fetch = async () => ({ ok: false, status: 500 }); h = fresh(); r = await call(h, { body: good(), ip: "9.9.9.9" }); ok(r.status === 502 && r.body.ok === false, "provider failure -> 502, not success");
  global.fetch = async () => { throw new Error("down"); }; r = await call(h, { body: good(), ip: "9.9.9.8" }); ok(r.status === 502, "provider down -> 502");
  global.fetch = async (u, i) => { calls.push({ url: u, init: i }); return { ok: true, status: 200, json: async () => ({ success: true }) }; }; h = fresh();
  for (let i = 0; i < 5; i++) r = await call(h, { body: good(), ip: "5.5.5.5" }); ok(r.status === 200, "5th ok");
  r = await call(h, { body: good(), ip: "5.5.5.5" }); ok(r.status === 429 && r.headers["Retry-After"], "6th rate limited");
  r = await call(h, { body: good(), ip: "6.6.6.6" }); ok(r.status === 200, "other IP unaffected");
  const oldUpstashUrl = process.env.UPSTASH_REDIS_REST_URL, oldUpstashToken = process.env.UPSTASH_REDIS_REST_TOKEN;
  process.env.UPSTASH_REDIS_REST_URL = "https://redis.example.com"; process.env.UPSTASH_REDIS_REST_TOKEN = "up_test";
  let redisCount = 0, redisCalls = 0;
  global.fetch = async (url, init) => {
    if (String(url).endsWith("/pipeline")) { redisCalls++; return { ok: true, status: 200, json: async () => [{ result: ++redisCount }, { result: 1 }] }; }
    calls.push({ url, init }); return { ok: true, status: 200, json: async () => ({ id: "email_test" }) };
  };
  h = fresh();
  for (let i = 0; i < 5; i++) r = await call(h, { body: good(), ip: "8.8.8.8" });
  ok(r.status === 200 && redisCalls === 5, "Upstash distributed limiter permits first five valid requests");
  r = await call(h, { body: good(), ip: "8.8.8.8" }); ok(r.status === 429 && redisCalls === 6, "Upstash distributed limiter blocks the sixth request");
  if (oldUpstashUrl === undefined) delete process.env.UPSTASH_REDIS_REST_URL; else process.env.UPSTASH_REDIS_REST_URL = oldUpstashUrl;
  if (oldUpstashToken === undefined) delete process.env.UPSTASH_REDIS_REST_TOKEN; else process.env.UPSTASH_REDIS_REST_TOKEN = oldUpstashToken;
  global.fetch = async (u, i) => { calls.push({ url: u, init: i }); return { ok: true, status: 200, json: async () => ({ id: "email_test" }) }; };
  process.env.TURNSTILE_SECRET = "ts"; h = fresh(); calls = [];
  global.fetch = async (u, i) => { calls.push(u); return { ok: true, status: 200, json: async () => ({ success: u.includes("turnstile") ? false : true }) }; };
  r = await call(h, { body: good() }); ok(r.status === 400 && !calls.some(u => u.includes("resend")), "turnstile missing token blocks email");
  r = await call(h, { body: Object.assign(good(), { ts: "tok" }) }); ok(r.status === 400 && !calls.some(u => u.includes("resend")), "turnstile failure blocks email");
  global.fetch = async (u) => ({ ok: true, status: 200, json: async () => ({ success: true }) }); r = await call(h, { body: Object.assign(good(), { ts: "tok" }), ip: "7.7.7.7" }); ok(r.status === 200, "turnstile pass -> 200");
  console.log(fails ? fails + " failed" : "api/lead.js: all tests passed"); process.exit(fails ? 1 : 0);
})();
