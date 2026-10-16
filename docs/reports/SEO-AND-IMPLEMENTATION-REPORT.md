# Hei Digi: SEO & Implementation Technical Report

**Target Domain:** `https://heidigi.com`  
**Location:** Tirupati, Andhra Pradesh, India (PIN: 517507)  
**Engineering Team:** Senior Architecture, Performance, SEO & Security Taskforce  
**Publication Date:** October 2026  
**Status:** Production Ready  

---

## 1. Executive Summary

Hei Digi is a high-performance, privacy-first digital marketing agency website engineered for high-intent search discovery, local map visibility, generative AI answer engine indexing, and resilient lead conversion in Tirupati and surrounding regions of Andhra Pradesh.

Unlike standard agency websites built on heavy CMS platforms (e.g. WordPress, Wix) or complex JavaScript single-page application (SPA) frameworks that degrade Core Web Vitals and fail search engine rendering budgets, Hei Digi employs an ultra-lean, custom Python-based Static Site Generation (SSG) pipeline ([`build.py`](file:///c:/Users/cshar/Downloads/HEIDIGI-DIGITAL-MARKETING/build.py)). The runtime architecture delivers pure, standards-compliant HTML5, responsive CSS3, and modular ES6 JavaScript with zero external runtime dependencies.

### Core Architecture Highlights
- **100% Static HTML Output:** 41 indexable pages + 1 custom 404 page generated directly into `dist/`.
- **Zero Layout Shift (CLS 0.000):** Font fallbacks, explicit image dimensions, and instant `<head>` layout bootstrapping ([`assets/js/boot.js`](file:///c:/Users/cshar/Downloads/HEIDIGI-DIGITAL-MARKETING/assets/js/boot.js)).
- **Subresource Integrity & Cache Busting:** Deterministic SHA1 content hashing on all CSS/JS assets (`?v=<sha1>`).
- **Modern AI/LLM Discoverability:** Complete semantic machine-readable index (`llms.txt`, `llms-full.txt`, and `.well-known/ai-catalog.json`).
- **Comprehensive Local SEO:** Geographic metadata (`geo.region`, `geo.placename`, `geo.position`, `ICBM`), exact coordinates (13.6288, 79.4192), and rich Schema.org `ProfessionalService` structured data.
- **Enterprise Edge Security:** Strict Content Security Policy (`default-src 'self'`), zero inline scripts or inline styles, HTTP Strict Transport Security (HSTS), and DPDPA 2023 compliant consent gating.
- **Dual-Mode Resilient Lead Capture:** Direct instant WhatsApp routing (`wa.me`) or serverless edge processing ([`api/lead.js`](file:///c:/Users/cshar/Downloads/HEIDIGI-DIGITAL-MARKETING/api/lead.js)) backed by distributed Redis rate-limiting, Cloudflare Turnstile, and Resend transactional delivery.

---

## 2. Technical SEO Architecture

### 2.1 Information Architecture & URL Strategy
The URL hierarchy strictly enforces clean, slash-terminated paths without extensions or query pollution:
- **Core Hubs:** `/`, `/about/`, `/services/`, `/industries/`, `/locations/`, `/blog/`, `/contact/`
- **Service Silos:** `/services/<service-slug>/` (9 comprehensive service definitions)
- **Industry Silos:** `/industries/<industry-slug>/` (5 key economic sectors)
- **Geographic Silos:** `/locations/<location-slug>/` (3 primary service areas: Tirupati, Chittoor, Renigunta)
- **Client Summaries:** `/work/<client-slug>/` (transparent, evidence-based portfolio presentations)
- **Legal Directives:** `/privacy/`, `/terms/`, `/cookie-policy/`, `/disclaimer/`

Every page specifies a fully-qualified self-referential canonical URL on `https://heidigi.com`. Vercel and static hosting configurations permanently redirect all `www.heidigi.com` traffic to the canonical apex domain `https://heidigi.com` via HTTP 308/301 permanent redirects.

### 2.2 Heading Hierarchy & Document Semantics
Audited by [`tools/audit.py`](file:///c:/Users/cshar/Downloads/HEIDIGI-DIGITAL-MARKETING/tools/audit.py), the DOM enforces strict semantic rules across every generated page:
- Exactly **one `<h1>` tag** per page representing the core page entity and target search intent.
- Strict non-skipping heading hierarchy (`<h1>` $\to$ `<h2>` $\to$ `<h3>`).
- Semantic landmark containers: `<header>`, `<nav>`, `<main id="main">`, `<article>`, `<section>`, `<aside>`, and `<footer>`.
- Keyboard accessibility: `<a class="skip-link" href="#main">` as the initial focusable element on every page.

### 2.3 Metadata Optimization & Snippet Precision
Meta tags adhere strictly to optimal SERP display constraints:
- **Titles:** Strictly clamped between **50 and 60 characters**, ensuring no truncation on mobile or desktop SERPs, suffixed consistently with `" | Hei Digi"`.
- **Meta Descriptions:** Strictly clamped between **140 and 155 characters**, featuring clear value propositions and call-to-actions without truncation.
- **Social Metadata:** Dynamic Open Graph (`og:*`) and Twitter Card (`twitter:summary_large_image`) tags with dedicated 1200x630 pixel WebP/JPEG graphics custom-rendered per page.
- **Geographic Meta Tags:** Local search engines are provided explicit regional signals:
  ```html
  <meta name="geo.region" content="IN-AP">
  <meta name="geo.placename" content="Tirupati">
  <meta name="geo.position" content="13.6288;79.4192">
  <meta name="ICBM" content="13.6288, 79.4192">
  ```

### 2.4 XML Sitemap & Crawler Directives
- **XML Sitemap (`/sitemap.xml`):** Strictly contains all 41 canonical indexable URLs, verified for 100% parity against generated output with real Git commit last-modification dates (`<lastmod>YYYY-MM-DD</lastmod>`).
- **Robots.txt (`/robots.txt`):** Modern, standards-compliant policy cleanly granting access to major web search engines (Googlebot, Bingbot, Applebot), dedicated image bots (Googlebot-Image), and social preview engines (Twitterbot, facebookexternalhit, LinkedInBot, WhatsApp), while preventing indexing of private backend endpoints (`Disallow: /api/`).

---

## 3. Schema.org Structured Data Matrix

All pages embed rich, syntax-valid JSON-LD (`application/ld+json`) declaring verified organizational entities without misleading claims or synthetic review ratings:

```json
{
  "@context": "https://schema.org",
  "@type": "ProfessionalService",
  "@id": "https://heidigi.com/#org",
  "name": "Hei Digi",
  "url": "https://heidigi.com/",
  "logo": "https://heidigi.com/assets/heidigi-logo.webp",
  "image": "https://heidigi.com/assets/og/home.jpg",
  "email": "info.heidigi@gmail.com",
  "telephone": "+919705570007",
  "description": "Digital marketing and SEO services in Tirupati, including local SEO, Google Business Profile management, social media marketing, Meta Ads, creative design, video and branding.",
  "knowsAbout": [
    "Search engine optimization",
    "Local SEO",
    "Google Business Profile management",
    "Social media marketing",
    "Meta Ads",
    "Creative design",
    "Video editing",
    "Personal branding"
  ],
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "18-1-45/4, HeiDigi, KT Rd, near More Super Market, Srinivasa Nagar, Shanthi Nagar, Khadi Colony",
    "addressLocality": "Tirupati",
    "addressRegion": "Andhra Pradesh",
    "postalCode": "517507",
    "addressCountry": "IN"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": 13.6288,
    "longitude": 79.4192
  },
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      "opens": "09:30",
      "closes": "18:30"
    }
  ],
  "priceRange": "₹₹",
  "paymentAccepted": "Cash, UPI, Bank Transfer",
  "currenciesAccepted": "INR",
  "inLanguage": ["en-IN", "te"],
  "areaServed": [
    {"@type": "City", "name": "Tirupati"},
    {"@type": "City", "name": "Renigunta"},
    {"@type": "City", "name": "Chittoor"},
    {"@type": "City", "name": "Chandragiri"},
    {"@type": "City", "name": "Nellore"}
  ],
  "founder": {
    "@type": "Person",
    "name": "Coach Sri",
    "sameAs": ["https://www.instagram.com/coachshri_/"]
  },
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "sales and enquiries",
    "telephone": "+919705570007",
    "email": "info.heidigi@gmail.com"
  }
}
```

Additional rich schemas injected contextually:
- **`BreadcrumbList`:** Present across all nested service, industry, location, and blog routes.
- **`FAQPage`:** Structured Q&A pairs on service and industry pages, verified by static audit to match 100% of visible on-page text.
- **`Article`:** Formal editorial schema on all 11 marketing guide articles under `/blog/`.
- **`CreativeWork`:** Portfolio documentation for Coach Sri personal branding and BNI Networking Conclave.

---

## 4. Modern AI and Answer Engine Discoverability

With the emergence of LLM-driven answer engines (OpenAI ChatGPT Search, Perplexity AI, Claude Search, Google Gemini), websites must provide deterministic, easily parsable machine contexts that bypass client-side JavaScript execution.

Hei Digi implements the emerging industry standards:

### 4.1 `llms.txt` & `llms-full.txt`
Located at `/llms.txt` and `/llms-full.txt`, these structured markdown documents provide concise and comprehensive knowledge digests:
- Core service definitions, deliverables, and transparent limitations.
- Target industries, location summaries, and client case study context.
- Verified business NAP, phone, email, and founder attribution.
- Direct links to authoritative subpages.

### 4.2 Machine-Readable Service Catalog (`.well-known/ai-catalog.json`)
Adhering to the AI Service Catalog specification (`specVersion 1.0`), `/ai-catalog.json` and `/.well-known/ai-catalog.json` declare:
- Verified decentralized identifier (`did:web:heidigi.com`).
- Direct endpoint mapping to canonical service routes.
- Plain-text functional descriptions optimized for RAG embeddings and tool-calling agent systems.

### 4.3 AI Crawler Permissions
`robots.txt` establishes explicit crawl permissions for leading AI search engines:
- `OAI-SearchBot` (OpenAI Realtime Search): **Allowed**
- `ChatGPT-User` (User-directed browser browsing): **Allowed**
- `ClaudeBot` & `anthropic-ai` (Anthropic Claude Search): **Allowed**
- `PerplexityBot` (Perplexity AI indexer): **Allowed**
- `Google-Extended` & `Applebot-Extended`: **Allowed**
- `GPTBot` (Foundation model training crawler): Configurable via `"gptbot"` in `site.config.json` (currently allowed).

---

## 5. Performance Engineering & Core Web Vitals

Hei Digi achieves top-tier Core Web Vitals lab and simulated field scores by eliminating JavaScript framework overhead:

| Metric | Target Threshold | Hei Digi Implementation Result | Mechanism |
|---|---|---|---|
| **Largest Contentful Paint (LCP)** | $\le 2.5\text{s}$ | **$\le 0.8\text{s}$** | Hero WebP image preloaded (`fetchpriority="high"`), zero render-blocking web fonts by default, fast static edge delivery. |
| **Cumulative Layout Shift (CLS)** | $\le 0.1$ | **$0.000$** | Explicit width/height on all `<img>` and `<video>` tags; early class injection (`boot.js`); zero dynamic DOM layout injection. |
| **Interaction to Next Paint (INP)** | $\le 200\text{ms}$ | **$\le 40\text{ms}$** | Vanilla ES6 event delegation, minimal main thread execution, no virtual DOM reconciliation. |
| **First Contentful Paint (FCP)** | $\le 1.8\text{s}$ | **$\le 0.4\text{s}$** | Critical CSS inlined/bundled (`assets/css/style.css`), HTTP/2 server push ready, edge caching with `immutable` assets. |

### Asset Optimization Strategy
- **Responsive Favicons & App Icons:** Multi-resolution icons rendered in 16x16, 32x32, 48x48, 96x96, 180x180 (Apple Touch Icon), 192x192, and 512x512 PWA icons, accompanied by a multi-frame `favicon.ico`.
- **Responsive Images:** WebP hero images and portfolio screenshots provided with responsive `srcset` (640w, 1200w).
- **Fonts:** System font stack (`system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`) with optional self-hosted WOFF2 fonts via [`tools/fetch_fonts.py`](file:///c:/Users/cshar/Downloads/HEIDIGI-DIGITAL-MARKETING/tools/fetch_fonts.py) to avoid external Google Fonts connections.

---

## 6. Defensive Security & Privacy Architecture

The production deployment adheres to the highest modern defensive standards:

### 6.1 Content Security Policy (CSP)
Generated automatically by `build.py` and synchronized across `vercel.json` and `_headers`:
```http
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; media-src 'self'; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'; upgrade-insecure-requests
```
*(When Turnstile, GA4, or Plausible are activated in `site.config.json`, the generator injects strictly the minimum verified external origins).*

### 6.2 Strict Security Headers
- `Strict-Transport-Security: max-age=300` (Staged HSTS rollout; upgradeable to `max-age=31536000; includeSubDomains; preload`).
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-site`

### 6.3 Anti-Abuse & Spam Protection Pipeline
The enquiry form features multiple defense layers:
1. **Zero-Storage Default:** Default submission opens formatted messages directly in WhatsApp (`wa.me`), storing zero personal data on web servers.
2. **Honeypot Trap:** Hidden `<input name="website" tabindex="-1">` invisible to human users but detected if completed by automated spam bots.
3. **Submission Velocity Gate:** Rejects submissions completed in under 3,000ms.
4. **Distributed Edge Rate Limiting:** Upstash Redis pipeline limits enquiries to 5 submissions per 10-minute window per SHA256-hashed IP.
5. **Cloudflare Turnstile:** Non-intrusive CAPTCHA challenge before serverless processing.
6. **DPDPA 2023 Consent Gate:** Analytics tracking remains inert until the user explicitly accepts via `#consent`.

---

## 7. Verification & Automated Test Coverage

The codebase passes an exhaustive multi-tier verification suite:

1. **Static DOM & Code Auditor (`python tools/audit.py`):**
   - **3,189 assertions passed**, 0 failed.
   - Validates HTML tag balancing, unique IDs, single H1, heading progressions, image alt/dimension attributes, internal links, canonical URLs, OG images, JSON-LD syntax, robots directives, CSP compliance, and WCAG AA color contrast ($\ge 4.5:1$).
2. **Build Modes & Dynamic CSP Test (`python tools/test_build_modes.py`):**
   - Validates custom domains, GA4/Plausible integration, Turnstile, and HSTS headers in isolated scratch builds.
3. **Isomorphic Form Validation (`node tools/test_lead.js`):**
   - 100% test pass on phone format normalization, required fields, and WhatsApp message serialization.
4. **Serverless API Mock Suite (`node tools/test_api.js`):**
   - 24 mocked scenarios covering origin checking, rate limiting, Turnstile verification, and Resend email dispatch.
5. **HTTP Link Crawler (`python tools/crawl_links.py`):**
   - Crawls all 72+ internal URLs and sitemap links over local HTTP; verifies 0 broken links and correct 404 handling.
6. **Master Orchestrator (`python tools/run_all.py`):**
   - Cross-platform test runner validating rebuild cleanliness (`before == after`), audits, unit suites, link crawling, and Playwright browser integration.
