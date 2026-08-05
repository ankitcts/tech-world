/* TechAtlas landing page — Netflix-style logo rows + a per-company detail tab.

   The view is fully data-driven: no company data is hardcoded here. Data comes
   from /api/companies (live from MongoDB) and falls back to the committed
   ./companies.json. Domains, employee tiers, and leadership all render from
   whatever the data provides — nothing invented.

   - Home: one slowly auto-scrolling row of logos per domain (pause on hover;
     static + swipeable when the visitor prefers reduced motion).
   - Click a logo: opens ?company=<id> in a NEW TAB — a deep-linkable detail
     page with the company's domains, employee tier, and leadership/board
     (sourced from SEC filings, with citations; unverified data is never shown). */

import {
  siApple, siGoogle, siMeta, siNvidia, siTesla, siNetflix, siIntel, siAmd,
  siQualcomm, siBroadcom, siCisco, siPaypal, siCoinbase, siVisa, siUber,
  siAirbnb, siDoordash, siSnowflake, siDatabricks, siPalantir, siSnapchat, siStripe,
} from "simple-icons";

const ICONS = {};
[siApple, siGoogle, siMeta, siNvidia, siTesla, siNetflix, siIntel, siAmd,
 siQualcomm, siBroadcom, siCisco, siPaypal, siCoinbase, siVisa, siUber,
 siAirbnb, siDoordash, siSnowflake, siDatabricks, siPalantir, siSnapchat, siStripe]
  .forEach((i) => { ICONS[i.slug] = i; });

const app = document.getElementById("app");
let DOMAIN_BY_ID = {};

/* ---------- helpers ---------- */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

function hashHue(str) { let h = 0; for (const ch of String(str)) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return h % 360; }
function fallbackColor(name) { return `hsl(${hashHue(name)} 44% 30%)`; }
function lum(hex) {
  const m = hex.replace("#", ""); if (m.length < 6) return 0.3;
  return (0.299 * parseInt(m.slice(0, 2), 16) + 0.587 * parseInt(m.slice(2, 4), 16)
    + 0.114 * parseInt(m.slice(4, 6), 16)) / 255;
}
const ink = (bg) => (bg.startsWith("#") && lum(bg) > 0.62 ? "#0B0D12" : "#ffffff");
function initials(c) {
  if (c.mono) return c.mono;
  const w = String(c.name).trim().split(/\s+/).filter(Boolean);
  return (((w[0] || "")[0] || "") + ((w[1] || "")[0] || "")).toUpperCase() || "•";
}
const tileBg = (c) => c.color || fallbackColor(c.name);

function logoInner(c) {
  const fg = ink(tileBg(c));
  const icon = c.icon && ICONS[c.icon];
  if (icon) return `<svg viewBox="0 0 24 24" aria-hidden="true" fill="${fg}"><path d="${esc(icon.path)}"/></svg>`;
  return `<span class="mono" style="color:${fg}">${esc(initials(c))}</span>`;
}

function card(c) {
  return `<a class="card" href="?company=${encodeURIComponent(c.id)}" target="_blank" rel="noopener"
             aria-label="${esc(c.name)} — open details in a new tab">
    <span class="tile" style="background:${esc(tileBg(c))}">${logoInner(c)}</span>
    <span class="name">${esc(c.name)}</span>
    ${c.ticker ? `<span class="tkr">${esc(c.ticker)}</span>` : ""}
  </a>`;
}

function rail(companies, index) {
  // Repeat short lists so the marquee fills the width, then duplicate the whole
  // sequence once so translateX(-50%) loops seamlessly.
  let list = companies.slice();
  while (list.length && list.length < 10) list = list.concat(companies);
  const half = list.map(card).join("");
  const dir = index % 2 ? "rev" : "fwd";
  const dur = 52 + (index % 3) * 20;
  return `<div class="rail" data-dir="${dir}" style="--dur:${dur}s">
    <div class="track">${half}${half}</div>
  </div>`;
}

/* ---------- home ---------- */
function renderHome(data) {
  document.title = "TechAtlas — U.S. Companies by Domain";
  const rows = data.domains.map((d, i) => {
    const companies = data.companies.filter((c) => (c.domains || []).includes(d.id));
    if (!companies.length) return "";
    return `<section class="row">
      <div class="row-head">
        <h2><span class="dot" style="--dc:${esc(d.color || "var(--accent)")}"></span>${esc(d.label)}</h2>
        <span class="n">${companies.length}</span>
      </div>
      ${rail(companies, i)}
    </section>`;
  }).join("");

  app.innerHTML = `
    <section class="hero">
      <div class="eyebrow">U.S. companies · by domain</div>
      <h1>The companies shaping <em>U.S. technology</em>.</h1>
      <p class="sub">Browse by industry domain. Pick a company to see its domains, employee
      tier, and leadership — all sourced from authoritative filings.</p>
    </section>
    <div class="rows">${rows || `<p class="empty">No companies to show yet.</p>`}</div>`;
}

/* ---------- detail (new tab) ---------- */
function domainChips(c) {
  const spans = (c.domains || []).map((id) => {
    const d = DOMAIN_BY_ID[id];
    return d ? `<span style="background:${esc(d.color || "var(--accent)")}">${esc(d.label)}</span>` : "";
  }).join("");
  return spans ? `<div class="dchips">${spans}</div>` : "";
}

function leadershipSection(c) {
  const led = Array.isArray(c.leadership) ? c.leadership : [];
  if (led.length) {
    const cards = led.map((p) => `<div class="leader">
      <div class="nm">${esc(p.name)}</div>
      <div class="ti">${esc(p.title || "")}</div>
      ${p.role_type ? `<span class="rl">${esc(p.role_type)}</span>` : ""}
      ${p.source_url ? `<a class="cite" href="${esc(p.source_url)}" target="_blank" rel="noopener">SEC filing${p.as_of ? ` · ${esc(p.as_of)}` : ""} ↗</a>` : ""}
    </div>`).join("");
    return `<section class="section">
      <h3>Leadership &amp; board</h3>
      <p class="note">From SEC filings — DEF 14A proxy · Forms 3/4/5. Each entry links to its source.</p>
      <div class="leaders">${cards}</div>
    </section>`;
  }
  return `<section class="section">
    <h3>Leadership &amp; board</h3>
    <div class="pending"><b>Not yet ingested.</b> The CEO, CTO, other executive officers and the
    board of directors are drawn from this company's <b>SEC filings</b> — DEF 14A proxy statements
    (full board + officers) and Forms 3/4/5 (officer/director records with titles) — each with a link
    to its source. They appear here once the filings pipeline has processed this company.
    Unverified names are never shown.
    <div class="how">source: SEC EDGAR · DEF 14A / Forms 3,4,5</div></div>
  </section>`;
}

function employeesRow(c) {
  const e = c.employees;
  if (e && e.value != null) {
    const src = e.source_url
      ? ` · <a href="${esc(e.source_url)}" target="_blank" rel="noopener" style="color:var(--accent)">source${e.as_of ? ` (${esc(e.as_of)})` : ""} ↗</a>` : "";
    return `<dt>Employees</dt><dd>${Number(e.value).toLocaleString()}${e.tier ? ` · tier ${esc(e.tier)}` : ""}${src}</dd>`;
  }
  return `<dt>Employees</dt><dd>Unknown — sourced from the SEC 10-K when available</dd>`;
}

function renderDetail(data, id) {
  const c = data.companies.find((x) => x.id === id);
  if (!c) {
    document.title = "Company not found — TechAtlas";
    app.innerHTML = `<article class="detail"><a class="back" href="./">← All companies</a>
      <p class="empty">No company matches “${esc(id)}”.</p></article>`;
    return;
  }
  document.title = `${c.name} — TechAtlas`;
  const bg = tileBg(c);
  const domainList = (c.domains || []).map((did) => esc(DOMAIN_BY_ID[did]?.label || did)).join(", ") || "—";

  app.innerHTML = `<article class="detail">
    <a class="back" href="./">← All companies</a>
    <div class="detail-top">
      <span class="big" style="background:${esc(bg)}">${logoInner(c)}</span>
      <div>
        <h1>${esc(c.name)}</h1>
        ${c.ticker ? `<div class="tkr">${esc(c.ticker)}</div>` : ""}
        ${c.hq ? `<div class="hq">${esc(c.hq)}</div>` : ""}
      </div>
    </div>
    ${c.blurb ? `<p class="blurb">${esc(c.blurb)}</p>` : ""}
    ${domainChips(c)}
    ${leadershipSection(c)}
    <dl class="kv">
      ${c.ticker ? `<dt>Ticker</dt><dd>${esc(c.ticker)}</dd>` : ""}
      ${c.hq ? `<dt>HQ</dt><dd>${esc(c.hq)}</dd>` : ""}
      ${employeesRow(c)}
      <dt>Domains</dt><dd>${domainList}</dd>
    </dl>
  </article>`;
}

/* ---------- boot ---------- */
async function load() {
  for (const url of ["/api/companies", "./companies.json"]) {
    try {
      const r = await fetch(url, { cache: "no-store" });
      if (r.ok) return await r.json();
    } catch { /* try next */ }
  }
  return null;
}

(async () => {
  const data = await load();
  if (!data) {
    app.innerHTML = `<p class="empty">Could not load company data. The pipeline export may not have run yet.</p>`;
    return;
  }
  data.domains = data.domains || [];
  data.companies = data.companies || [];
  DOMAIN_BY_ID = Object.fromEntries(data.domains.map((d) => [d.id, d]));
  const id = new URLSearchParams(location.search).get("company");
  if (id) renderDetail(data, id); else renderHome(data);
})();
