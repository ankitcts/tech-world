import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { makePatternCanvas } from "./patterns.js";

/* TechAtlas — 3D constellation of U.S. tech companies. Each company is a lit,
   beveled logo-tile carrying its exact brand colors + a distinct pattern.
   Two views: grouped "by domain", or spread "independent". Data comes from
   companies.json (exported from MongoDB); no company data is hardcoded here. */

const REDUCE = window.matchMedia("(prefers-reduced-motion:reduce)").matches;
const el = (id) => document.getElementById(id);
const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const scene = new THREE.Scene();
const container = el("scene");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
renderer.outputColorSpace = THREE.SRGBColorSpace;
container.appendChild(renderer.domElement);

scene.add(new THREE.AmbientLight(0xffffff, 0.92));
const key = new THREE.DirectionalLight(0xffffff, 0.7); key.position.set(4, 6, 8); scene.add(key);
const fill = new THREE.DirectionalLight(0xffffff, 0.32); fill.position.set(-6, -3, -5); scene.add(fill);

const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 100);
camera.position.set(0, 0, 21);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = 0.06; controls.enablePan = false;
controls.minDistance = 10; controls.maxDistance = 36;
controls.autoRotate = !REDUCE; controls.autoRotateSpeed = 0.5;

const root = new THREE.Group(); scene.add(root);

let DOMAINS = [], COMPANIES = [], domainById = {};
let coNodes = [], domNodes = [], baseLinks = null, hlLinks = null;
let hovered = null, selected = null, activeDomains = new Set(), query = "";
let view = "domain", viewMix = 1, viewTarget = 1; // 1 = by domain, 0 = independent
const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2();
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const lum = (hex) => { const m = hex.replace("#", ""); return (0.299 * parseInt(m.substr(0, 2), 16) + 0.587 * parseInt(m.substr(2, 2), 16) + 0.114 * parseInt(m.substr(4, 2), 16)) / 255; };

/* ---------- layout ---------- */
function fib(i, n, R) {
  const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), phi = i * Math.PI * (3 - Math.sqrt(5));
  return V(Math.cos(phi) * r, y, Math.sin(phi) * r).multiplyScalar(R);
}
function layout() {
  DOMAINS.forEach((d, i) => { d._pos = fib(i, DOMAINS.length, 6.6); });
  COMPANIES.forEach((c, i) => {
    const p = V(0, 0, 0);
    c.domains.forEach((id) => p.add(domainById[id]._pos));
    p.multiplyScalar(1 / Math.max(1, c.domains.length));
    p.add(V((Math.random() - 0.5) * 2, (Math.random() - 0.5) * 2, (Math.random() - 0.5) * 2));
    c._dom = p; c._ind = fib(i, COMPANIES.length, 8.2);
  });
  for (let it = 0; it < 130; it++) {
    for (let i = 0; i < COMPANIES.length; i++) {
      const a = COMPANIES[i], f = V(0, 0, 0);
      for (let j = 0; j < COMPANIES.length; j++) {
        if (i === j) continue;
        const d = new THREE.Vector3().subVectors(a._dom, COMPANIES[j]._dom);
        const dist = d.length() || 0.01;
        if (dist < 2.15) f.add(d.multiplyScalar((2.15 - dist) / dist * 0.5));
      }
      const ctr = V(0, 0, 0); a.domains.forEach((id) => ctr.add(domainById[id]._pos));
      ctr.multiplyScalar(1 / Math.max(1, a.domains.length));
      f.add(new THREE.Vector3().subVectors(ctr, a._dom).multiplyScalar(0.06));
      a._dom.add(f.multiplyScalar(0.5));
    }
  }
  COMPANIES.forEach((c) => { c._pos = c._dom.clone(); });
}

/* ---------- textures ---------- */
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

/* ---------- build ---------- */
function build() {
  const ink = cssv("--ink"), bg = cssv("--bg");
  domNodes = DOMAINS.map((d) => {
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 24, 24),
      new THREE.MeshStandardMaterial({ color: new THREE.Color(d.color), roughness: 0.45, metalness: 0.1, transparent: true }));
    mesh.position.copy(d._pos); mesh.userData = { type: "domain", data: d }; root.add(mesh);
    const lab = labelTexture(d.label, "#ffffff", "rgba(0,0,0,.45)");
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: lab.tex, transparent: true, depthTest: false }));
    sp.scale.set(0.62 * lab.aspect, 0.62, 1); sp.position.copy(d._pos).add(V(0, 0.92, 0)); root.add(sp);
    return { type: "domain", data: d, mesh, label: sp };
  });
  coNodes = COMPANIES.map((c) => {
    const tex = new THREE.CanvasTexture(makePatternCanvas(c));
    tex.anisotropy = 4; tex.colorSpace = THREE.SRGBColorSpace;
    const face = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.5, metalness: 0.18, transparent: true });
    const edgeCol = (c.palette && c.palette[0]) || c.color;
    const edge = new THREE.MeshStandardMaterial({ color: new THREE.Color(edgeCol), roughness: 0.4, metalness: 0.25, transparent: true });
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 0.15), [edge, edge, edge, edge, face, face]);
    mesh.scale.setScalar(0.86); mesh.position.copy(c._pos);
    mesh.userData = { type: "co", data: c }; root.add(mesh);
    const lab = labelTexture(c.name, ink, bg);
    const nm = new THREE.Sprite(new THREE.SpriteMaterial({ map: lab.tex, transparent: true, depthTest: false }));
    nm.scale.set(0.5 * lab.aspect, 0.5, 1); nm.position.copy(c._pos).add(V(0, 0.62, 0)); root.add(nm);
    return { type: "co", data: c, mesh, label: nm, face, edge };
  });
  buildLinks(); frameCamera();
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
function updateLinkPositions() {
  const pos = baseLinks.geometry.getAttribute("position"); let k = 0;
  COMPANIES.forEach((c) => c.domains.forEach((id) => {
    const d = domainById[id];
    pos.setXYZ(k++, c._pos.x, c._pos.y, c._pos.z);
    pos.setXYZ(k++, d._pos.x, d._pos.y, d._pos.z);
  }));
  pos.needsUpdate = true;
}
function frameCamera() {
  const c = new THREE.Box3().setFromObject(root).getCenter(V(0, 0, 0));
  controls.target.copy(c);
}

/* ---------- highlight + dim ---------- */
function matchCompany(c) {
  const mq = !query || c.name.toLowerCase().includes(query);
  const md = activeDomains.size === 0 || c.domains.some((d) => activeDomains.has(d));
  return mq && md;
}
function setHighlight(node) {
  if (hlLinks) { root.remove(hlLinks); hlLinks.geometry.dispose(); hlLinks = null; }
  let active = null;
  if (node && viewMix > 0.5) {
    active = new Set(); const pts = [], cols = [];
    const addLink = (c, id) => { const d = domainById[id];
      pts.push(c._pos.x, c._pos.y, c._pos.z, d._pos.x, d._pos.y, d._pos.z);
      const col = new THREE.Color(d.color); cols.push(col.r, col.g, col.b, col.r, col.g, col.b); };
    if (node.type === "co") { active.add(node.data.id); node.data.domains.forEach((id) => { active.add("dom:" + id); addLink(node.data, id); }); }
    else { active.add("dom:" + node.data.id); COMPANIES.forEach((c) => { if (c.domains.includes(node.data.id)) { active.add(c.id); addLink(c, node.data.id); } }); }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3));
    hlLinks = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 }));
    root.add(hlLinks);
  } else if (node) { active = new Set([node.type === "co" ? node.data.id : "dom:" + node.data.id]); if (node.type === "domain") COMPANIES.forEach((c) => { if (c.domains.includes(node.data.id)) active.add(c.id); }); if (node.type === "co") node.data.domains.forEach((id) => active.add("dom:" + id)); }
  applyDim(active);
}
function applyDim(activeSet) {
  const anyFilter = activeDomains.size > 0 || query.length > 0;
  coNodes.forEach((n) => {
    let vis = matchCompany(n.data);
    if (activeSet && !activeSet.has(n.data.id)) vis = false;
    const o = vis ? 1 : (anyFilter || activeSet ? 0.08 : 1);
    n.face.opacity = o; n.edge.opacity = o; n.label.material.opacity = Math.min(o, 0.95);
    const s = (activeSet && activeSet.has(n.data.id)) ? 1.0 : 0.86;
    n.mesh.scale.setScalar(s);
  });
  domNodes.forEach((n) => {
    const on = !activeSet || activeSet.has("dom:" + n.data.id);
    n._dim = on ? 1 : 0.25;
  });
  baseLinks.material.opacity = (activeSet ? 0.04 : (anyFilter ? 0.06 : 0.14)) * viewMix;
}

/* ---------- interaction ---------- */
function updatePointer(e) { const r = renderer.domElement.getBoundingClientRect();
  pointer.x = ((e.clientX - r.left) / r.width) * 2 - 1; pointer.y = -((e.clientY - r.top) / r.height) * 2 + 1; }
function pick() {
  raycaster.setFromCamera(pointer, camera);
  const targets = [...coNodes.map((n) => n.mesh), ...domNodes.map((n) => n.mesh)];
  const hit = raycaster.intersectObjects(targets, false)[0];
  return hit ? hit.object.userData : null;
}
let down = false, moved = false;
renderer.domElement.addEventListener("pointermove", (e) => {
  updatePointer(e); if (down) { moved = true; return; }
  const ud = pick();
  const node = ud ? (ud.type === "co" ? coNodes.find((n) => n.data === ud.data) : domNodes.find((n) => n.data === ud.data)) : null;
  hovered = node; renderer.domElement.style.cursor = node ? "pointer" : "grab";
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
  const mono = el("p-mono"); mono.textContent = c.mono; mono.style.background = (c.palette && c.palette[0]) || c.color;
  mono.style.color = lum((c.palette && c.palette[0]) || c.color) > 0.7 ? "#111" : "#fff";
  const dc = el("p-domains"); dc.innerHTML = "";
  c.domains.forEach((id) => { const d = domainById[id]; const s = document.createElement("span"); s.textContent = d.label; s.style.background = d.color; dc.appendChild(s); });
  panel.hidden = false; requestAnimationFrame(() => panel.classList.add("open"));
}
function closePanel() { panel.classList.remove("open"); setTimeout(() => { panel.hidden = true; }, 320); }
el("p-close").addEventListener("click", () => { selected = null; setHighlight(null); closePanel(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { selected = null; setHighlight(null); closePanel(); } });

/* ---------- filters + view ---------- */
function toggleDomain(id) {
  if (activeDomains.has(id)) activeDomains.delete(id); else activeDomains.add(id);
  [...el("chips").children].forEach((b) => b.setAttribute("aria-pressed", activeDomains.has(b.dataset.id) ? "true" : "false"));
  setHighlight(selected); updateCount();
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
el("search").addEventListener("input", (e) => { query = e.target.value.trim().toLowerCase(); setHighlight(selected); updateCount(); });
function updateCount() { el("count").textContent = `${COMPANIES.filter(matchCompany).length} / ${COMPANIES.length} companies`; }

function setView(v) {
  view = v; viewTarget = v === "domain" ? 1 : 0;
  el("view-domain").setAttribute("aria-pressed", v === "domain" ? "true" : "false");
  el("view-indep").setAttribute("aria-pressed", v === "independent" ? "true" : "false");
  if (v === "independent") { selected = null; setHighlight(null); closePanel(); }
}
el("view-domain").addEventListener("click", () => setView("domain"));
el("view-indep").addEventListener("click", () => setView("independent"));

/* ---------- a11y ---------- */
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

const tmp = new THREE.Vector3();
function tick() {
  const animating = Math.abs(viewTarget - viewMix) > 0.001;
  if (animating) viewMix += (viewTarget - viewMix) * 0.08;
  // position morph between independent and domain layouts
  if (animating || viewMix > 0.999 || viewMix < 0.001) {
    coNodes.forEach((n) => {
      tmp.copy(n.data._ind).lerp(n.data._dom, viewMix);
      n.data._pos.copy(tmp); n.mesh.position.copy(tmp);
      n.label.position.copy(tmp).add(V(0, 0.62, 0));
      n.mesh.lookAt(tmp.clone().multiplyScalar(2)); // face outward
    });
    updateLinkPositions();
  }
  // fade domain scaffolding out in independent view
  domNodes.forEach((n) => { const a = viewMix * (n._dim ?? 1);
    n.mesh.material.opacity = a; n.label.material.opacity = a; n.mesh.visible = a > 0.02; n.label.visible = a > 0.02; });
  if (!hlLinks) baseLinks.material.opacity = (activeDomains.size || query ? 0.06 : 0.14) * viewMix;
  controls.update(); renderer.render(scene, camera); requestAnimationFrame(tick);
}

/* ---------- boot ---------- */
async function boot() {
  try {
    const res = await fetch("./companies.json", { cache: "no-store" });
    const data = await res.json();
    DOMAINS = data.domains; COMPANIES = data.companies;
    domainById = Object.fromEntries(DOMAINS.map((d) => [d.id, d]));
    layout(); build(); buildChips(); buildA11y(); updateCount(); resize(); tick();
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
