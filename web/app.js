// Tick & Tie front end: plain JavaScript, no build step.
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const S = {
  meta: null,
  profile: JSON.parse(localStorage.getItem("tt_profile") || "null"),
  token: localStorage.getItem("tt_token"),
  rating: null,
  session: null,
  mode: "diagnostic",
  persona: "associate",
  qStart: null,
  timer: null,
  busy: false,
  events: [],
};

const VERDICT = {
  correct: ["Correct", "Every graded line item checks out and the reasoning holds."],
  correct_unexplained: ["Right numbers, thin reasoning", "The interviewer will probe why."],
  incomplete: ["Incomplete", "Some required line items are missing."],
  incorrect: ["Incorrect", "At least one number is off. See which below."],
  redirect: ["Redirected", "Nothing gradable in that answer."],
};

async function api(path, body) {
  const headers = { "Content-Type": "application/json" };
  if (S.token) headers["X-Auth-Token"] = S.token;
  const r = await fetch(path, body === undefined ? { headers } : { method: "POST", headers, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401) { signOut(); throw new Error("Please sign in again."); }
  if (!r.ok) throw new Error(data.error || data.detail || `Request failed (${r.status})`);
  return data;
}

function signOut() {
  S.token = null;
  S.profile = null;
  S.session = null;
  localStorage.removeItem("tt_token");
  localStorage.removeItem("tt_profile");
  stopTimer();
  updateChip();
  setSignedIn(false);
  show("start");
}

function setSignedIn(on) {
  const pw = $("#password");
  pw.closest(".field").hidden = on;
  pw.required = !on;
  $("#name").readOnly = on;
  $("#signin-note").innerHTML = on
    ? `Signed in as <b>${esc(S.profile.name)}</b>. Your weakness map carries over. <button type="button" class="link" id="switch-user">Not you?</button>`
    : "First time? Pick any name and password and you get a private profile with your own weakness map. Next time, use the same pair to pick up where you left off.";
  const sw = $("#switch-user");
  if (sw) sw.addEventListener("click", signOut);
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.hidden = true), 6000);
}

const money = (x, dp = 4) => "$" + Number(x || 0).toFixed(dp);
const fmt = (x) => (x === null || x === undefined ? "—" : Number(x).toLocaleString(undefined, { maximumFractionDigits: 2 }));

// ------------------------------------------------------------------ views
function show(view) {
  if (view === "interview" && !S.session) view = "start";
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view || (view === "start" && t.dataset.view === "interview")));
  if (view === "map") renderMap();
  if (view === "trace") renderTrace();
  if (view === "club") renderClub();
}

$$(".tab").forEach((t) => t.addEventListener("click", () => show(t.dataset.view)));
document.addEventListener("click", (e) => {
  const g = e.target.closest("[data-goto]");
  if (g) { $("#debrief").hidden = true; show(g.dataset.goto); }
});

function pick(groupSel, key) {
  $$(`${groupSel} .opt`).forEach((b) => b.addEventListener("click", () => {
    $$(`${groupSel} .opt`).forEach((x) => x.classList.remove("sel"));
    b.classList.add("sel");
    S[key] = b.dataset.v;
  }));
}
pick("#mode-choice", "mode");
pick("#persona-choice", "persona");

// ------------------------------------------------------------------ start
async function init() {
  S.meta = await api("/api/meta");
  const sel = $("#focus");
  for (const [k, v] of Object.entries(S.meta.skills)) sel.insertAdjacentHTML("beforeend", `<option value="${k}">${esc(v)}</option>`);
  $("#key-warning").hidden = S.meta.key_present;
  if (S.token) {
    try { S.profile = await api("/api/me"); } catch { S.token = null; S.profile = null; }
  }
  if (S.profile) $("#name").value = S.profile.name;
  setSignedIn(!!S.token);
  updateChip();
  show("start");
}

function updateChip() {
  $("#profile-chip").textContent = S.profile ? `${S.profile.name} · sign out` : "Not signed in";
}
$("#profile-chip").addEventListener("click", () => {
  if (S.token && !confirm("Sign out? Your progress is saved to your profile.")) return;
  signOut();
  $("#name").focus();
});

$("#setup").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#name").value.trim();
  if (!name) return;
  const btn = $("#start-btn");
  btn.disabled = true;
  btn.textContent = "Setting up…";
  try {
    if (!S.token) {
      const r = await api("/api/signin", { name, password: $("#password").value });
      S.token = r.token;
      S.profile = r.profile;
      localStorage.setItem("tt_token", r.token);
      localStorage.setItem("tt_profile", JSON.stringify(r.profile));
      $("#password").value = "";
      setSignedIn(true);
      updateChip();
    }
    await startSession(S.mode, S.persona, $("#focus").value || null);
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Start interview";
  }
});

async function startSession(mode, persona, focus) {
  const s = await api("/api/session", { mode, persona, focus });
  S.session = s;
  S.events = s.events || [];
  $("#chat").innerHTML = "";
  resetDiag();
  addMsg("ai", s.opener, s.persona_label);
  addQuestion(s.question);
  updateMeter(s.usage);
  renderTurnTrace(s.events);
  show("interview");
  $("#answer").focus();
}

// ------------------------------------------------------------------ chat
function addMsg(kind, text, who) {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.innerHTML = `<div class="who">${esc(who || (kind === "me" ? "You" : "Interviewer"))}</div>${esc(text)}`;
  $("#chat").appendChild(el);
  el.scrollIntoView({ block: "end" });
  return el;
}

function addQuestion(q) {
  const el = document.createElement("div");
  el.className = "qcard";
  const diff = "●".repeat(q.difficulty) + "○".repeat(3 - q.difficulty);
  el.innerHTML = `
    <div class="qcard-head">
      <span class="tag skill">${esc(S.meta.skills[q.skill])}</span>
      <span class="qcard-title">${esc(q.title)}</span>
      <span class="diff" title="Difficulty">${diff}</span>
      <span class="timer" data-target="${q.target_seconds}">0:00</span>
    </div>
    <div class="qcard-text">${esc(q.text)}</div>`;
  $("#chat").appendChild(el);
  el.scrollIntoView({ block: "end" });
  startTimer(el.querySelector(".timer"), q.target_seconds);
  setAttemptHint(q);
}

function setAttemptHint(q) {
  const s = S.session?.question;
  const phase = s?.phase === "why" ? "Explain your reasoning" : `Attempt ${s?.attempt || 1} of ${S.meta.limits.attempts}`;
  $("#attempt-hint").textContent = `${phase} · target ${Math.round((q?.target_seconds || 60))}s`;
}

function startTimer(el, target) {
  stopTimer();
  S.qStart = Date.now();
  S.timer = setInterval(() => {
    const s = Math.floor((Date.now() - S.qStart) / 1000);
    el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    el.classList.toggle("over", s > target);
  }, 500);
}
function stopTimer() { clearInterval(S.timer); }

function thinking() {
  const el = document.createElement("div");
  el.className = "msg ai thinking";
  el.innerHTML = `<span class="dots"><span></span><span></span><span></span></span> Grading with the calculator…`;
  $("#chat").appendChild(el);
  el.scrollIntoView({ block: "end" });
  return el;
}

$("#answer").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); }
});

$("#composer").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (S.busy || !S.session) return;
  if (MIC.on) stopMic();
  const text = $("#answer").value.trim();
  if (!text) return;
  const seconds = S.qStart ? (Date.now() - S.qStart) / 1000 : null;
  S.busy = true;
  $("#send-btn").disabled = true;
  addMsg("me", text, S.profile?.name);
  $("#answer").value = "";
  const t = thinking();
  try {
    const r = await api(`/api/session/${S.session.id}/answer`, { text, seconds });
    t.remove();
    handleTurn(r);
  } catch (err) {
    t.remove();
    toast(err.message);
  } finally {
    S.busy = false;
    $("#send-btn").disabled = false;
    $("#answer").focus();
  }
});

function handleTurn(r) {
  S.events = S.events.concat(r.events || []);
  renderShield(r.events || []);
  renderTurnTrace(r.events || []);
  if (r.blocked) {
    addMsg("ai", r.reason, "Tick & Tie");
    updateMeter(r.session?.usage);
    return;
  }
  S.session = { ...S.session, ...r.session };
  addMsg("ai", r.interviewer, S.session.persona_label);
  renderDiag(r);
  updateMeter(r.session.usage);
  if (r.next_question) {
    stopTimer();
    addQuestion(r.next_question);
  } else {
    setAttemptHint(r.session.question);
  }
}

// ------------------------------------------------------------------ diagnosis panel
function resetDiag() {
  $("#diag-empty").hidden = false;
  $("#diag-body").hidden = true;
  $("#shield").hidden = true;
  $("#shield-list").innerHTML = "";
}

function renderDiag(r) {
  $("#diag-empty").hidden = true;
  $("#diag-body").hidden = false;
  const v = r.verdict;
  const [title, sub] = VERDICT[v] || [v, ""];
  const tail = r.explain_only ? " (your explanation)" : "";
  $("#verdict").className = `verdict v-${v}`;
  $("#verdict").innerHTML = `<span class="dot"></span><div>${esc(title + tail)}<div class="muted" style="font-size:13px;font-weight:500">${esc(sub)}</div></div>`;

  const checks = r.checks || [];
  $("#checks").innerHTML = checks.map((c) => {
    const cls = c.status === "correct" ? "ok" : c.status === "wrong" ? "bad" : "miss";
    const ic = c.status === "correct" ? "✓" : c.status === "wrong" ? "✗" : "–";
    let val = c.stated === null ? (c.required ? "not stated" : "optional") : `you: <b>${fmt(c.stated)}</b>`;
    if (c.expected !== null && c.expected !== undefined && c.status !== "correct") val += ` · key: <b>${fmt(c.expected)}</b>`;
    return `<li class="${cls}"><span class="ic">${ic}</span><span>${esc(c.name)}${c.required ? "" : ' <span class="muted">(optional)</span>'}</span><span class="val">${val}</span></li>`;
  }).join("");

  $("#mis-wrap").innerHTML = (r.misconceptions || []).map((m) =>
    `<div class="mis"><b>${esc(m.name)}</b><p>${esc(m.fix)}</p></div>`).join("");
  $("#rationale").textContent = r.rationale ? `Grader's note: ${r.rationale}` : (!r.resolved && v !== "correct" ? "Details unlock once you've had your second attempt, so you can fix it yourself first." : "");
  $("#solution-wrap").hidden = !r.solution;
  $("#solution").textContent = r.solution || "";
  if (r.action === "reveal" || r.action === "note_next") $("#solution-wrap").open = true;
}

function renderShield(events) {
  const safety = events.filter((e) => e.kind === "safety");
  if (!safety.length) return;
  $("#shield").hidden = false;
  $("#shield-list").insertAdjacentHTML("afterbegin", safety.map((e) => `<li>${esc(e.summary)}</li>`).join(""));
}

function actorClass(a) {
  return ["Director", "Guard", "Calculator", "Interviewer", "Coach"].includes(a) ? a : "spec";
}

function traceItem(e, compact) {
  const tok = e.kind === "llm" ? `<span class="tok">${fmt(e.input_tokens)} in (${fmt(e.cached_tokens)} cached) · ${fmt(e.output_tokens)} out · ${money(e.cost_usd, 5)}</span>` : `<span class="tok"></span>`;
  const detail = !compact && e.detail && Object.keys(e.detail).length
    ? `<details><summary>details</summary><pre>${esc(JSON.stringify(e.detail, null, 2))}</pre></details>` : "";
  return `<li><span class="actor ${actorClass(e.actor)}">${esc(e.actor)}</span><span>${esc(e.summary)}</span>${tok}${detail}</li>`;
}

function renderTurnTrace(events) {
  $("#turn-trace").innerHTML = events.map((e) => traceItem(e, true)).join("") || `<li class="muted">—</li>`;
}

function updateMeter(u) {
  if (!u) return;
  const total = (u.input_tokens || 0) + (u.output_tokens || 0);
  $("#meter-cost").textContent = money(u.cost_usd);
  $("#meter-tokens").textContent = total.toLocaleString();
  const budget = S.session?.budget || S.meta.limits.session_tokens;
  $("#meter-fill").style.width = `${Math.min(100, (100 * total) / budget)}%`;
}

// ------------------------------------------------------------------ end & debrief
$("#end-btn").addEventListener("click", async () => {
  if (!S.session || S.busy) return;
  S.busy = true;
  const b = $("#end-btn");
  b.textContent = "Writing debrief…";
  try {
    const r = await api(`/api/session/${S.session.id}/end`, {});
    stopTimer();
    renderDebrief(r);
    S.events = r.events;
  } catch (err) {
    toast(err.message);
  } finally {
    S.busy = false;
    b.textContent = "End & debrief";
  }
});

function renderDebrief(r) {
  const d = r.debrief || {};
  $("#db-headline").textContent = d.headline || "Session complete.";
  $("#db-strengths").innerHTML = (d.strengths || []).map((s) => `<li>${esc(s)}</li>`).join("") || `<li class="muted">Not enough answers yet.</li>`;
  $("#db-focus").innerHTML = (d.focus_areas || []).map((f) =>
    `<div class="focus"><b>${esc(f.name || f.misconception_id)}</b> · ${esc(f.why_it_matters)}<br>${esc(f.drill)}</div>`).join("") || `<p class="muted">No misconceptions detected this session.</p>`;
  $("#db-next").textContent = d.next_session || "";
  const rows = Object.entries(S.meta.skills).map(([k, name]) => {
    const a = Math.round(100 * (r.mastery_start?.[k]?.p ?? 0.3));
    const b = Math.round(100 * (r.mastery_end?.[k]?.p ?? 0.3));
    const dl = b - a;
    return `<div class="mrow"><span>${esc(name)}</span><div class="bar"><div class="ghostbar" style="width:${a}%"></div><div style="width:${b}%"></div></div>
      <span class="${dl > 0 ? "delta-up" : dl < 0 ? "delta-down" : "muted"}">${a}→${b}%</span></div>`;
  }).join("");
  $("#db-mastery").innerHTML = rows;
  const u = r.usage || {};
  const answered = (r.turns || []).filter((t) => t.verdict).length;
  $("#db-foot").textContent = `${answered} graded answers · ${(u.input_tokens + u.output_tokens).toLocaleString()} tokens (${(u.cached_tokens || 0).toLocaleString()} cached) · ${money(u.cost_usd)} total`;
  resetSurvey();
  $("#debrief").hidden = false;
}

// ------------------------------------------------------------------ pilot survey
$$("#rating button").forEach((b) => b.addEventListener("click", () => {
  $$("#rating button").forEach((x) => x.classList.remove("sel"));
  b.classList.add("sel");
  S.rating = Number(b.textContent);
}));

function resetSurvey() {
  S.rating = null;
  $$("#rating button").forEach((x) => x.classList.remove("sel"));
  $("#survey").reset();
  $("#survey-status").textContent = "";
  $("#survey button[type=submit]").disabled = false;
}

$("#survey").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    session_id: S.session?.id || null, rating: S.rating,
    vs_current: $("#vs-current").value || null, found_new: $("#found-new").value || null,
    time_to_find: $("#time-to-find").value || null, prep_today: $("#prep-today").value.trim() || null,
    quote: $("#quote").value.trim() || null, consent: $("#consent").checked,
  };
  if (!body.rating && !body.quote && !body.vs_current) { $("#survey-status").textContent = "Pick a rating or write a line first."; return; }
  try {
    await api("/api/feedback", body);
    $("#survey-status").textContent = "Thanks! Feedback saved.";
    $("#survey button[type=submit]").disabled = true;
  } catch (err) { toast(err.message); }
});
$("#debrief-close").addEventListener("click", () => ($("#debrief").hidden = true));
$("#db-again").addEventListener("click", () => {
  $("#debrief").hidden = true;
  S.session = null;
  show("start");
});

// ------------------------------------------------------------------ map
async function renderMap() {
  if (!S.token) { $("#skills").innerHTML = `<p class="muted">Sign in and start a session first.</p>`; $("#mis-list").innerHTML = ""; return; }
  const m = await api("/api/map");
  $("#skills").innerHTML = m.skills.map((s) => {
    const pct = Math.round(s.p * 100);
    const t = s.avg_seconds ? ` · avg ${s.avg_seconds}s per answer` : "";
    return `<div class="skill"><div class="skill-top"><b>${esc(s.name)}</b><span>${pct}% · ${esc(s.level)}</span></div>
      <div class="bar lv-${s.level.replace(" ", "-")}"><div style="width:${pct}%"></div></div>
      <div class="skill-sub">${s.n} question${s.n === 1 ? "" : "s"} graded${t}</div></div>`;
  }).join("");
  $("#mis-list").innerHTML = m.misconceptions.length ? m.misconceptions.map((x) => {
    const ev = (x.evidence || []).slice(-2).reverse().map((e) => e.quote ? `<q>${esc(e.quote)}</q>` : "").join("");
    const st = x.active ? `<span class="tag active">active</span>` : `<span class="tag cleared">cleared</span>`;
    return `<div class="mis-item"><div class="top">${st}<b>${esc(x.name)}</b><span class="tag">${esc(S.meta.skills[x.skill] || "General")}</span>
      <span class="tag">seen ${x.hits}×</span></div>${ev}<p>${esc(x.fix)}</p></div>`;
  }).join("") : `<p class="muted">No misconceptions yet. Run a diagnostic session to build your map.</p>`;
}
$("#drill-btn").addEventListener("click", async () => {
  if (!S.token) return show("start");
  try { await startSession("drill", S.persona, null); } catch (e) { toast(e.message); }
});

// ------------------------------------------------------------------ trace & cost
async function renderTrace() {
  if (S.session) {
    const r = await api(`/api/session/${S.session.id}/events`);
    S.events = r.events;
    $("#trace").innerHTML = r.events.map((e) => traceItem(e, false)).join("");
    const u = r.usage;
    const total = u.input_tokens + u.output_tokens;
    const cachedPct = u.input_tokens ? Math.round((100 * u.cached_tokens) / u.input_tokens) : 0;
    $("#kpis").innerHTML = `
      <div class="kpi"><b>${money(u.cost_usd)}</b><span>cost this session</span></div>
      <div class="kpi"><b>${total.toLocaleString()}</b><span>tokens (${u.llm_calls} model calls)</span></div>
      <div class="kpi"><b>${cachedPct}%</b><span>of input served from cache</span></div>
      <div class="kpi"><b>${u.output_tokens.toLocaleString()}</b><span>output tokens</span></div>`;
  } else {
    $("#trace").innerHTML = `<li class="muted">Start a session to see the trace.</li>`;
    $("#kpis").innerHTML = "";
  }
  const c = await api("/api/costs");
  $("#agent-tbl").innerHTML = `<tr><th>Agent</th><th>Calls</th><th>Input</th><th>Cached</th><th>Output</th><th>Cost</th></tr>` +
    c.per_agent.map((a) => `<tr><td><span class="actor ${actorClass(a.actor)}">${esc(a.actor)}</span></td><td>${a.calls}</td>
      <td>${fmt(a.input_tokens)}</td><td>${fmt(a.cached_tokens)}</td><td>${fmt(a.output_tokens)}</td><td>${money(a.cost_usd, 4)}</td></tr>`).join("") +
    `<tr><td><b>Per graded answer</b></td><td></td><td>${fmt(Math.round(c.per_answer.i))}</td><td>${fmt(Math.round(c.per_answer.cch))}</td><td>${fmt(Math.round(c.per_answer.o))}</td><td><b>${money(c.per_answer.usd, 5)}</b></td></tr>`;
}

// ------------------------------------------------------------------ club
async function renderClub() {
  const c = await api("/api/club");
  const n = Math.max(c.members, 1);
  $("#club-mis").innerHTML = c.misconceptions.length ? `<p class="muted" style="margin-top:0">${c.members} members · ${c.answers} graded answers</p>` +
    c.misconceptions.slice(0, 10).map((m) => {
      const pct = Math.round((100 * m.members) / n);
      return `<div class="club-row"><div>${esc(m.name)}<small>${esc(m.skill)} · ${m.hits} occurrences</small><div class="bar"><div style="width:${pct}%"></div></div></div><b>${pct}%</b></div>`;
    }).join("") : `<p class="muted">No data yet.</p>`;
  $("#club-skills").innerHTML = c.skills.map((s) => {
    const pct = Math.round(100 * s.avg_p);
    return `<div class="skill"><div class="skill-top"><b>${esc(s.name)}</b><span>${pct}%</span></div><div class="bar"><div style="width:${pct}%"></div></div></div>`;
  }).join("");
}


// ------------------------------------------------------------------ voice input (browser speech recognition, no tokens)
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const MIC = { rec: null, on: false, base: "" };

function setupMic() {
  const b = $("#mic-btn");
  if (!SR) { b.disabled = true; b.title = "Voice input needs Chrome or Edge"; return; }
  b.addEventListener("click", () => (MIC.on ? stopMic() : startMic()));
}

function startMic() {
  MIC.rec = new SR();
  MIC.rec.lang = "en-US";
  MIC.rec.continuous = true;
  MIC.rec.interimResults = true;
  MIC.base = $("#answer").value.trim() ? $("#answer").value.trim() + " " : "";
  MIC.rec.onresult = (e) => {
    let text = "";
    for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
    $("#answer").value = MIC.base + text.trim();
  };
  MIC.rec.onerror = (e) => {
    if (e.error === "no-speech") return;
    toast(e.error === "not-allowed" ? "Microphone access is blocked. Allow it from the icon in the address bar." : `Voice input stopped (${e.error}).`);
    stopMic();
  };
  MIC.rec.onend = () => {  // browsers stop after a pause; keep listening until the user clicks stop
    if (MIC.on) { MIC.base = $("#answer").value.trim() + " "; try { MIC.rec.start(); } catch {} }
  };
  MIC.rec.start();
  MIC.on = true;
  $("#mic-btn").classList.add("rec");
  $("#mic-label").textContent = "Listening… tap to stop";
}

function stopMic() {
  MIC.on = false;
  if (MIC.rec) try { MIC.rec.stop(); } catch {}
  $("#mic-btn").classList.remove("rec");
  $("#mic-label").textContent = "Speak";
}
setupMic();

init().catch((e) => toast(e.message));
