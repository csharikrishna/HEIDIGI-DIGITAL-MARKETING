/* Pure enquiry logic (validation + WhatsApp message). Works in browsers and Node (for tests). */
(function (root, factory) { if (typeof module === "object" && module.exports) module.exports = factory(); else root.HeiLead = factory(); })(this, function () {
  function digits(s) { return String(s || "").replace(/\D/g, ""); }
  function phoneOk(p) {
    var raw = String(p || "").trim(), d = digits(raw);
    if (d.length === 12 && d.slice(0, 2) === "91") d = d.slice(2);
    if (d.length === 11 && d[0] === "0") d = d.slice(1);
    if (/^[6-9]\d{9}$/.test(d)) return true;
    return raw.charAt(0) === "+" && d.length >= 8 && d.length <= 15;
  }
  function validate(v) {
    var e = {};
    if (!String(v.name || "").trim()) e.name = "Enter your name.";
    if (!phoneOk(v.phone)) e.phone = "Enter a valid phone number, for example 98765 43210.";
    if (v.email && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(String(v.email).trim())) e.email = "Enter a valid email address or leave it empty.";
    if (v.service === "other" && !String(v.other || "").trim()) e.other = "Tell us which service you need.";
    return e;
  }
  function message(v, serviceName) {
    var svc = v.service === "other" ? "Other: " + String(v.other).trim() : serviceName;
    var l = ["Hi Hei Digi, I would like to discuss " + svc + ".", "Name: " + v.name.trim(), "Phone: " + v.phone.trim()];
    if (v.email) l.push("Email: " + v.email.trim());
    if (v.company) l.push("Company: " + v.company.trim());
    if (v.budget) l.push("Budget for service fee: " + v.budget);
    if (v.message) l.push("Message: " + v.message.trim());
    return l.join("\n");
  }
  function waUrl(number, text) { return "https://wa.me/" + digits(number) + "?text=" + encodeURIComponent(text); }
  return { validate: validate, message: message, waUrl: waUrl, phoneOk: phoneOk };
});
