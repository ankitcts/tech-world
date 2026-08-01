import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { makePatternCanvas } from "./patterns.js";

/* TechAtlas — a plain, highly-interactive 3D field of company logo tiles.
   No hubs, no connectors: every company is an independent, lit, beveled tile
   that drifts and slowly spins. Hover to focus, click for details, filter by
   domain or search. Data comes from companies.json (exported from MongoDB). */

const REDUCE = window.matchMedia("(prefers-reduced-motion:reduce)").matches;
const el = (id) => document.getElementById(id);
const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const scene = new THREE.Scene();
const container = el("scene");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.appendChild(renderer.domElement);

scene.add(new THREE.AmbientLight(0xffffff, 0.95));
const key = new THREE.DirectionalLight(0xffffff, 0.75); key.position.set(4, 6, 8); scene.add(key);
const fill = new THREE.DirectionalLight(0xffffff, 0.3); fill.position.set(-6, -3, -5); scene.add(fill);

const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
camera.position.set(0, 0, 22);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.07; controls.enablePan = false;
controls.minDistance = 12; controls.maxDistance = 40;
controls.autoRotate = !REDUCE; controls.autoRotateSpeed = 0.25;

const root = new THREE.Group(); scene.add(root);

let DOMAINS = [], COMPANIES = [], domainById = {}, coNodes = [];
let hovered = null, selected = null, activeDomains = new Set(), query = "";
const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2();
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const lum = (hex) => { const m = hex.replace("#", ""); return (0.299 * parseInt(m.substr(0, 2), 16) + 0.587 * parseInt(m.substr(2, 2), 16) + 0.114 * parseInt(m.substr(4, 2), 16)) / 255; };
const rnd = (a, b) => a + Math.random() * (b - a);

function fib(i, n, R) {
  const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), phi = i * Math.PI * (3 - Math.sqrt(5));
  return V(Math.cos(phi) * r, y, Math.sin(phi) * r).multiplyScalar(R);
}

function labelTexture(text, ink, halo) {
  const f = 34, pad = 10;
  const m = document.createElement("canvas").getContext("2d");
  m.font = `600 ${f}px system-ui,sans-serif`;
  const w = Math.ceil(m.measureText(text).width) + pad * 2;
  const c = document.createElement("canvas"); c.width = w; c.height = f + pad * 2;
  const g = c.getContext("2d");
  g.font = `600 ${f}px system-ui,sans-serif`; g.textAlign = "center"; g.textBaseline = "middle";
  g.lineWidth = 5; g.lineJoin = "round"; g.strokeStyle = halo; g.strokeText(text, c.width / 2, c.height / 2);
  g.fillStyle = ink; g.fillText(text, c.width / 2, c.height / 2);
  const t = new THREE.CanvasTexture(c); t.anisotropy = 4; return { tex: t, aspect: c.width / c.height };
}

function build() {
  const ink = cssv("--ink"), bg = cssv("--bg");
  coNodes = COMPANIES.map((c, i) => {
    const base = fib(i, COMPANIES.length, 8.4).add(V(rnd(-0.6, 0.6), rnd(-0.6, 0.6), rnd(-0.6, 0.6)));
    const tex = new THREE.CanvasTexture(makePatternCanvas(c));
    tex.anisotropy = 4; tex.colorSpace = THREE.SRGBColorSpace;
    const face = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.5, metalness: 0.2, transparent: true });
    const edge = new THREE.MeshStandardMaterial({ color: new THREE.Color((c.palette && c.palette[0]) || c.color), roughness: 0.4, metalness: 0.3, transparent: true });
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 0.16), [edge, edge, edge, edge, face, face]);
    mesh.position.copy(base); mesh.userData = { type: "co", data: c }; root.add(mesh);
    const lab = labelTexture(c.name, ink, bg);
    const nm = new THREE.Sprite(new THREE.SpriteMaterial({ map: lab.tex, transparent: true, depthTest: false }));
    nm.scale.set(0.5 * lab.aspect, 0.5, 1); root.add(nm);
    return {
      data: c, mesh, label: nm, face, edge, base,
      // independent motion params
      drift: { ax: rnd(0.15, 0.4), ay: rnd(0.15, 0.4), az: rnd(0.15, 0.4), px: rnd(0, 6.28), py: rnd(0, 6.28), pz: rnd(0, 6.28), sp: rnd(0.15, 0.35) },
      spin: rnd(0.15, 0.5) * (Math.random() < 0.5 ? -1 : 1),
      tilt: rnd(0, 6.28),
      scale: 0.86, targetScale: 0.86,
    };
  });
  controls.target.set(0, 0, 0);
}

function matchCompany(c) {
  const mq = !query || c.name.toLowerCase().includes(query);
  const md = activeDomains.size === 0 || c.domains.some((d) => activeDomains.has(d));
  return mq && md;
}

/* ---------- interaction ---------- */
function updatePointer(e) { const r = renderer.domElement.getBoundingClientRect();
  pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1; pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1; }
function pick() {
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(coNodes.map((n) => n.mesh), false)[0];
  return hit ? coNodes.find((n) => n.mesh === hit.object) : null;
}
let down = false, moved = false;
renderer.domElement.addEventListener("pointermove", (e) => {
  updatePointer(e); if (down) { moved = true; return; }
  hovered = pick(); renderer.domElement.style.cursor = hovered ? "pointer" : "grab";
});
renderer.domElement.addEventListener("pointerdown", () => { down = true; moved = false; });
renderer.domElement.addEventListener("pointerup", () => {
  if (!moved) { const n = pick();
    if (n) { selected = n; openPanel(n.data); } else { selected = null; closePanel(); } }
  down = false;
});

/* ---------- panel ---------- */
const panel = el("panel");
function openPanel(c) {
  el("p-name").textContent = c.name;
  el("p-hq").textContent = `${c.hq}${c.ticker && c.ticker !== "—" ? " · " + c.ticker : ""}`;
  el("p-blurb").textContent = c.blurb;
  const p0 = (c.palette && c.palette[0]) || c.color;
  const mono = el("p-mono"); mono.textContent = c.mono; mono.style.background = p0;
  mono.style.color = lum(p0) > 0.7 ? "#111" : "#fff";
  const dc = el("p-domains"); dc.innerHTML = "";
  c.domains.forEach((id) => { const d = domainById[id]; const s = document.createElement("span"); s.textContent = d.label; s.style.background = d.color; dc.appendChild(s); });
  panel.hidden = false; requestAnimationFrame(() => panel.classList.add("open"));
}
function closePanel() { panel.classList.remove("open"); setTimeout(() => { panel.hidden = true; }, 320); }
el("p-close").addEventListener("click", () => { selected = null; closePanel(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { selected = null; closePanel(); } });

/* ---------- filters ---------- */
function toggleDomain(id) {
  if (activeDomains.has(id)) activeDomains.delete(id); else activeDomains.add(id);
  [...el("chips").children].forEach((b) => b.setAttribute("aria-pressed", activeDomains.has(b.dataset.id) ? "true" : "false"));
  updateCount();
}
function buildChips() {
  const wrap = el("chips");
  DOMAINS.forEach((d) => {
    const b = document.createElement("button"); b.className = "chip"; b.dataset.id = d.id;
    b.setAttribute("aria-pressed", "false"); b.style.setProperty("--dc", d.color);
    b.innerHTML = '<span class="dot"></span>' + d.label;
    b.addEventListener("click", () => toggleDomain(d.id)); wrap.appendChild(b);
  });
}
el("search").addEventListener("input", (e) => { query = e.target.value.trim().toLowerCase(); updateCount(); });
function updateCount() { el("count").textContent = `${COMPANIES.filter(matchCompany).length} / ${COMPANIES.length} companies`; }

function buildA11y() {
  let html = "<h2>U.S. tech companies by technology domain</h2>";
  DOMAINS.forEach((d) => { html += `<h3>${d.label}</h3><ul>`;
    COMPANIES.filter((c) => c.domains.includes(d.id)).forEach((c) => { html += `<li>${c.name} — ${c.blurb}</li>`; });
    html += "</ul>"; });
  el("a11y-list").innerHTML = html;
}

/* ---------- loop ---------- */
function resize() { const r = container.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false); camera.aspect = r.width / Math.max(1, r.height); camera.updateProjectionMatrix(); }
window.addEventListener("resize", resize);

const clock = new THREE.Clock();
const camQ = new THREE.Quaternion();
function tick() {
  const t = clock.getElapsedTime();
  const active = selected || hovered;
  const anyFilter = activeDomains.size > 0 || query.length > 0;
  coNodes.forEach((n) => {
    const vis = matchCompany(n.data);
    const isActive = active === n;
    // opacity: filtered-out or dimmed-by-focus
    let o = vis ? 1 : (anyFilter ? 0.06 : 1);
    if (active && !isActive) o = Math.min(o, 0.14);
    n.face.opacity = o; n.edge.opacity = o; n.label.material.opacity = Math.min(o, 0.95);
    n.mesh.visible = o > 0.02; n.label.visible = o > 0.02 && (isActive || (!active && vis));
    // motion (independent drift + spin), frozen when focused or reduced-motion
    const d = n.drift;
    const pos = n.base.clone();
    if (!REDUCE && !isActive) pos.add(V(Math.sin(t * d.sp + d.px) * d.ax, Math.sin(t * d.sp * 0.9 + d.py) * d.ay, Math.sin(t * d.sp * 1.1 + d.pz) * d.az));
    n.mesh.position.copy(pos);
    n.label.position.copy(pos).add(V(0, 0.66, 0));
    if (isActive) {
      // face the camera + pop
      camera.getWorldQuaternion(camQ); n.mesh.quaternion.slerp(camQ, 0.2);
      n.targetScale = 1.4;
    } else {
      n.targetScale = 0.86;
      if (!REDUCE) { n.mesh.rotation.y += n.spin * 0.01; n.mesh.rotation.x = Math.sin(t * 0.4 + n.tilt) * 0.22; }
    }
    n.scale += (n.targetScale - n.scale) * 0.18;
    n.mesh.scale.setScalar(n.scale);
  });
  controls.autoRotate = !REDUCE && !active;
  controls.update(); renderer.render(scene, camera); requestAnimationFrame(tick);
}

/* ---------- boot ---------- */
async function boot() {
  try {
    const res = await fetch("./companies.json", { cache: "no-store" });
    const data = await res.json();
    DOMAINS = data.domains; COMPANIES = data.companies;
    domainById = Object.fromEntries(DOMAINS.map((d) => [d.id, d]));
    build(); buildChips(); buildA11y(); updateCount(); resize(); tick();
  } catch (err) {
    container.innerHTML = `<p style="padding:2rem;color:var(--muted);font-family:var(--font-mono)">Could not load companies.json — run the pipeline export first.<br>${err}</p>`;
  }
}
boot();

new MutationObserver(() => {
  const ink = cssv("--ink"), bg = cssv("--bg");
  coNodes.forEach((n) => { const lab = labelTexture(n.data.name, ink, bg);
    n.label.material.map.dispose(); n.label.material.map = lab.tex; n.label.material.needsUpdate = true; });
}).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
