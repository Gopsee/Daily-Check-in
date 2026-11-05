"use strict";

const BOOT = window.BOOT;
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const MOOD_LABEL = { 1: "Very low", 2: "Low", 3: "Okay", 4: "Good", 5: "Great" };
const LEVEL_LABEL = { low: "Low risk", elevated: "Elevated", high: "High", imminent: "Imminent" };
const LEVEL_COLOR = { low: "#3f9d74", elevated: "#d79a23", high: "#d0643a", imminent: "#c23b3b" };
const PHQ_OPTIONS = ["Not at all", "Several days", "Over half the days", "Nearly every day"];
const REGIONS = { IN: "India", US: "US", GB: "UK", AU: "Australia", DEFAULT: "Other" };
const CRISIS_LOCK_S = 5;

const storage = {
  get(key, fallback) { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* private mode */ } },
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const titleCase = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const state = {
  tab: "checkin",
  mood: null,
  tags: new Set(),
  sleep: 7,
  sleepSkipped: false,
  phq: { interest: null, down: null, item9: null },
  region: (() => { const r = storage.get("region", BOOT.region); return r in REGIONS ? r : "DEFAULT"; })(),
  days: 30,
  profile: BOOT.profile?.profile ?? {},
  body: BOOT.profile?.body ?? null,
  sleepFromHealth: false,
  memories: BOOT.profile?.memories ?? [],
};

/* ---------- shell: tabs, palettes, art ---------- */
function showTab(tab) {
  // Leaving the Talk screen ends the conversation, so the mic is never live in the background.
  if (state.tab === "talk" && tab !== "talk" && talk.ws) endTalk(true);
  state.tab = tab;
  const navTab = tab === "talk" ? "checkin" : tab; // Talk opens from the check-in tab's mic button
  $$(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === navTab));
  $$(".screen").forEach((s) => s.classList.toggle("active", s.id === `screen-${tab}`));
  $("#scroll").scrollTop = 0;
  if (tab === "history") loadHistory();
  if (tab === "support") loadProfile(); // an agent may have remembered something new
}
$$(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));

function drawArt() {
  $$("[data-art]").forEach((el) => { el.innerHTML = scene(el.dataset.art); });
  $$("[data-icon]").forEach((el) => { el.innerHTML = ICONS[el.dataset.icon]; });
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 1800);
}

function pillHTML(label, on, attrs = "", disabled = false) {
  return `<button type="button" class="pill${on ? " on" : ""}" aria-pressed="${on}" ${attrs}${disabled ? " disabled" : ""}>${esc(label)}</button>`;
}

/* ---------- hotlines (pure data, works offline) ---------- */
function hotlinesFor(region) {
  return BOOT.hotlines[region] || BOOT.hotlines.DEFAULT;
}

function smsHref(sms) {
  const m = /text\s+(\w+)\s+to\s+([\d\s]+)/i.exec(sms);
  if (m) return `sms:${m[2].replace(/\s/g, "")}?&body=${encodeURIComponent(m[1])}`;
  return `sms:${sms.replace(/[^\d+]/g, "")}`;
}

/** Rendered only from bundled hotlines.json, never from model output. */
function hotlineHTML(lines) {
  return lines.map((l) => {
    const acts = [];
    if (l.phone) acts.push(`<a class="act" href="tel:${l.phone.replace(/[^\d+]/g, "")}">${ICONS.call}Call ${esc(l.phone)}</a>`);
    if (l.alt_phone) acts.push(`<a class="act alt" href="tel:${l.alt_phone.replace(/[^\d+]/g, "")}">${ICONS.call}${esc(l.alt_phone)}</a>`);
    if (l.sms) acts.push(`<a class="act alt" href="${smsHref(l.sms)}">${ICONS.sms}${/^[\d\s+]+$/.test(l.sms) ? "Text " + esc(l.sms) : esc(l.sms)}</a>`);
    if (l.url) acts.push(`<a class="act" href="${esc(l.url)}" target="_blank" rel="noopener">${ICONS.open}Find a helpline</a>`);
    return `<div class="line"><p class="name">${esc(l.name)}</p><div class="acts">${acts.join("")}</div></div>`;
  }).join("");
}

/** The person's own emergency contact, from their profile. Never sent to a model. */
function contactHTML() {
  const c = state.profile.emergency_contact;
  if (!c?.phone) return "";
  const digits = c.phone.replace(/[^\d+]/g, "");
  return `<div class="line"><p class="name">${esc(c.name)} · your emergency contact</p><div class="acts"><a class="act" href="tel:${digits}">${ICONS.call}Call ${esc(c.name)}</a><a class="act alt" href="sms:${digits}">${ICONS.sms}Text</a></div></div>`;
}

/* ---------- crisis screen ---------- */
let crisisTimer = null;
function openCrisis(reasons = [], lines = hotlinesFor(state.region)) {
  const el = $("#crisis");
  $("#crisis-hotlines").innerHTML = hotlineHTML(lines);
  $("#crisis-contact").innerHTML = contactHTML();
  $("#crisis-contact").hidden = !contactHTML();
  $("#crisis-why").hidden = reasons.length === 0;
  $("#crisis-why ul").innerHTML = reasons.map((r) => `<li>${esc(r)}</li>`).join("");

  // A short pause before it can be dismissed, so the numbers are seen.
  const close = $("#crisis-close");
  clearInterval(crisisTimer);
  let left = reasons.length ? CRISIS_LOCK_S : 0;
  const label = () => { close.textContent = left > 0 ? `I'm safe for now (${left})` : "I'm safe for now"; close.disabled = left > 0; };
  label();
  if (left > 0) crisisTimer = setInterval(() => { left -= 1; label(); if (left <= 0) clearInterval(crisisTimer); }, 1000);

  el.hidden = false;
  el.scrollTop = 0;
  $(".act", el)?.focus();
}
$("#crisis-close").addEventListener("click", () => { $("#crisis").hidden = true; });
$$('[data-action="sos"]').forEach((b) => b.addEventListener("click", () => openCrisis()));

/* ---------- check-in form ---------- */
function renderGreeting() {
  const now = new Date();
  const h = now.getHours();
  const hello = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  $("#greeting").textContent = state.profile.preferred_name ? `${hello}, ${state.profile.preferred_name}` : hello;
  $("#today-label").textContent = now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
}

$("#moods").addEventListener("click", (e) => {
  const b = e.target.closest(".mood");
  if (!b) return;
  state.mood = Number(b.dataset.mood);
  if (state.mood > 2) state.phq = { interest: null, down: null, item9: null };
  syncForm();
});
$("#tags").addEventListener("click", (e) => {
  const b = e.target.closest("[data-tag]");
  if (!b || b.disabled) return;
  const t = b.dataset.tag;
  state.tags.has(t) ? state.tags.delete(t) : state.tags.add(t);
  syncForm();
});
$("#sleep-minus").addEventListener("click", () => { state.sleep = Math.max(0, state.sleep - 0.5); state.sleepSkipped = false; state.sleepFromHealth = false; syncForm(); });
$("#sleep-plus").addEventListener("click", () => { state.sleep = Math.min(24, state.sleep + 0.5); state.sleepSkipped = false; state.sleepFromHealth = false; syncForm(); });
$("#sleep-skip").addEventListener("click", () => { state.sleepSkipped = !state.sleepSkipped; syncForm(); });
$("#phq").addEventListener("click", (e) => {
  const b = e.target.closest("[data-v]");
  if (!b) return;
  const key = b.closest(".phq-q").dataset.q;
  const v = Number(b.dataset.v);
  state.phq[key] = state.phq[key] === v ? null : v;
  syncForm();
});

function phq2Score() {
  const { interest, down } = state.phq;
  return interest == null || down == null ? null : interest + down;
}

function syncForm() {
  $("#moods").innerHTML = [1, 2, 3, 4, 5].map((m) => {
    const on = m === state.mood;
    return `<button type="button" class="mood" role="radio" aria-checked="${on}" data-mood="${m}"><span class="face">${face(m)}</span>${MOOD_LABEL[m]}</button>`;
  }).join("");

  const full = state.tags.size >= 3;
  $("#tags").innerHTML = BOOT.tags.map((t) => pillHTML(titleCase(t), state.tags.has(t), `data-tag="${esc(t)}"`, full && !state.tags.has(t))).join("");
  $("#tag-count").textContent = state.tags.size ? `${state.tags.size} of 3` : "Pick up to 3";

  $("#sleep-value").textContent = `${state.sleep} h`;
  $("#sleep-source").hidden = !state.sleepFromHealth || state.sleepSkipped;
  $(".stepper").classList.toggle("off", state.sleepSkipped);
  $("#sleep-skip").classList.toggle("on", state.sleepSkipped);
  $("#sleep-skip").setAttribute("aria-pressed", String(state.sleepSkipped));

  $("#details").classList.toggle("off", state.mood == null);

  const needsPhq = state.mood != null && state.mood <= 2;
  const score = phq2Score();
  const askItem9 = score != null && score >= 3;
  if (!askItem9) state.phq.item9 = null;
  $$(".phq-q").forEach((q) => {
    const key = q.dataset.q;
    $(".pills", q).innerHTML = PHQ_OPTIONS.map((label, i) => pillHTML(label, state.phq[key] === i, `role="radio" data-v="${i}"`)).join("");
  });
  $("#phq").hidden = !needsPhq;
  $('.phq-q[data-q="item9"]').hidden = !askItem9;

  const phqDone = !needsPhq || (score != null && (!askItem9 || state.phq.item9 != null));
  $("#submit-btn").disabled = state.mood == null || !phqDone;
}

function payload() {
  const score = state.mood <= 2 ? phq2Score() : null;
  return {
    mood: state.mood,
    tags: [...state.tags],
    sleep_hours: state.sleepSkipped ? null : state.sleep,
    note: $("#note").value.trim() || null,
    phq2_score: score,
    phq9_item9: score != null && score >= 3 ? state.phq.item9 : null,
  };
}

async function postJSON(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

$("#checkin-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if ($("#submit-btn").disabled) return;
  const body = payload();
  $("#checkin-form").hidden = true;
  $("#thinking").hidden = false;

  // The rules take milliseconds. If they already say high or imminent, show help
  // before the agent finishes; the reflection loads behind the crisis screen.
  let crisisShown = false;
  postJSON("/api/checkins/precheck", body).then((pre) => {
    if (pre.show_crisis && !crisisShown) { crisisShown = true; openCrisis(pre.reasons); }
  }).catch(() => {});

  try {
    const result = await postJSON(`/api/checkins?region=${encodeURIComponent(state.region)}`, body);
    if (result.show_crisis && !crisisShown) { crisisShown = true; openCrisis(result.reasons, result.hotlines); }
    renderResult(result, body);
  } catch {
    renderOffline(body);
  } finally {
    $("#thinking").hidden = true;
  }
});

function renderResult(r, body) {
  const why = r.findings.filter((f) => f.level !== "low");
  const parts = [];
  if (r.show_crisis) {
    parts.push(`<div class="alert"><span>Support is one tap away</span><button type="button" id="reopen-crisis">Show lines</button></div>`);
  }
  parts.push(`<div class="mood-head"><span class="face">${face(body.mood)}</span><div><span class="soft small">Today</span><b>${MOOD_LABEL[body.mood]}</b></div><span class="badge lv-${r.risk}">${LEVEL_LABEL[r.risk]}</span></div>`);
  if (r.coping) {
    parts.push(`<div class="card"><p class="label">Try this first</p><h3>${esc(r.coping.title)}</h3><ul class="steps">${r.coping.steps.map((s) => `<li tabindex="0">${esc(s)}</li>`).join("")}</ul></div>`);
  }
  parts.push(`<div class="card stack tight"><p class="reflection">${esc(r.reflection)}</p>${r.ai_available ? "" : '<p class="soft small">Our AI couldn\'t respond just now, so this is a standard message.</p>'}</div>`);
  if (r.risk === "elevated") {
    parts.push(`<h2>Would talking to someone help?</h2><p class="soft">These lines are free and confidential.</p><div class="stack">${hotlineHTML(r.hotlines)}</div>`);
  }
  if (why.length) {
    parts.push(`<details class="card"><summary>Why am I seeing this?</summary><div class="inner"><ul class="why">${why.map((f) => `<li><i style="background:${LEVEL_COLOR[f.level]}"></i><span>${esc(f.reason)}<small>${esc(f.source.toUpperCase())}</small></span></li>`).join("")}</ul></div></details>`);
  }
  parts.push(`<button type="button" class="outline" id="new-checkin">Done</button>`);

  const el = $("#result");
  el.innerHTML = parts.join("");
  el.hidden = false;
  $("#reopen-crisis")?.addEventListener("click", () => openCrisis(r.reasons, r.hotlines));
  $$(".steps li", el).forEach((li) => {
    const toggle = () => li.classList.toggle("done");
    li.addEventListener("click", toggle);
    li.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  });
  $("#new-checkin").addEventListener("click", resetForm);
}

function renderOffline(body) {
  // No server: still never leave someone without numbers on a low day.
  const low = body.mood <= 2 || body.note;
  const el = $("#result");
  el.innerHTML = `<div class="card stack tight"><h3>We couldn't reach the server</h3><p class="soft">Your check-in wasn't saved. Please try again in a moment.</p></div>`
    + (low ? `<h2>If you need to talk to someone now</h2><div class="stack">${hotlineHTML(hotlinesFor(state.region))}</div>` : "")
    + `<button type="button" class="outline" id="new-checkin">Back</button>`;
  el.hidden = false;
  $("#new-checkin").addEventListener("click", () => { el.hidden = true; $("#checkin-form").hidden = false; });
}

/** Last night's sleep from Apple Health, rounded to the stepper's half hours. */
function healthSleep() {
  const h = state.body?.last_night_sleep;
  return h == null ? null : Math.round(h * 2) / 2;
}

function resetForm() {
  state.mood = null;
  state.tags.clear();
  state.sleep = healthSleep() ?? 7;
  state.sleepFromHealth = healthSleep() != null;
  state.sleepSkipped = false;
  state.phq = { interest: null, down: null, item9: null };
  $("#note").value = "";
  $("#result").hidden = true;
  $("#checkin-form").hidden = false;
  $("#scroll").scrollTop = 0;
  syncForm();
}

/* ---------- talk: voice chat with Nova Sonic ---------- */
// Mic audio goes up the WebSocket as 16 kHz PCM; the voice comes back as PCM and is queued for playback.
// Each line the person says is risk-checked on the server, which can open the crisis screen.
const talk = {
  ws: null, connecting: false, muted: false, speaking: false,
  stream: null, micCtx: null, micNode: null, silenceTimer: null,
  playCtx: null, nextTime: 0, sources: [], outputRate: 24000,
  bubbles: new Map(), lines: [], typed: 0,
};

function refreshTalk(status) {
  const live = Boolean(talk.ws);
  const state = !live ? "idle" : talk.connecting ? "connecting" : talk.speaking ? "speaking" : talk.muted ? "muted" : "listening";
  const orb = $("#talk-orb");
  orb.dataset.state = state;
  orb.setAttribute("aria-label", !live ? "Start talking" : talk.muted ? "Unmute microphone" : "Mute microphone");
  $("#talk-status").textContent = status ?? {
    idle: talk.lines.length ? "Conversation ended. Tap to talk again." : "Tap to start talking",
    connecting: "Connecting…",
    speaking: "Speaking…",
    muted: "Mic muted. Tap to unmute.",
    listening: "Listening…",
  }[state];
  $("#talk-controls").hidden = !live;
  $("#talk-type").hidden = !live;
  $("#talk-hint").hidden = live;
  $("#talk-mute").textContent = talk.muted ? "Unmute mic" : "Mute mic";
  $("#talk-mute").setAttribute("aria-pressed", String(talk.muted));
  $("#talk-to-checkin").hidden = talk.lines.length === 0;
}

function sendAudio(buffer) {
  if (talk.ws?.readyState === WebSocket.OPEN) talk.ws.send(buffer);
}

async function startMic() {
  talk.stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
  });
  talk.micCtx = new AudioContext();
  await talk.micCtx.audioWorklet.addModule("/static/mic-worklet.js");
  talk.micNode = new AudioWorkletNode(talk.micCtx, "mic-capture", { processorOptions: { targetRate: 16000 } });
  talk.micNode.port.onmessage = (e) => {
    sendAudio(e.data.pcm);
    $("#talk-orb").style.setProperty("--level", Math.min(1, e.data.level * 3).toFixed(2));
  };
  const sink = talk.micCtx.createGain();
  sink.gain.value = 0; // keeps the graph running without playing the mic back
  talk.micCtx.createMediaStreamSource(talk.stream).connect(talk.micNode).connect(sink).connect(talk.micCtx.destination);
}

function stopMic() {
  talk.stream?.getTracks().forEach((t) => t.stop());
  talk.micCtx?.close().catch(() => {});
  clearInterval(talk.silenceTimer);
  Object.assign(talk, { stream: null, micCtx: null, micNode: null, silenceTimer: null });
}

async function startTalk() {
  if (talk.ws) return;
  talk.lines = [];
  talk.bubbles.clear();
  $("#talk-log").innerHTML = "";
  $("#talk-support").hidden = true;
  talk.muted = false;
  talk.connecting = true;
  talk.playCtx = new AudioContext(); // created inside the tap, so the browser allows playback
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/talk`);
  ws.binaryType = "arraybuffer";
  // Attach handlers before the mic setup awaits, or the server's first messages would be missed.
  ws.onmessage = (e) => (typeof e.data === "string" ? onTalkMessage(JSON.parse(e.data)) : playVoice(e.data));
  ws.onclose = () => { if (talk.ws === ws) endTalk(false); };
  talk.ws = ws;
  refreshTalk();

  try {
    await startMic();
  } catch {
    // No microphone (denied or missing): keep the audio stream open with silence so typing still works.
    talk.silenceTimer = setInterval(() => sendAudio(new ArrayBuffer(3200)), 100);
    toast("Microphone is off. You can type instead.");
  }
  if (talk.ws !== ws) stopMic(); // the conversation ended while the mic was starting
}

function endTalk(tellServer = true) {
  const ws = talk.ws;
  talk.ws = null;
  if (ws && tellServer && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "end" }));
    ws.close();
  }
  stopMic();
  stopVoice();
  talk.playCtx?.close().catch(() => {});
  Object.assign(talk, { playCtx: null, connecting: false, speaking: false });
  $("#talk-orb").style.setProperty("--level", 0);
  refreshTalk();
}

function setMuted(muted) {
  talk.muted = muted;
  talk.micNode?.port.postMessage({ muted });
  refreshTalk();
}

function onTalkMessage(m) {
  switch (m.type) {
    case "ready":
      talk.outputRate = m.output_rate;
      talk.connecting = false;
      refreshTalk();
      break;
    case "caption": {
      const b = talk.bubbles.get(m.id);
      showBubble(m.id, m.role, (b?.text ?? "") + m.text, false);
      break;
    }
    case "line":
      showBubble(m.id, m.role, m.text, true);
      if (m.role === "user" && m.text) { talk.lines.push(m.text); refreshTalk(); }
      break;
    case "barge_in":
      stopVoice(); // the person started talking, so stop the reply mid-sentence
      break;
    case "risk":
      if (m.show_crisis) openCrisis(m.reasons);
      else $("#talk-support").hidden = false;
      break;
    case "error":
      endTalk(false);
      refreshTalk(m.message);
      break;
  }
}

function showBubble(id, role, text, final) {
  let b = talk.bubbles.get(id);
  if (!b) {
    const li = document.createElement("li");
    li.className = `say ${role === "user" ? "me" : "them"}`;
    $("#talk-log").append(li);
    b = { li, text: "" };
    talk.bubbles.set(id, b);
  }
  b.text = text;
  b.li.textContent = text;
  b.li.classList.toggle("partial", !final);
  b.li.scrollIntoView({ block: "nearest" });
}

function playVoice(buffer) {
  if (!talk.playCtx) return;
  const pcm = new Int16Array(buffer, 0, buffer.byteLength >> 1);
  const samples = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) samples[i] = pcm[i] / 32768;
  const clip = talk.playCtx.createBuffer(1, samples.length, talk.outputRate);
  clip.copyToChannel(samples, 0);
  const node = talk.playCtx.createBufferSource();
  node.buffer = clip;
  node.connect(talk.playCtx.destination);
  const at = Math.max(talk.playCtx.currentTime + 0.04, talk.nextTime);
  node.start(at);
  talk.nextTime = at + clip.duration;
  talk.sources.push(node);
  node.onended = () => {
    talk.sources = talk.sources.filter((n) => n !== node);
    if (!talk.sources.length && talk.speaking) { talk.speaking = false; refreshTalk(); }
  };
  if (!talk.speaking) { talk.speaking = true; refreshTalk(); }
}

function stopVoice() {
  talk.sources.forEach((n) => { try { n.stop(); } catch { /* already stopped */ } });
  talk.sources = [];
  talk.nextTime = 0;
  if (talk.speaking) { talk.speaking = false; refreshTalk(); }
}

$("#talk-open").addEventListener("click", () => showTab("talk"));
$("#talk-back").addEventListener("click", () => showTab("checkin"));
$("#talk-orb").addEventListener("click", () => (talk.ws ? setMuted(!talk.muted) : startTalk()));
$("#talk-mute").addEventListener("click", () => setMuted(!talk.muted));
$("#talk-end").addEventListener("click", () => endTalk(true));
$("#talk-support-open").addEventListener("click", () => openCrisis());
$("#talk-type").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("#talk-input");
  const text = input.value.trim();
  if (!text || talk.ws?.readyState !== WebSocket.OPEN) return;
  talk.ws.send(JSON.stringify({ type: "text", text }));
  showBubble(`typed-${++talk.typed}`, "user", text, true);
  talk.lines.push(text);
  input.value = "";
  refreshTalk();
});
$("#talk-to-checkin").addEventListener("click", () => {
  if (talk.ws) endTalk(true);
  const note = $("#note");
  const said = talk.lines.join(" ");
  note.value = [note.value.trim(), said].filter(Boolean).join(" ").slice(0, 1000);
  showTab("checkin");
  toast("Your words are in today's note. Pick a mood to finish.");
});

/* ---------- history ---------- */
function renderRangePills() {
  $("#range-pills").innerHTML = [7, 14, 30].map((d) => pillHTML(`${d} days`, d === state.days, `data-days="${d}"`)).join("");
}
$("#range-pills").addEventListener("click", (e) => {
  const b = e.target.closest("[data-days]");
  if (!b) return;
  state.days = Number(b.dataset.days);
  loadHistory();
});

async function loadHistory() {
  renderRangePills();
  try {
    const data = await (await fetch(`/api/history?days=${state.days}`)).json();
    renderHistory(data.checkins);
  } catch {
    $("#chart").innerHTML = '<p class="empty">History needs a connection.</p>';
  }
}

function renderHistory(rows) {
  const avg = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  const mood = avg(rows.map((r) => r.mood));
  const sleep = avg(rows.filter((r) => r.sleep_hours != null).map((r) => r.sleep_hours));
  const low = rows.filter((r) => r.mood <= 2).length;
  $("#avg-label").textContent = mood == null ? "" : `${mood.toFixed(1)} average`;
  renderChart(rows);

  const bar = (label, value, fraction) => `<div class="bar"><div class="row-head"><span>${label}</span><span class="soft">${value}</span></div><div class="track"><i style="width:${Math.round(Math.max(0, Math.min(1, fraction)) * 100)}%"></i></div></div>`;
  $("#bars").innerHTML = [
    bar("Check-ins", `${rows.length}/${state.days} days`, rows.length / state.days),
    bar("Average mood", mood == null ? "–" : `${mood.toFixed(1)}/5`, (mood ?? 0) / 5),
    bar("Average sleep", sleep == null ? "–" : `${sleep.toFixed(1)}/8 h`, (sleep ?? 0) / 8),
    bar("Low days", `${low}/${rows.length}`, rows.length ? low / rows.length : 0),
  ].join("");

  const recent = rows.slice(-7).reverse();
  $("#days").innerHTML = recent.length
    ? recent.map((r) => `<li><span class="face">${face(r.mood)}</span><span class="d">${new Date(r.date + "T00:00:00").toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}<small>${esc(r.tags.map(titleCase).join(", ") || MOOD_LABEL[r.mood])}</small></span>${r.risk && r.risk !== "low" ? `<span class="badge lv-${r.risk}">${LEVEL_LABEL[r.risk]}</span>` : ""}</li>`).join("")
    : '<li class="empty">Nothing yet.</li>';
}

function renderChart(rows) {
  if (!rows.length) { $("#chart").innerHTML = '<p class="empty">No check-ins yet. Your chart starts with today.</p>'; return; }
  const W = 360, H = 160, L = 18, R = 8, T = 10, B = 20;
  const { accent, inkSoft: soft } = PALETTE;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const start = new Date(today); start.setDate(start.getDate() - state.days);
  const x = (d) => L + ((new Date(d + "T00:00:00") - start) / (today - start)) * (W - L - R);
  const y = (m) => T + ((5 - m) / 4) * (H - T - B);

  const grid = [1, 2, 3, 4, 5].map((m) => `<line x1="${L}" x2="${W - R}" y1="${y(m)}" y2="${y(m)}" stroke="${soft}" stroke-opacity=".18"/><text x="${L - 8}" y="${y(m) + 3.5}" text-anchor="end" font-size="10" fill="${soft}">${m}</text>`).join("");
  const pts = rows.map((r) => [x(r.date), y(r.mood), r]);
  const line = pts.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`).join("");
  const area = `${line}L${pts.at(-1)[0].toFixed(1)},${y(1)}L${pts[0][0].toFixed(1)},${y(1)}Z`;
  const dots = pts.map(([px, py, r]) => `<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="4.5" fill="#fff" stroke="${LEVEL_COLOR[r.risk] || accent}" stroke-width="2.5"><title>${r.date}: ${MOOD_LABEL[r.mood]}${r.risk ? " · " + LEVEL_LABEL[r.risk] : ""}</title></circle>`).join("");
  const fmt = (d) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  const ticks = `<text x="${L}" y="${H - 3}" font-size="10" fill="${soft}">${fmt(start)}</text><text x="${W - R}" y="${H - 3}" text-anchor="end" font-size="10" fill="${soft}">Today</text>`;
  // Shade the predicted week before each period, if they track their cycle.
  const xd = (d) => L + ((d - start) / (today - start)) * (W - L - R);
  const clampX = (v) => Math.max(L, Math.min(W - R, v));
  const starts = periodStarts(state.profile.cycle, start, today);
  const bands = starts.map((s) => {
    const x0 = clampX(xd(addDays(s, -PREMENSTRUAL_DAYS))), x1 = clampX(xd(s));
    return x1 > x0 ? `<rect x="${x0.toFixed(1)}" y="${T}" width="${(x1 - x0).toFixed(1)}" height="${H - T - B}" fill="#e46a8f" fill-opacity=".12"><title>Week before a predicted period</title></rect>` : "";
  }).join("");
  renderCycleNote(rows, starts);
  $("#chart").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Mood over the last ${state.days} days">${bands}${grid}<path d="${area}" fill="${accent}" fill-opacity=".12"/><path d="${line}" fill="none" stroke="${accent}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>${dots}${ticks}</svg>`;
}

function renderCycleNote(rows, starts) {
  const note = $("#cycle-note");
  const inWindow = (iso) => starts.some((s) => { const d = daysBetween(day0(iso), s); return d >= 1 && d <= PREMENSTRUAL_DAYS; });
  const low = rows.filter((r) => r.mood <= 2);
  note.hidden = !starts.length;
  if (!starts.length) return;
  const before = low.filter((r) => inWindow(r.date)).length;
  note.textContent = low.length
    ? `Shaded: the week before each predicted period. ${before} of your ${low.length} low days fell in those weeks.`
    : "Shaded: the week before each predicted period.";
}

/* ---------- support ---------- */
function renderSupport() {
  $("#region-pills").innerHTML = Object.entries(REGIONS).map(([code, label]) => pillHTML(label, code === state.region, `data-region="${code}"`)).join("");
  $("#support-hotlines").innerHTML = contactHTML() + hotlineHTML(hotlinesFor(state.region));
}
$("#region-pills").addEventListener("click", (e) => {
  const b = e.target.closest("[data-region]");
  if (!b) return;
  state.region = b.dataset.region;
  storage.set("region", state.region);
  renderSupport();
});

function renderExercises() {
  $("#exercises").innerHTML = BOOT.coping.map((x) => `<details class="card"><summary>${esc(x.title)}</summary><div class="inner"><ol class="ex">${x.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol></div></details>`).join("");
}

/* ---------- period cycle (same rules as app/cycle.py) ---------- */
const PREMENSTRUAL_DAYS = 7, STALE_CYCLES = 3;
const day0 = (iso) => new Date(iso + "T00:00:00");
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const isoDate = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const daysBetween = (a, b) => Math.round((b - a) / 86400000);

function cycleStatus(c, today = new Date()) {
  if (!c?.tracking || !c.last_start) return null;
  const t = day0(isoDate(today)), since = daysBetween(day0(c.last_start), t);
  if (since < 0 || since > STALE_CYCLES * c.length) return null;
  const cycleDay = (since % c.length) + 1, untilNext = c.length - (since % c.length);
  const phase = cycleDay <= c.period_length ? "period" : untilNext <= PREMENSTRUAL_DAYS ? "premenstrual" : "other";
  return { phase, cycleDay, untilNext, next: addDays(t, untilNext) };
}

/** Predicted period starts covering [from, to], stepping both ways from the last known start. */
function periodStarts(c, from, to) {
  if (!c?.tracking || !c.last_start) return [];
  const last = day0(c.last_start), out = [];
  let s = new Date(last);
  while (s > from) s = addDays(s, -c.length);
  const stop = addDays(last, STALE_CYCLES * c.length);
  for (; s <= addDays(to, PREMENSTRUAL_DAYS) && s <= stop; s = addDays(s, c.length)) out.push(new Date(s));
  return out;
}

/* ---------- profile and memory ---------- */
const AGE_GROUPS = { teen: "13–17", young_adult: "18–25", adult: "26–59", older_adult: "60+", "": "Prefer not to say" };
const GENDERS = { male: "Male", female: "Female", other: "Other" };
const CONTEXTS = { new_baby: "New baby", shift_work: "Shift work", illness_or_injury: "Illness or injury", travel: "Travel" };
const splitList = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

function renderProfile() {
  const p = state.profile;
  $("#pf-name").value = p.preferred_name ?? "";
  $("#pf-age").innerHTML = Object.entries(AGE_GROUPS).map(([v, label]) => pillHTML(label, (p.age_group ?? "") === v, `data-age="${v}" role="radio"`)).join("");
  $("#pf-gender").innerHTML = Object.entries(GENDERS).map(([v, label]) => pillHTML(label, (p.gender ?? "") === v, `data-gender="${v}" role="radio"`)).join("");
  const c = p.cycle ?? {};
  $("#pf-cycle-on").checked = Boolean(c.tracking);
  $("#pf-cycle-start").value = c.last_start ?? "";
  $("#pf-cycle-start").max = isoDate(new Date());
  $("#pf-cycle-length").value = c.length ?? 28;
  $("#pf-cycle-period").value = c.period_length ?? 5;
  syncCycle();
  $("#pf-context").innerHTML = Object.entries(CONTEXTS).map(([v, label]) => pillHTML(label, (p.health_context ?? []).includes(v), `data-context="${v}"`)).join("");
  $("#pf-helps").value = (p.what_helps ?? []).join(", ");
  $("#pf-people").value = (p.trusted_people ?? []).join(", ");
  $("#pf-contact-name").value = p.emergency_contact?.name ?? "";
  $("#pf-contact-phone").value = p.emergency_contact?.phone ?? "";
  $("#memories").innerHTML = state.memories.length
    ? state.memories.map((m, i) => `<li><span>${esc(m.text)}<small>${new Date(m.saved + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" })}</small></span><button type="button" data-forget="${i}" aria-label="Forget this">×</button></li>`).join("")
    : '<li class="empty">Nothing yet. Lantern notes things you share, like who helps you.</li>';
}

function renderBody() {
  const b = state.body;
  $("#noticed").hidden = !b?.noticed?.length;
  $("#noticed-list").innerHTML = (b?.noticed ?? []).map((r) => `<li>${esc(r.replace(/ \(Apple Health\)$/, ""))}</li>`).join("");
  $("#body-card").hidden = !b?.available;
  if (!b?.available) return;
  const num = (r, v) => (r.key === "sleep_hours" ? v.toFixed(1) : Math.round(v).toLocaleString());
  const flagged = (r) => (r.key === "sleep_hours" || r.key === "steps") && b.noticed.some((n) => n.toLowerCase().includes(r.label.toLowerCase()));
  $("#body-rows").innerHTML = b.rows.map((r) => {
    const pct = r.usual ? Math.round(((r.this_week - r.usual) / r.usual) * 100) : 0;
    const chg = pct === 0 ? "same" : `${pct > 0 ? "↑" : "↓"} ${Math.abs(pct)}%`;
    return `<div class="body-row"><b>${esc(r.label)}</b><span class="chg${flagged(r) ? " flag" : ""}">${chg}</span><small>${num(r, r.this_week)} ${esc(r.unit)} this week · usual ${num(r, r.usual)}</small></div>`;
  }).join("");
  $("#body-expected").hidden = !b.expected.length;
  $("#body-expected").textContent = b.expected.length ? `Changes in sleep or activity are expected with ${b.expected.join(" and ")}, so Lantern doesn't treat them as warning signs.` : "";
}

function applyProfile(data) {
  state.profile = data.profile;
  state.memories = data.memories;
  if ("body" in data) { state.body = data.body; renderBody(); }
  renderProfile();
  renderGreeting();
  renderSupport();
}

async function loadProfile() {
  try { applyProfile(await (await fetch("/api/profile")).json()); } catch { renderProfile(); }
}

async function sendProfile(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Couldn't save");
  applyProfile(data);
}

const isMale = () => $("#pf-gender .on")?.dataset.gender === "male";

function formCycle() {
  return {
    tracking: !isMale() && $("#pf-cycle-on").checked,
    last_start: $("#pf-cycle-start").value || null,
    length: Number($("#pf-cycle-length").value) || 28,
    period_length: Number($("#pf-cycle-period").value) || 5,
  };
}

function syncCycle() {
  $("#pf-cycle").hidden = isMale();
  $("#pf-cycle-fields").hidden = !$("#pf-cycle-on").checked;
  const s = cycleStatus(formCycle());
  const fmt = (d) => d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  $("#pf-cycle-status").textContent = !$("#pf-cycle-on").checked ? ""
    : !$("#pf-cycle-start").value ? "Add when your last period started to see predictions."
    : !s ? "That date is a while ago. Update it to keep predictions useful."
    : s.phase === "period" ? `Today is about day ${s.cycleDay} of your period.`
    : s.phase === "premenstrual" ? `Your next period is expected in about ${s.untilNext} days.`
    : `Next period expected around ${fmt(s.next)}.`;
}

// Choosing Female turns cycle tracking on by default; anyone can switch it on or off.
$("#pf-gender").addEventListener("click", (e) => {
  const b = e.target.closest("[data-gender]");
  if (!b) return;
  // Tapping the chosen option again clears it, so gender stays optional.
  const choose = !b.classList.contains("on");
  $$("#pf-gender [data-gender]").forEach((x) => { const on = choose && x === b; x.classList.toggle("on", on); x.setAttribute("aria-pressed", String(on)); });
  if (choose && b.dataset.gender === "female" && !state.profile.cycle?.last_start) $("#pf-cycle-on").checked = true;
  syncCycle();
});
["#pf-cycle-on", "#pf-cycle-start", "#pf-cycle-length", "#pf-cycle-period"].forEach((id) => $(id).addEventListener("input", syncCycle));
$("#pf-cycle-today").addEventListener("click", () => { $("#pf-cycle-start").value = isoDate(new Date()); syncCycle(); });

$("#pf-context").addEventListener("click", (e) => {
  const b = e.target.closest("[data-context]");
  if (!b) return;
  const on = !b.classList.contains("on");
  b.classList.toggle("on", on);
  b.setAttribute("aria-pressed", String(on));
});

$("#pf-age").addEventListener("click", (e) => {
  const b = e.target.closest("[data-age]");
  if (!b) return;
  $$("#pf-age [data-age]").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", String(x === b)); });
});

$("#profile-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#pf-contact-name").value.trim(), phone = $("#pf-contact-phone").value.trim();
  const err = $("#pf-error");
  err.hidden = true;
  if (Boolean(name) !== Boolean(phone)) { err.textContent = "Add both a name and a phone for your emergency contact."; err.hidden = false; return; }
  try {
    await sendProfile("/api/profile", {
      preferred_name: $("#pf-name").value.trim() || null,
      age_group: $("#pf-age .on")?.dataset.age || null,
      gender: $("#pf-gender .on")?.dataset.gender || null,
      cycle: formCycle(),
      health_context: $$("#pf-context .on").map((b) => b.dataset.context),
      what_helps: splitList($("#pf-helps").value),
      trusted_people: splitList($("#pf-people").value),
      emergency_contact: name ? { name, phone } : null,
    });
    toast("Saved");
  } catch (ex) {
    err.textContent = ex.message;
    err.hidden = false;
  }
});

$("#memories").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-forget]");
  if (!b) return;
  try { await sendProfile("/api/memories/forget", { index: Number(b.dataset.forget) }); toast("Forgotten"); } catch { toast("Couldn't reach the server"); }
});

// Two taps, no browser dialog: the first arms the button for a few seconds.
let forgetArmed = null;
$("#forget-all").addEventListener("click", async () => {
  const b = $("#forget-all");
  if (!forgetArmed) {
    b.textContent = "Tap again to forget everything";
    forgetArmed = setTimeout(() => { forgetArmed = null; b.textContent = "Forget everything"; }, 4000);
    return;
  }
  clearTimeout(forgetArmed);
  forgetArmed = null;
  b.textContent = "Forget everything";
  try { await sendProfile("/api/memories/forget-all", {}); toast("Memories and past conversations deleted"); } catch { toast("Couldn't reach the server"); }
});

/* ---------- init ---------- */
drawArt();
renderGreeting();
syncForm();
refreshTalk();
renderSupport();
renderExercises();
renderProfile();
renderBody();
resetForm();
showTab("checkin");
