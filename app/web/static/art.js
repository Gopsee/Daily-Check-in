"use strict";
/* Icons, mood faces and flat illustrations, all drawn as inline SVG (no image files). */

// Single breezy-blue tone; the CSS tokens in styles.css use the same values.
const PALETTE = {
  accent: "#2b7de9",
  inkSoft: "#5a7290",
  heroMid: "#3d8dec", // window bars blend into the header gradient
  heroSoft: "#cfe6ff",
  heroDeep: "#1f66c9",
  shirt: "#ffffff",
  pants: "#174a8f",
  book: "#a9d1fb",
  leaf: "#bfe0ff",
  stem: "#e6f2ff",
  pot: "#ffffff",
  pot2: "#a9d1fb",
  heart: "#ffffff",
  cloud: "#ffffff",
};

const ICONS = {
  lotus: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20c-4.2 0-8-2.4-9.2-6.2 2.9-.1 5.4.9 7 2.6-.9-3.5-.3-7.4 2.2-11.2 2.5 3.8 3.1 7.7 2.2 11.2 1.6-1.7 4.1-2.7 7-2.6C20 17.6 16.2 20 12 20z"/></svg>',
  chart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 18.5l5.5-6 4 3.5 7-8.5 1.5 1.3-8.3 10-4-3.5-4.2 4.6z"/></svg>',
  heart: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.3-9.6C1.4 7.6 4 4 7.5 4c1.9 0 3.5 1 4.5 2.5C13 5 14.6 4 16.5 4 20 4 22.6 7.6 21.3 11.4 19.5 16.4 12 21 12 21z"/></svg>',
  call: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z"/></svg>',
  sms: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 4h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H8l-4 4V5a1 1 0 0 1 1-1z"/></svg>',
  mic: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11z"/></svg>',
  open: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 3h7v7h-2V6.4l-8.3 8.3-1.4-1.4L17.6 5H14zM5 5h6v2H5v12h12v-6h2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/></svg>',
};

const MOUTHS = {
  1: "M-4.5 5.5Q0 1 4.5 5.5",
  2: "M-4 5Q0 2.8 4 5",
  3: "M-4 4.2H4",
  4: "M-4.2 3Q0 6.5 4.2 3",
  5: "M-5 2.2Q0 9 5 2.2Z",
};

/** A simple face for mood 1-5, drawn in the surrounding text colour. */
function face(mood) {
  const c = "currentColor";
  return `<svg viewBox="-12 -12 24 24" aria-hidden="true"><circle r="10" fill="none" stroke="${c}" stroke-width="1.8"/>`
    + `<circle cx="-3.6" cy="-2.5" r="1.4" fill="${c}"/><circle cx="3.6" cy="-2.5" r="1.4" fill="${c}"/>`
    + `<path d="${MOUTHS[mood]}" fill="${mood === 5 ? c : "none"}" stroke="${c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

/* ---------- illustrations ---------- */

const SKIN = "#f3c7a8", HAIR = "#4a3226", CHEEK = "#f29b9b";
const ART_W = 400, ART_H = 170;

function leaf(x, y, dir, p, s = 0.9) {
  const d = dir * s;
  return `<path d="M${x} ${y}Q${x + 12 * d} ${y - 16 * s} ${x + 28 * d} ${y - 10 * s}Q${x + 14 * d} ${y + 4 * s} ${x} ${y}Z" fill="${p.leaf}"/>`;
}

function plant(x, ground, height, pot, p) {
  let out = `<line x1="${x}" y1="${ground - 22}" x2="${x}" y2="${ground - 22 - height}" stroke="${p.stem}" stroke-width="3" stroke-linecap="round"/>`;
  for (let y = ground - 40, i = 0; y > ground - 22 - height; y -= 18, i++) out += leaf(x, y, i % 2 ? 1 : -1, p);
  return out + `<path d="M${x - 16} ${ground - 24}H${x + 16}L${x + 11} ${ground}H${x - 11}Z" fill="${pot}"/>`;
}

function heart(x, y, r, color) {
  return `<circle cx="${x - r * 0.5}" cy="${y}" r="${r * 0.55}" fill="${color}"/><circle cx="${x + r * 0.5}" cy="${y}" r="${r * 0.55}" fill="${color}"/>`
    + `<path d="M${x - r * 1.02} ${y + r * 0.15}L${x} ${y + r * 1.15}L${x + r * 1.02} ${y + r * 0.15}Z" fill="${color}"/>`;
}

function cloud(x, y, s, p) {
  return `<g fill="${p.cloud}" opacity=".9"><ellipse cx="${x}" cy="${y}" rx="${26 * s}" ry="${11 * s}"/>`
    + `<circle cx="${x - 9 * s}" cy="${y - 7 * s}" r="${10 * s}"/><circle cx="${x + 7 * s}" cy="${y - 10 * s}" r="${13 * s}"/></g>`;
}

/** A person sitting cross-legged, drawn around (0, 0) = the middle of the floor. pose: meditate | rest | read | call. */
function person(pose, p) {
  const arm = `fill="none" stroke="${SKIN}" stroke-width="12" stroke-linecap="round"`;
  let g = `<ellipse cx="0" cy="-23" rx="76" ry="23" fill="${p.pants}"/>`
    + `<ellipse cx="-62" cy="-18.5" rx="9" ry="5.5" fill="${SKIN}"/><ellipse cx="62" cy="-18.5" rx="9" ry="5.5" fill="${SKIN}"/>`
    + `<circle cx="0" cy="-142" r="26" fill="${HAIR}"/><circle cx="3" cy="-171" r="11" fill="${HAIR}"/>`
    + `<rect x="-7" y="-128" width="14" height="18" fill="${SKIN}"/>`
    + `<rect x="-31" y="-114" width="62" height="84" rx="28" fill="${p.shirt}"/>`
    + `<ellipse cx="0" cy="-138" rx="20" ry="22" fill="${SKIN}"/>`
    + `<path d="M-22 -146Q-4 -170 22 -150V-160Q0 -176 -22 -158Z" fill="${HAIR}"/>`;
  for (const side of [-1, 1]) {
    g += pose === "meditate"
      ? `<path d="M${side * 8 - 4} -139A4 3 0 0 0 ${side * 8 + 4} -139" fill="none" stroke="${HAIR}" stroke-width="1.6" stroke-linecap="round"/>`
      : `<circle cx="${side * 8}" cy="-138" r="2.3" fill="${HAIR}"/>`;
    g += `<circle cx="${side * 12}" cy="-129" r="4" fill="${CHEEK}" opacity=".45"/>`;
  }
  g += `<path d="M-4 -125.5Q0 -121.5 4 -125.5" fill="none" stroke="#b5584f" stroke-width="1.6" stroke-linecap="round"/>`;

  if (pose === "meditate" || pose === "rest") {
    for (const side of [-1, 1]) {
      g += `<path d="M${side * 24} -104Q${side * 62} -86 ${side * 56} -46" ${arm}/><circle cx="${side * 56}" cy="-44" r="7" fill="${SKIN}"/>`;
    }
  } else if (pose === "read") {
    for (const side of [-1, 1]) g += `<path d="M${side * 24} -104Q${side * 40} -70 ${side * 26} -66" ${arm}/>`;
    g += `<rect x="-32" y="-92" width="64" height="42" rx="4" fill="${p.book}"/><line x1="0" y1="-92" x2="0" y2="-50" stroke="${p.accent}" stroke-width="2"/>`;
    for (const side of [-1, 1]) g += `<circle cx="${side * 30}" cy="-68" r="7" fill="${SKIN}"/>`;
  } else {
    g += `<path d="M-24 -104Q-46 -70 -22 -56" ${arm}/><circle cx="-20" cy="-56" r="7" fill="${SKIN}"/>`;
    g += `<path d="M24 -104Q52 -96 26 -138" ${arm}/>`;
    g += `<rect x="19" y="-158" width="13" height="24" rx="3" fill="#183a63"/><circle cx="26" cy="-138" r="7" fill="${SKIN}"/>`;
  }
  return g;
}

function speechBubble(x, y, w, p) {
  const h = w * 0.62, dots = [0.3, 0.5, 0.7].map((f) => `<circle cx="${x + w * f}" cy="${y + h / 2}" r="${w * 0.06}" fill="${p.accent}"/>`).join("");
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${h / 2}" fill="#fff"/><path d="M${x + w * 0.2} ${y + h - 2}l-6 12 16-10z" fill="#fff"/>${dots}`;
}

/** kind: checkin | talk | history | support */
function scene(kind, p = PALETTE) {
  const W = ART_W, H = ART_H, ground = H - 16, s = 0.8, cx = W * 0.46;
  let bg = "";
  if (kind === "checkin") {
    const wx = W * 0.55, ww = W * 0.36, wh = H * 0.62;
    bg += `<rect x="${wx}" y="8" width="${ww}" height="${wh}" rx="10" fill="${p.heroSoft}" opacity=".55"/>`;
    bg += `<line x1="${wx + ww / 2}" y1="8" x2="${wx + ww / 2}" y2="${8 + wh}" stroke="${p.heroMid}" stroke-width="5"/>`;
    for (const i of [1, 2]) bg += `<line x1="${wx}" y1="${8 + (wh * i) / 3}" x2="${wx + ww}" y2="${8 + (wh * i) / 3}" stroke="${p.heroMid}" stroke-width="5"/>`;
    bg += cloud(W * 0.68, 46, 0.9, p);
    bg += plant(W * 0.14, ground, 70, p.pot, p);
    bg += cloud(W * 0.2, 30, 0.7, p);
  } else if (kind === "talk") {
    bg += cloud(W * 0.16, 40, 0.8, p) + cloud(W * 0.86, 30, 0.6, p);
    bg += speechBubble(W * 0.6, 24, 70, p);
    bg += `<g opacity=".85">${speechBubble(W * 0.2, 70, 46, p)}</g>`;
    // Sound waves from the person's mouth (the head sits about 108 px above the floor at this scale).
    const mx = cx + 22, my = ground - 104;
    for (const [r, o] of [[10, 0.7], [18, 0.45], [26, 0.25]]) {
      bg += `<path d="M${mx + r * 0.5} ${my - r}A${r} ${r} 0 0 1 ${mx + r * 0.5} ${my + r}" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity="${o}"/>`;
    }
  } else if (kind === "history") {
    bg += `<circle cx="${W * 0.8}" cy="40" r="24" fill="${p.heroSoft}" opacity=".7"/>`;
    bg += cloud(W * 0.62, 34, 0.8, p) + cloud(W * 0.18, 52, 0.6, p);
    bg += `<ellipse cx="${W * 0.2}" cy="${ground + 5}" rx="${W * 0.4}" ry="75" fill="${p.heroSoft}" opacity=".35"/>`;
    bg += `<ellipse cx="${W * 0.8}" cy="${ground + 25}" rx="${W * 0.45}" ry="75" fill="${p.heroSoft}" opacity=".25"/>`;
    for (const [dx, dy, r] of [[0, 0, 22], [22, 6, 18], [-20, 8, 16], [8, -18, 16]]) {
      bg += `<circle cx="${W * 0.85 + dx}" cy="${ground - 40 + dy}" r="${r}" fill="${p.leaf}" opacity=".8"/>`;
    }
    bg += `<rect x="${W * 0.12 - 4}" y="${ground - 70}" width="8" height="60" fill="${p.stem}"/><circle cx="${W * 0.12}" cy="${ground - 84}" r="26" fill="${p.leaf}"/>`;
  } else {
    bg += `<circle cx="${W * 0.16}" cy="44" r="24" fill="${p.heroSoft}" opacity=".7"/>`;
    bg += cloud(W * 0.36, 30, 0.7, p);
    [[0.74, 96], [0.84, 120], [0.93, 80]].forEach(([x, h], i) => { bg += plant(W * x, ground, h, i % 2 ? p.pot2 : p.pot, p); });
    bg += heart(cx + 62 * s, 34, 12, p.heart);
  }
  bg += `<rect x="0" y="${ground - 4}" width="${W}" height="${H - ground + 4}" fill="${p.heroDeep}" opacity=".35"/>`;
  const pose = { checkin: "meditate", talk: "rest", history: "read", support: "call" }[kind];
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMax meet" role="img" aria-label="Illustration">${bg}`
    + `<g transform="translate(${cx} ${ground}) scale(${s})">${person(pose, p)}</g></svg>`;
}
