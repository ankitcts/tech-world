/* Procedural brand-emblem textures.

   Each company gets a distinct geometric pattern drawn in its EXACT brand
   colors, so nodes are recognizable independently. These are original,
   stylized emblems (color + pattern), not reproductions of trademarked logos —
   swap in official logo art later if you hold the rights. */

function lum(hex) {
  const m = hex.replace("#", "");
  const r = parseInt(m.substr(0, 2), 16), g = parseInt(m.substr(2, 2), 16), b = parseInt(m.substr(4, 2), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}
const ink = (bg) => (lum(bg) > 0.6 ? "#111111" : "#ffffff");

function drawMono(g, S, text, color) {
  g.fillStyle = color;
  g.font = `800 ${S * 0.16}px system-ui,sans-serif`;
  g.textAlign = "left"; g.textBaseline = "alphabetic";
  g.globalAlpha = 0.9;
  g.fillText(text, S * 0.08, S * 0.94);
  g.globalAlpha = 1;
}

const DRAW = {
  quad(g, S, p) {
    const c = [p[0], p[1] || p[0], p[2] || p[0], p[3] || p[1] || p[0]];
    const h = S / 2, gap = S * 0.04;
    const cells = [[0, 0], [1, 0], [0, 1], [1, 1]];
    cells.forEach(([x, y], i) => {
      g.fillStyle = c[i];
      g.fillRect(x * h + gap, y * h + gap, h - gap * 2, h - gap * 2);
    });
  },
  smile(g, S, p) {
    g.fillStyle = p[1] || "#232F3E"; g.fillRect(0, 0, S, S);
    g.strokeStyle = p[0]; g.lineCap = "round"; g.lineWidth = S * 0.11;
    g.beginPath(); g.arc(S / 2, S * 0.42, S * 0.32, 0.15 * Math.PI, 0.85 * Math.PI); g.stroke();
    // arrowhead
    g.beginPath(); g.moveTo(S * 0.70, S * 0.66); g.lineTo(S * 0.80, S * 0.74); g.lineTo(S * 0.66, S * 0.78);
    g.closePath(); g.fillStyle = p[0]; g.fill();
  },
  orbit(g, S, p) {
    g.fillStyle = p[0]; g.fillRect(0, 0, S, S);
    const ringC = p[2] || ink(p[0]);
    g.strokeStyle = ringC; g.lineWidth = S * 0.045;
    g.beginPath(); g.ellipse(S / 2, S / 2, S * 0.34, S * 0.20, -0.5, 0, Math.PI * 2); g.stroke();
    g.fillStyle = p[1] || ink(p[0]); g.beginPath(); g.arc(S / 2, S / 2, S * 0.13, 0, 7); g.fill();
    g.fillStyle = ringC; g.beginPath(); g.arc(S * 0.80, S * 0.36, S * 0.05, 0, 7); g.fill();
  },
  chevron(g, S, p) {
    g.fillStyle = p[1] || ink(p[0]); g.fillRect(0, 0, S, S);
    g.fillStyle = p[0];
    for (let i = 0; i < 2; i++) {
      const o = i * S * 0.26;
      g.beginPath();
      g.moveTo(S * 0.5, S * 0.22 + o); g.lineTo(S * 0.78, S * 0.5 + o);
      g.lineTo(S * 0.72, S * 0.58 + o); g.lineTo(S * 0.5, S * 0.38 + o);
      g.lineTo(S * 0.28, S * 0.58 + o); g.lineTo(S * 0.22, S * 0.5 + o);
      g.closePath(); g.fill();
    }
  },
  bars(g, S, p) {
    g.fillStyle = p[1] && lum(p[1]) < 0.9 ? p[1] : "#0d0d0d"; g.fillRect(0, 0, S, S);
    const n = 5, w = S * 0.1, gap = (S - n * w) / (n + 1);
    const hs = [0.42, 0.7, 0.5, 0.85, 0.6];
    for (let i = 0; i < n; i++) {
      const x = gap + i * (w + gap), h = S * hs[i];
      g.fillStyle = p[0]; g.fillRect(x, (S - h) / 2, w, h);
    }
  },
  split(g, S, p) {
    g.fillStyle = p[0]; g.fillRect(0, 0, S, S);
    g.fillStyle = p[1] || ink(p[0]);
    g.beginPath(); g.moveTo(S, 0); g.lineTo(S, S); g.lineTo(0, S); g.closePath(); g.fill();
    g.strokeStyle = "rgba(255,255,255,.5)"; g.lineWidth = S * 0.02;
    g.beginPath(); g.moveTo(S, 0); g.lineTo(0, S); g.stroke();
  },
  ring(g, S, p) {
    g.fillStyle = p[1] && lum(p[1]) > 0.85 ? p[1] : "#ffffff"; g.fillRect(0, 0, S, S);
    const rings = 4;
    for (let i = rings; i >= 1; i--) {
      g.fillStyle = i % 2 ? p[0] : (p[1] || "#ffffff");
      g.beginPath(); g.arc(S / 2, S / 2, (S * 0.44) * (i / rings), 0, 7); g.fill();
    }
  },
  stripes(g, S, p) {
    g.fillStyle = p[1] || "#ffffff"; g.fillRect(0, 0, S, S);
    g.fillStyle = p[0];
    const n = 6, h = S * 0.072, gap = (S - n * h) / (n + 1);
    for (let i = 0; i < n; i++) g.fillRect(S * 0.14, gap + i * (h + gap), S * 0.72, h);
  },
  hex(g, S, p) {
    g.fillStyle = p[1] || ink(p[0]); g.fillRect(0, 0, S, S);
    const cx = S / 2, cy = S / 2, r = S * 0.34;
    g.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 6 + i * Math.PI / 3;
      const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.closePath(); g.fillStyle = p[0]; g.fill();
    g.fillStyle = p[1] || "#fff"; g.beginPath(); g.arc(cx, cy, r * 0.42, 0, 7); g.fill();
  },
  grid(g, S, p) {
    g.fillStyle = p[0]; g.fillRect(0, 0, S, S);
    g.fillStyle = p[1] || ink(p[0]);
    const n = 4, r = S * 0.05, gap = S / (n + 1);
    for (let i = 1; i <= n; i++) for (let j = 1; j <= n; j++) {
      g.beginPath(); g.arc(i * gap, j * gap, r, 0, 7); g.fill();
    }
  },
  spark(g, S, p) {
    g.fillStyle = p[0]; g.fillRect(0, 0, S, S);
    const cx = S / 2, cy = S / 2, petals = 6;
    g.fillStyle = p[1] || ink(p[0]);
    for (let i = 0; i < petals; i++) {
      const a = i * (Math.PI * 2 / petals);
      g.save(); g.translate(cx, cy); g.rotate(a);
      g.beginPath(); g.ellipse(S * 0.24, 0, S * 0.16, S * 0.055, 0, 0, 7); g.fill();
      g.restore();
    }
    g.beginPath(); g.arc(cx, cy, S * 0.08, 0, 7); g.fill();
  },
  wordmark(g, S, p) {
    g.fillStyle = p[0]; g.fillRect(0, 0, S, S);
  },
};

export function makePatternCanvas(company) {
  const S = 256;
  const c = document.createElement("canvas"); c.width = c.height = S;
  const g = c.getContext("2d");
  const p = company.palette && company.palette.length ? company.palette : [company.color];
  (DRAW[company.pattern] || DRAW.wordmark)(g, S, p);
  // monogram for recognition (skip on quad where 4 colors already read)
  if (company.pattern !== "quad") drawMono(g, S, company.mono, ink(p[0]));
  else drawMono(g, S, company.mono, "#111");
  return c;
}
