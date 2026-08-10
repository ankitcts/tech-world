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
  siSeagate, siDell, siHp, siAutodesk, siIntuit, siDatadog, siMongodb, siCloudflare,
  siOkta, siPaloaltonetworks, siFortinet, siGitlab, siHubspot, siDropbox, siBox,
  siAsana, siDigitalocean, siUnity, siAkamai, siReddit, siPinterest, siRoblox,
  siEbay, siZoom, siLyft, siRobinhood,
} from "simple-icons";

const ICONS = {};
[siApple, siGoogle, siMeta, siNvidia, siTesla, siNetflix, siIntel, siAmd,
 siQualcomm, siBroadcom, siCisco, siPaypal, siCoinbase, siVisa, siUber,
 siAirbnb, siDoordash, siSnowflake, siDatabricks, siPalantir, siSnapchat, siStripe,
 siSeagate, siDell, siHp, siAutodesk, siIntuit, siDatadog, siMongodb, siCloudflare,
 siOkta, siPaloaltonetworks, siFortinet, siGitlab, siHubspot, siDropbox, siBox,
 siAsana, siDigitalocean, siUnity, siAkamai, siReddit, siPinterest, siRoblox,
 siEbay, siZoom, siLyft, siRobinhood]
  .forEach((i) => { ICONS[i.slug] = i; });

/* Curated presentation (logos, brand colors, blurbs) for well-known companies.
   Bundled from the seed so brand identity survives even when the live SEC data
   only carries name/ticker. Keyed by uppercased ticker. */
import seedData from "../public/companies.json";
const CURATED = {};
for (const c of seedData.companies || []) {
  if (c.ticker) CURATED[c.ticker.toUpperCase()] = c;
}
const curatedFor = (c) => (c && c.ticker ? CURATED[String(c.ticker).toUpperCase()] : null);
const SEED_DOMAIN_IDS = new Set((seedData.domains || []).map((d) => d.id));

// Merge the curated seed with the live SEC data: curated companies keep their
// identity (logo/blurb/domains) and are ENRICHED with live SEC facts (employee
// tier, leadership, hq) matched by ticker; the SEC long-tail is added on top.
function mergeWithSeed(live) {
  const domainById = {};
  for (const d of seedData.domains || []) domainById[d.id] = d;
  for (const d of live.domains || []) if (!domainById[d.id]) domainById[d.id] = d;

  const keyOf = (c) => (c.ticker ? "T:" + String(c.ticker).toUpperCase() : "I:" + c.id);
  const byKey = new Map();
  for (const c of seedData.companies || []) byKey.set(keyOf(c), { ...c });
  for (const lc of live.companies || []) {
    const k = keyOf(lc);
    const cur = byKey.get(k);
    if (cur) {
      byKey.set(k, {
        ...cur,
        hq: cur.hq || lc.hq,
        cik: lc.cik ?? cur.cik,
        sic: lc.sic ?? cur.sic,
        sic_description: lc.sic_description ?? cur.sic_description,
        employees: lc.employees ?? cur.employees,
        leadership: lc.leadership && lc.leadership.length ? lc.leadership : cur.leadership,
        domains: Array.from(new Set([...(cur.domains || []), ...(lc.domains || [])])),
      });
    } else {
      byKey.set(k, lc);
    }
  }
  const companies = Array.from(byKey.values());
  const referenced = new Set();
  companies.forEach((c) => (c.domains || []).forEach((d) => referenced.add(d)));
  const domains = Object.values(domainById).filter((d) => referenced.has(d.id));
  return { domains, companies };
}

const app = document.getElementById("app");
let DOMAIN_BY_ID = {};
let DATA = { domains: [], companies: [] };
let DATA_SOURCE = "static";
let VIEW = "rows";   // "rows" | "list"
let QUERY = "";

// Live = served from MongoDB by the daily SEC agent; otherwise the curated seed.
function sourceBadge() {
  const live = DATA_SOURCE === "mongo";
  const label = live ? "Live · MongoDB" : "Sample data · seed";
  const color = live ? "#2ecc71" : "#E9A23B";
  const title = live
    ? "Served live from MongoDB (updated by the daily SEC EDGAR agent)."
    : "Showing the curated seed. Live data appears once the SEC pipeline has populated MongoDB on Vercel.";
  return `<span class="src-badge" title="${esc(title)}">
    <span class="src-dot" style="background:${color}"></span>${esc(label)}</span>`;
}

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
  const cur = curatedFor(c);
  if (c.mono || cur?.mono) return c.mono || cur.mono;
  const w = String(c.name).trim().split(/\s+/).filter(Boolean);
  return (((w[0] || "")[0] || "") + ((w[1] || "")[0] || "")).toUpperCase() || "•";
}
const tileBg = (c) => c.color || curatedFor(c)?.color || fallbackColor(c.name);

// Neutral "no verified logo" placeholder — a broken-image glyph shown whenever
// we don't have a VERIFIED brand mark, instead of guessing/faking a logo.
const PLACEHOLDER_BG = "#141B2C";
function brokenLogoSVG() {
  return '<svg class="ph-logo" viewBox="0 0 24 24" fill="none" stroke="#6B7890" '
    + 'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    + '<rect x="3" y="3" width="18" height="18" rx="3"/>'
    + '<circle cx="9" cy="9.5" r="1.5"/>'
    + '<path d="M4.5 17.5l4.2-4.6 3.3 3.3 3-3.2 4 4.3"/>'
    + '<path d="M4.5 4.5l15 15"/></svg>';
}

// Broken-logo glyph is reused by the <img> onerror fallback below.
window.__thBrokenLogo = brokenLogoSVG;

// Returns {bg, inner} for a company tile. Logo priority, VERIFIED sources only:
//   1. curated simple-icons brand mark (hand-checked), else
//   2. the company's own official logo resolved from Wikidata (P249 ticker →
//      P154 logo on Wikimedia Commons) — entity-verified, not a ticker-image
//      guess; if the image 404s at runtime it falls back to the placeholder,
//   3. the broken-logo placeholder — never a logo faked from a ticker service.
function tileParts(c) {
  const slug = c.icon || curatedFor(c)?.icon;
  const icon = slug && ICONS[slug];
  if (icon) {
    const bg = tileBg(c);
    return { bg, inner: `<svg viewBox="0 0 24 24" aria-hidden="true" fill="${ink(bg)}"><path d="${esc(icon.path)}"/></svg>` };
  }
  const url = c.logo_url || curatedFor(c)?.logo_url;
  if (url) {
    return { bg: "#FFFFFF", inner: `<img class="logo-img" src="${esc(url)}" alt="" loading="lazy" onerror="this.outerHTML=window.__thBrokenLogo()">` };
  }
  return { bg: PLACEHOLDER_BG, inner: brokenLogoSVG() };
}

function logoInner(c) { return tileParts(c).inner; }

function card(c) {
  const { bg, inner } = tileParts(c);
  return `<a class="card" href="?company=${encodeURIComponent(c.id)}" target="_blank" rel="noopener"
             aria-label="${esc(c.name)} — open details in a new tab">
    <span class="tile" style="background:${esc(bg)}">${inner}</span>
    <span class="name">${esc(c.name)}</span>
    ${c.ticker ? `<span class="tkr">${esc(c.ticker)}</span>` : ""}
  </a>`;
}

function rail(companies, index) {
  const CARD = 162; // card width + gap (px)
  const pad = Math.min(32, Math.max(16, window.innerWidth * 0.04));
  const containerW = Math.min(window.innerWidth, 1240) - 2 * pad;
  const contentW = companies.length * CARD;

  // Fits within the visible row → render once, no loop (static).
  if (contentW <= containerW) {
    return `<div class="rail is-static">
      <div class="track is-static">${companies.map(card).join("")}</div>
    </div>`;
  }
  // Overflows the visible width → seamless marquee (two copies, translateX(-50%)).
  const half = companies.map(card).join("");
  const dir = index % 2 ? "rev" : "fwd";
  const dur = Math.round(companies.length * 3) + 16;
  return `<div class="rail" data-dir="${dir}" style="--dur:${dur}s">
    <div class="track">${half}${half}</div>
  </div>`;
}

/* ---------- home ---------- */
const matches = (c, q) => !q
  || String(c.name).toLowerCase().includes(q)
  || String(c.ticker || "").toLowerCase().includes(q);

function listItem(c) {
  const doms = (c.domains || []).map((id) => DOMAIN_BY_ID[id]?.label || id).join(" · ");
  const { bg, inner } = tileParts(c);
  return `<a class="litem" href="?company=${encodeURIComponent(c.id)}" target="_blank" rel="noopener">
    <span class="sw" style="background:${esc(bg)}">${inner}</span>
    <span class="li-name">${esc(c.name)}${c.ticker ? ` <span class="li-tkr">${esc(c.ticker)}</span>` : ""}</span>
    <span class="li-dom">${esc(doms)}</span>
    <span class="li-hq">${esc(c.hq || "")}</span>
  </a>`;
}

function renderContent() {
  const q = QUERY.trim().toLowerCase();
  const box = document.getElementById("home-content");
  const count = document.getElementById("home-count");
  const pool = DATA.companies.filter((c) => matches(c, q));
  if (count) count.textContent = `${pool.length} compan${pool.length === 1 ? "y" : "ies"}`;

  if (VIEW === "list") {
    const items = [...pool].sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
    box.innerHTML = items.length
      ? `<div class="list">${items.map(listItem).join("")}</div>`
      : `<p class="empty">No companies match “${esc(q)}”.</p>`;
    return;
  }
  // Build rows, fullest first. Skip sparse SIC domains (unless curated) so we
  // don't get dozens of one-company rows while the SEC backfill is still thin.
  const rows = DATA.domains
    .map((d) => ({ d, companies: pool.filter((c) => (c.domains || []).includes(d.id)) }))
    .filter(({ d, companies }) => companies.length
      && (companies.length >= 3 || SEED_DOMAIN_IDS.has(d.id)))
    .sort((a, b) => b.companies.length - a.companies.length)
    .map(({ d, companies }, i) => `<section class="row">
      <div class="row-head">
        <h2><span class="dot" style="--dc:${esc(d.color || "var(--accent)")}"></span>${esc(d.label)}</h2>
        <span class="n">${companies.length}</span>
      </div>
      ${rail(companies, i)}
    </section>`).join("");
  box.innerHTML = `<div class="rows">${rows || `<p class="empty">No companies match “${esc(q)}”.</p>`}</div>`;
}

function renderHome() {
  document.title = "TechAtlas — U.S. Companies by Domain";
  app.innerHTML = `
    <section class="hero">
      <div class="eyebrow">U.S. companies · by domain ${sourceBadge()}</div>
      <h1>The companies shaping <em>U.S. technology</em>.</h1>
      <p class="sub">Browse by industry domain, or switch to a searchable list. Pick a company
      to see its domains, employee tier, and leadership — sourced from authoritative filings.</p>
    </section>
    <div class="toolbar">
      <div class="toggle" role="tablist" aria-label="View mode">
        <button id="view-rows" role="tab" aria-selected="${VIEW === "rows"}" class="${VIEW === "rows" ? "on" : ""}">Rows</button>
        <button id="view-list" role="tab" aria-selected="${VIEW === "list"}" class="${VIEW === "list" ? "on" : ""}">List</button>
      </div>
      <div class="search">
        <input id="home-search" type="search" placeholder="Search companies…" aria-label="Search companies" value="${esc(QUERY)}">
      </div>
      <span class="home-count" id="home-count" aria-live="polite"></span>
    </div>
    <div id="home-content"></div>`;

  const setView = (v) => {
    VIEW = v;
    document.getElementById("view-rows").classList.toggle("on", v === "rows");
    document.getElementById("view-list").classList.toggle("on", v === "list");
    document.getElementById("view-rows").setAttribute("aria-selected", String(v === "rows"));
    document.getElementById("view-list").setAttribute("aria-selected", String(v === "list"));
    renderContent();
  };
  document.getElementById("view-rows").addEventListener("click", () => setView("rows"));
  document.getElementById("view-list").addEventListener("click", () => setView("list"));
  document.getElementById("home-search").addEventListener("input", (e) => {
    QUERY = e.target.value;
    renderContent();
  });
  renderContent();
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
  const { bg, inner } = tileParts(c);
  const domainList = (c.domains || []).map((did) => esc(DOMAIN_BY_ID[did]?.label || did)).join(", ") || "—";

  app.innerHTML = `<article class="detail">
    <a class="back" href="./">← All companies</a>
    <div class="detail-top">
      <span class="big" style="background:${esc(bg)}">${inner}</span>
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
      if (r.ok) {
        const data = await r.json();
        DATA_SOURCE = r.headers.get("X-Data-Source")
          || (url.startsWith("/api") ? "api" : "static");
        return data;
      }
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
  DATA = mergeWithSeed(data);
  DOMAIN_BY_ID = Object.fromEntries(DATA.domains.map((d) => [d.id, d]));
  const id = new URLSearchParams(location.search).get("company");
  if (id) renderDetail(DATA, id); else renderHome();
})();
