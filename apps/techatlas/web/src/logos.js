/* Real company logos, extruded into true 3D.

   Uses the `simple-icons` library (official brand marks as SVG paths + brand
   hex colors) and Three's SVGLoader + ExtrudeGeometry to build a genuine 3D
   mesh of each logo. Only the needed icons are imported by name so the bundle
   stays small and tree-shaken.

   Logos are the trademarks of their respective owners; they are shown here to
   identify each company in a factual directory. */

import * as THREE from "three";
import { SVGLoader } from "three/addons/loaders/SVGLoader.js";
import {
  siApple, siGoogle, siMeta, siNvidia, siTesla, siNetflix, siIntel, siAmd,
  siQualcomm, siBroadcom, siCisco, siPaypal, siCoinbase, siVisa, siUber,
  siAirbnb, siDoordash, siSnowflake, siDatabricks, siPalantir, siSnapchat, siStripe,
} from "simple-icons";

const ICONS = {};
[siApple, siGoogle, siMeta, siNvidia, siTesla, siNetflix, siIntel, siAmd,
 siQualcomm, siBroadcom, siCisco, siPaypal, siCoinbase, siVisa, siUber,
 siAirbnb, siDoordash, siSnowflake, siDatabricks, siPalantir, siSnapchat, siStripe]
  .forEach((v) => { ICONS[v.slug] = v; });

const loader = new SVGLoader();
const lum = (hex) => { const m = hex.replace("#", ""); return (0.299 * parseInt(m.substr(0, 2), 16) + 0.587 * parseInt(m.substr(2, 2), 16) + 0.114 * parseInt(m.substr(4, 2), 16)) / 255; };

export function hasLogo(slug) { return !!ICONS[slug]; }

export function makeLogoMesh(slug) {
  const icon = ICONS[slug];
  if (!icon) return null;
  const svg = `<svg viewBox="0 0 24 24"><path d="${icon.path}"/></svg>`;
  const shapes = [];
  loader.parse(svg).paths.forEach((p) => SVGLoader.createShapes(p).forEach((s) => shapes.push(s)));
  if (!shapes.length) return null;

  const geo = new THREE.ExtrudeGeometry(shapes, {
    depth: 6, bevelEnabled: true, bevelThickness: 1.1, bevelSize: 0.7, bevelSegments: 2,
  });
  geo.scale(1, -1, 1);            // SVG y-axis points down — flip it
  geo.computeBoundingBox();
  const size = geo.boundingBox.getSize(new THREE.Vector3());
  const s = 1.55 / Math.max(size.x, size.y, 0.001);
  geo.scale(s, s, s);
  geo.center();

  let hex = "#" + icon.hex;
  if (lum(hex) < 0.18) hex = "#ECEEF3";   // very dark marks → light, so they read on the black space bg
  const mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(hex), metalness: 0.38, roughness: 0.36, transparent: true });
  return { mesh: new THREE.Mesh(geo, mat), mats: [mat] };
}
