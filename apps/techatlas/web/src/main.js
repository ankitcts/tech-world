import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

/* TechAtlas — 3D constellation of U.S. tech companies linked to technology
   domains. Data is loaded from companies.json (exported from MongoDB; the app
   itself hardcodes no company data). */

const REDUCE = window.matchMedia("(prefers-reduced-motion:reduce)").matches;
const el = (id) => document.getElementById(id);
const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const scene = new THREE.Scene();
const container = el("scene");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
container.appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 100);
camera.position.set(0, 0, 20);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.enablePan = false;
controls.minDistance = 9;
controls.maxDistance = 34;
controls.autoRotate = !REDUCE;
controls.autoRotateSpeed = 0.55;

const root = new THREE.Group();
scene.add(root);

let DOMAINS = [], COMPANIES = [], domainById = {};
let coNodes = [], domNodes = [], baseLinks = null, hlLinks = null;
let hovered = null, selected = null;
let activeDomains = new Set(), query = "";
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

/* ---------- texture helpers ---------- */
function discTexture(text, fill, textColor) {
  const s = 128, c = document.createElement("canvas"); c.width = c.height = s;
  const g = c.getContext("2d");
  g.beginPath(); g.arc(s / 2, s / 2, s / 2 - 6, 0, Math.PI * 2);
  g.fillStyle = fill; g.fill();
  g.lineWidth = 6; g.strokeStyle = "rgba(255,255,255,.30)"; g.stroke();
  g.fillStyle = textColor; g.font = "800 52px system-ui,sans-serif";
  g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(text, s / 2, s / 2 + 2);
  const t = new THREE.CanvasTexture(c); t.anisotropy = 4; return t;
}
function labelTexture(text, ink, halo) {
  const pad = 10, f = 34;
  const m = document.createElement("canvas").getContext("2d");
  m.font = `600 ${f}px system-ui,sans-serif`;
  const w = Math.ceil(m.measureText(text).width) + pad * 2;
  const c = document.createElement("canvas"); c.width = w; c.height = f + pad * 2;
  const g = c.getContext("2d");
  g.font = `600 ${f}px system-ui,sans-serif`;
  g.textAlign = "center"; g.textBaseline = "middle";
  g.lineWidth = 5; g.strokeStyle = halo; g.lineJoin = "round";
  g.strokeText(text, c.width / 2, c.height / 2);
  g.fillStyle = ink; g.fillText(text, c.width / 2, c.height / 2);
  const t = new THREE.CanvasTexture(c); t.anisotropy = 4;
  return { tex: t, aspect: c.width / c.height };
}
function lum(hex) {
  const m = hex.replace("#", "");
  const r = parseInt(m.substr(0, 2), 16), g = parseInt(m.substr(2, 2), 16), b = parseInt(m.substr(4, 2), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

/* ---------- layout ---------- */
function fib(i, n, R) { // point i of n on a sphere
  const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y);
  const phi = i * Math.PI * (3 - Math.sqrt(5));
  return new THREE.Vector3(Math.cos(phi) * r, y, Math.sin(phi) * r).multiplyScalar(R);
}
function layout() {
  DOMAINS.forEach((d, i) => { d._pos = fib(i, DOMAINS.length, 6.6); });
  COMPANIES.forEach((c) => {
    const p = new THREE.Vector3();
    c.domains.forEach((id) => p.add(domainById[id]._pos));
    p.multiplyScalar(1 / Math.max(1, c.domains.length));
    p.add(new THREE.Vector3((Math.random() - 0.5) * 2, (Math.random() - 0.5) * 2, (Math.random() - 0.5) * 2));
    c._pos = p;
  });
  for (let iter = 0; iter < 140; iter++) {
    for (let i = 0; i < COMPANIES.length; i++) {
      const a = COMPANIES[i]; const f = new THREE.Vector3();
      for (let j = 0; j < COMPANIES.length; j++) {
        if (i === j) continue;
        const d = new THREE.Vector3().subVectors(a._pos, COMPANIES[j]._pos);
        const dist = d.length() || 0.01;
        if (dist < 2.15) f.add(d.multiplyScalar((2.15 - dist) / dist * 0.5));
      }
      const centroid = new THREE.Vector3();
      a.domains.forEach((id) => centroid.add(domainById[id]._pos));
      centroid.multiplyScalar(1 / Math.max(1, a.domains.length));
      f.add(new THREE.Vector3().subVectors(centroid, a._pos).multiplyScalar(0.06));
      a._pos.add(f.multiplyScalar(0.5));
    }
  }
}

/* ---------- build scene ---------- */
function build() {
  const ink = cssv("--ink"), bg = cssv("--bg");
  // domain hubs
  domNodes = DOMAINS.map((d) => {
    const geo = new THREE.SphereGeometry(0.5, 24, 24);
    const mat = new THREE.MeshBasicMaterial({ color: new THREE.Color(d.color) });
    const mesh = new THREE.Mesh(geo, mat); mesh.position.copy(d._pos);
    mesh.userData = { type: "domain", data: d }; root.add(mesh);
    const lab = labelTexture(d.label, "#ffffff", "rgba(0,0,0,.45)");
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: lab.tex, transparent: true, depthTest: false }));
    sp.scale.set(0.62 * lab.aspect, 0.62, 1); sp.position.copy(d._pos).add(new THREE.Vector3(0, 0.92, 0));
    root.add(sp);
    return { type: "domain", data: d, mesh, label: sp };
  });
  // company nodes
  coNodes = COMPANIES.map((c) => {
    const tc = lum(c.color) > 0.7 ? "#111" : "#fff";
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: discTexture(c.mono, c.color, tc), transparent: true, depthTest: true }));
    sp.scale.set(0.72, 0.72, 1); sp.position.copy(c._pos);
    sp.userData = { type: "co", data: c }; root.add(sp);
    const lab = labelTexture(c.name, ink, bg);
    const nm = new THREE.Sprite(new THREE.SpriteMaterial({ map: lab.tex, transparent: true, depthTest: false }));
    nm.scale.set(0.5 * lab.aspect, 0.5, 1); nm.position.copy(c._pos).add(new THREE.Vector3(0, 0.5, 0));
    nm.userData = { label: true };
    root.add(nm);
    return { type: "co", data: c, sprite: sp, label: nm, base: c._pos.clone() };
  });
  buildLinks();
  frameCamera();
}
function buildLinks() {
  const pts = [], cols = [];
  COMPANIES.forEach((c) => c.domains.forEach((id) => {
    const d = domainById[id];
    pts.push(c._pos.x, c._pos.y, c._pos.z, d._pos.x, d._pos.y, d._pos.z);
    const col = new THREE.Color(d.color);
    cols.push(col.r, col.g, col.b, col.r, col.g, col.b);
  }));
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3));
  baseLinks = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.14 }));
  root.add(baseLinks);
}
function frameCamera() {
  const box = new THREE.Box3().setFromObject(root);
  const c = box.getCenter(new THREE.Vector3());
  controls.target.copy(c); camera.lookAt(c);
}

/* ---------- highlight ---------- */
function setHighlight(node) {
  if (hlLinks) { root.remove(hlLinks); hlLinks.geometry.dispose(); hlLinks = null; }
  const active = node ? new Set() : null;
  if (node) {
    const pts = [], cols = [];
    const addLink = (c, id) => {
      const d = domainById[id];
      pts.push(c._pos.x, c._pos.y, c._pos.z, d._pos.x, d._pos.y, d._pos.z);
      const col = new THREE.Color(d.color);
      cols.push(col.r, col.g, col.b, col.r, col.g, col.b);
    };
    if (node.type === "co") {
      active.add(node.data.id);
      node.data.domains.forEach((id) => { active.add("dom:" + id); addLink(node.data, id); });
    } else {
      active.add("dom:" + node.data.id);
      COMPANIES.forEach((c) => { if (c.domains.includes(node.data.id)) { active.add(c.id); addLink(c, node.data.id); } });
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3));
    hlLinks = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.85 }));
    root.add(hlLinks);
  }
  applyDim(active);
}
function matchCompany(c) {
  const mq = !query || c.name.toLowerCase().includes(query);
  const md = activeDomains.size === 0 || c.domains.some((d) => activeDomains.has(d));
  return mq && md;
}
function applyDim(activeSet) {
  const anyFilter = activeDomains.size > 0 || query.length > 0;
  coNodes.forEach((n) => {
    let vis = matchCompany(n.data);
    if (activeSet && !activeSet.has(n.data.id)) vis = false;
    const o = vis ? 1 : (anyFilter || activeSet ? 0.08 : 1);
    n.sprite.material.opacity = o; n.label.material.opacity = Math.min(o, 0.95);
    const s = (activeSet && activeSet.has(n.data.id)) ? 0.92 : 0.72;
    n.sprite.scale.set(s, s, 1);
  });
  domNodes.forEach((n) => {
    const on = !activeSet || activeSet.has("dom:" + n.data.id);
    n.mesh.material.opacity = on ? 1 : 0.25; n.mesh.material.transparent = true;
    n.label.material.opacity = on ? 1 : 0.25;
  });
  baseLinks.material.opacity = activeSet ? 0.04 : (anyFilter ? 0.06 : 0.14);
}

/* ---------- interaction ---------- */
function updatePointer(e) {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1;
}
function pick() {
  raycaster.setFromCamera(pointer, camera);
  const targets = [...coNodes.map((n) => n.sprite), ...domNodes.map((n) => n.mesh)];
  const hit = raycaster.intersectObjects(targets, false)[0];
  return hit ? hit.object.userData : null;
}
let down = null, moved = false;
renderer.domElement.addEventListener("pointermove", (e) => {
  updatePointer(e);
  if (down) { moved = true; return; }
  const ud = pick();
  const node = ud ? (ud.type === "co" ? coNodes.find((n) => n.data === ud.data) : domNodes.find((n) => n.data === ud.data)) : null;
  hovered = node;
  renderer.domElement.style.cursor = node ? "pointer" : "grab";
  if (!selected) setHighlight(node);
});
renderer.domElement.addEventListener("pointerdown", () => { down = true; moved = false; });
renderer.domElement.addEventListener("pointerup", () => {
  if (!moved) {
    const ud = pick();
    if (ud && ud.type === "co") { selected = coNodes.find((n) => n.data === ud.data); setHighlight(selected); openPanel(ud.data); }
    else if (ud && ud.type === "domain") { toggleDomain(ud.data.id); selected = null; }
    else { selected = null; setHighlight(null); closePanel(); }
  }
  down = false;
});

/* ---------- panel ---------- */
const panel = el("panel");
function openPanel(c) {
  el("p-name").textContent = c.name;
  el("p-hq").textContent = `${c.hq}${c.ticker && c.ticker !== "—" ? " · " + c.ticker : ""}`;
  el("p-blurb").textContent = c.blurb;
  const mono = el("p-mono"); mono.textContent = c.mono; mono.style.background = c.color;
  mono.style.color = lum(c.color) > 0.7 ? "#111" : "#fff";
  const dc = el("p-domains"); dc.innerHTML = "";
  c.domains.forEach((id) => { const d = domainById[id]; const s = document.createElement("span"); s.textContent = d.label; s.style.background = d.color; dc.appendChild(s); });
  panel.hidden = false; requestAnimationFrame(() => panel.classList.add("open"));
}
function closePanel() { panel.classList.remove("open"); setTimeout(() => { panel.hidden = true; }, 320); }
el("p-close").addEventListener("click", () => { selected = null; setHighlight(null); closePanel(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { selected = null; setHighlight(null); closePanel(); } });

/* ---------- filters ---------- */
function toggleDomain(id) {
  if (activeDomains.has(id)) activeDomains.delete(id); else activeDomains.add(id);
  [...el("chips").children].forEach((b) => b.setAttribute("aria-pressed", activeDomains.has(b.dataset.id) ? "true" : "false"));
  if (!selected) setHighlight(null); else applyDim(null);
  updateCount();
}
function buildChips() {
  const wrap = el("chips");
  DOMAINS.forEach((d) => {
    const b = document.createElement("button"); b.className = "chip"; b.dataset.id = d.id;
    b.setAttribute("aria-pressed", "false"); b.style.setProperty("--dc", d.color);
    b.innerHTML = '<span class="dot"></span>' + d.label;
    b.addEventListener("click", () => toggleDomain(d.id));
    wrap.appendChild(b);
  });
}
el("search").addEventListener("input", (e) => { query = e.target.value.trim().toLowerCase(); if (!selected) setHighlight(null); else applyDim(null); updateCount(); });
function updateCount() {
  const vis = COMPANIES.filter(matchCompany).length;
  el("count").textContent = `${vis} / ${COMPANIES.length} companies`;
}

/* ---------- a11y list ---------- */
function buildA11y() {
  let html = "<h2>U.S. tech companies by technology domain</h2>";
  DOMAINS.forEach((d) => {
    html += `<h3>${d.label}</h3><ul>`;
    COMPANIES.filter((c) => c.domains.includes(d.id)).forEach((c) => { html += `<li>${c.name} — ${c.blurb}</li>`; });
    html += "</ul>";
  });
  el("a11y-list").innerHTML = html;
}

/* ---------- resize + loop ---------- */
function resize() {
  const r = container.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false);
  camera.aspect = r.width / Math.max(1, r.height); camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
function tick() { controls.update(); renderer.render(scene, camera); requestAnimationFrame(tick); }

/* ---------- boot ---------- */
async function boot() {
  try {
    const res = await fetch("./companies.json", { cache: "no-store" });
    const data = await res.json();
    DOMAINS = data.domains; COMPANIES = data.companies;
    domainById = Object.fromEntries(DOMAINS.map((d) => [d.id, d]));
    layout(); build(); buildChips(); buildA11y(); updateCount(); resize();
    tick();
  } catch (err) {
    container.innerHTML = `<p style="padding:2rem;color:var(--muted);font-family:var(--font-mono)">Could not load companies.json — run the pipeline export first.<br>${err}</p>`;
  }
}
boot();

// regenerate theme-dependent labels when the viewer toggles theme
new MutationObserver(() => {
  const ink = cssv("--ink"), bg = cssv("--bg");
  coNodes.forEach((n) => {
    const lab = labelTexture(n.data.name, ink, bg);
    n.label.material.map.dispose(); n.label.material.map = lab.tex; n.label.material.needsUpdate = true;
  });
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
