// Tick & Tie front end: plain JavaScript, no build step.
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (x, dp = 4) => "$" + Number(x || 0).toFixed(dp);
const fmt = (x) => (x === null || x === undefined ? "—" : Number(x).toLocaleString(undefined, { maximumFractionDigits: 2 }));
const LEVEL_NAMES = ["Foundations", "Basic", "Intermediate", "Advanced"];

const S = {
  meta: null, token: localStorage.getItem("tt_token"), profile: JSON.parse(localStorage.getItem("tt_profile") || "null"),
  dash: null, session: null, persona: "associate", group: null, stage: "first_rounds", events: [],
  busy: false, qStart: null, timer: null, rating: null, lastReport: null,
  tts: localStorage.getItem("tt_tts") === "1", handsfree: localStorage.getItem("tt_hf") === "1",
};

const VERDICT = {
  correct: ["Correct", "Every graded line item checks out and the reasoning holds."],
  correct_unexplained: ["Right numbers, thin reasoning", "The interviewer will probe why."],
  incomplete: ["Incomplete", "Some required points are missing."],
  incorrect: ["Not quite", "At least one number or key idea is off. See which below."],
  redirect: ["Redirected", "Nothing gradable in that answer."],
};

// ------------------------------------------------------------------ api
async function api(path, body) {
  const headers = { "Content-Type": "application/json" };
  if (S.token) headers["X-Auth-Token"] = S.token;
  const r = await fetch(path, body === undefined ? { headers } : { method: "POST", headers, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401) { signOut(); throw new Error("Please sign in again."); }
  if (!r.ok) throw new Error(data.error || data.detail || `Request failed (${r.status})`);
  return data;
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 6000);
}

// ------------------------------------------------------------------ navigation
function show(view) {
  if (view === "interview" && !S.session) view = "dashboard";
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  $("#meter").hidden = view !== "interview";
  if (view === "dashboard") loadDashboard();
  if (view === "plan") renderPlan();
  if (view === "skills") renderSkillsPage();
  if (view === "trace") renderTrace();
  if (view === "club") renderClub();
  window.scrollTo({ top: 0 });
}
$$(".tab").forEach((t) => t.addEventListener("click", () => show(t.dataset.view)));
document.addEventListener("click", (e) => { const g = e.target.closest("[data-goto]"); if (g) show(g.dataset.goto); });

function signedInUI(on) {
  $("#tabs").hidden = !on;
  $("#profile-chip").hidden = !on;
  $("#profile-chip").textContent = on ? `${S.profile.name} · sign out` : "";
}
function signOut() {
  S.token = null; S.profile = null; S.session = null; S.dash = null;
  localStorage.removeItem("tt_token"); localStorage.removeItem("tt_profile");
  stopTimer(); stopMic(); signedInUI(false); show("welcome");
}
$("#profile-chip").addEventListener("click", () => { if (confirm("Sign out? Your progress is saved.")) signOut(); });

// ------------------------------------------------------------------ boot
async function init() {
  S.meta = await api("/api/meta");
  $("#key-warning").hidden = S.meta.key_present;
  buildIntakeOptions();
  buildQuickControls();
  $("#tts-toggle").checked = S.tts; $("#handsfree-toggle").checked = S.handsfree;
  if (S.token) {
    try { S.profile = await api("/api/me"); } catch { S.token = null; }
  }
  if (!S.token) { signedInUI(false); show("welcome"); return; }
  signedInUI(true);
  await routeHome();
}

async function routeHome() {
  S.dash = await api("/api/dashboard");
  if (S.dash.needs_intake) { openIntake(); return; }
  show("dashboard");
}

$("#signin").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("#signin-btn"); btn.disabled = true; btn.textContent = "Signing in…";
  try {
    const r = await api("/api/signin", { name: $("#name").value.trim(), password: $("#password").value });
    S.token = r.token; S.profile = r.profile;
    localStorage.setItem("tt_token", r.token); localStorage.setItem("tt_profile", JSON.stringify(r.profile));
    $("#password").value = "";
    signedInUI(true);
    await routeHome();
  } catch (err) { toast(err.message); } finally { btn.disabled = false; btn.textContent = "Continue"; }
});

// ------------------------------------------------------------------ intake
function optButton(v, label, sub, sel) {
  return `<button type="button" class="opt${sel ? " sel" : ""}" data-v="${esc(v)}"><b>${esc(label)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</button>`;
}
function wireChoice(container, key) {
  $$(`${container} .opt`).forEach((b) => b.addEventListener("click", () => {
    $$(`${container} .opt`).forEach((x) => x.classList.remove("sel"));
    b.classList.add("sel"); S[key] = b.dataset.v;
  }));
}
function buildIntakeOptions() {
  const cov = S.meta.groups.filter((g) => g.kind === "coverage"), prod = S.meta.groups.filter((g) => g.kind === "product");
  $("#groups-coverage").innerHTML = cov.map((g) => optButton(g.id, g.name)).join("");
  $("#groups-product").innerHTML = prod.map((g) => optButton(g.id, g.name)).join("");
  $$("#groups-coverage .opt, #groups-product .opt").forEach((b) => b.addEventListener("click", () => {
    $$("#groups-coverage .opt, #groups-product .opt").forEach((x) => x.classList.remove("sel"));
    b.classList.add("sel"); S.group = b.dataset.v;
  }));
  const stageSub = { networking: "Coffee chats", first_rounds: "First rounds", superdays: "Final rounds", offer: "Staying sharp" };
  $("#stages").innerHTML = Object.entries(S.meta.stages).map(([k, v]) => optButton(k, v, stageSub[k], k === S.stage)).join("");
  wireChoice("#stages", "stage");
  wireChoice("#persona-choice", "persona");
  $("#hours").addEventListener("input", () => ($("#hours-val").textContent = `${$("#hours").value} h/week`));
  const d = new Date(); d.setDate(d.getDate() + 21); $("#interview-date").value = d.toISOString().slice(0, 10);
}
function openIntake() {
  const i = S.dash?.intake || {};
  if (i.group) { S.group = i.group; $$(`#groups-coverage .opt, #groups-product .opt`).forEach((b) => b.classList.toggle("sel", b.dataset.v === i.group)); }
  if (i.stage) { S.stage = i.stage; $$("#stages .opt").forEach((b) => b.classList.toggle("sel", b.dataset.v === i.stage)); }
  if (i.persona) { S.persona = i.persona; $$("#persona-choice .opt").forEach((b) => b.classList.toggle("sel", b.dataset.v === i.persona)); }
  if (i.interview_date) $("#interview-date").value = i.interview_date;
  if (i.hours_per_week) { $("#hours").value = i.hours_per_week; $("#hours-val").textContent = `${i.hours_per_week} h/week`; }
  $("#intake-btn").textContent = S.dash?.diagnostic_done ? "Save and rebuild my plan" : "Save and start my placement interview";
  show("intake");
}
$("#edit-intake").addEventListener("click", openIntake);
$("#intake").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!S.group) { toast("Pick the group you're targeting (or Generalist)."); return; }
  const btn = $("#intake-btn"); btn.disabled = true;
  try {
    await api("/api/intake", { group: S.group, stage: S.stage, interview_date: $("#interview-date").value || null,
      hours_per_week: Number($("#hours").value), persona: S.persona });
    if (S.dash?.diagnostic_done) { await api("/api/plan/rebuild", {}); await routeHome(); show("plan"); }
    else await startSession("diagnostic", S.persona);
  } catch (err) { toast(err.message); } finally { btn.disabled = false; }
});

// ------------------------------------------------------------------ dashboard
function ladderHTML(level, target) {
  return [1, 2, 3].map((l) => `<span class="${l <= level ? "on" : l === target ? "tgt" : ""}" title="${LEVEL_NAMES[l]}"></span>`).join("");
}
function sparkline(hist, color) {
  const pts = (hist || []).map((h) => h.p);
  if (pts.length < 2) return `<svg class="spark" viewBox="0 0 200 44"><text x="0" y="28" font-size="11" fill="#9a95b0">Trend appears after your next session</text></svg>`;
  const xs = pts.map((_, i) => (i / (pts.length - 1)) * 196 + 2), ys = pts.map((p) => 40 - p * 36);
  const d = xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 200 44" preserveAspectRatio="none"><path d="${d} L198,44 L2,44 Z" fill="${color}" opacity=".18"/>
    <path d="${d}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${xs.at(-1)}" cy="${ys.at(-1)}" r="3.5" fill="${color}"/></svg>`;
}
const SKILL_INK = { accounting: "#2f7cb8", ev: "#5e4cc2", dcf: "#237e5b", ma: "#c4652e", lbo: "#c2456a", industry: "#9a7408", fit: "#7a4fc4" };
function skillName(key, name) { return key === "industry" ? `${S.dash?.group_name?.split(" (")[0] || "Group"} specifics` : name; }
function skillCard(s, full) {
  const pct = Math.round(s.p * 100);
  const subs = (s.subskills || []).slice(0, full ? 12 : 4).map((x) =>
    `<span class="subchip ${x.p < 0.5 ? "weak" : x.p >= 0.75 ? "ok" : ""}" title="${Math.round(x.p * 100)}% on ${x.n} answer(s)">${esc(x.name)}</span>`).join("");
  const name = skillName(s.key, s.name);
  return `<div class="card skill-card c-${s.key}" data-skill="${s.key}">
    <h4>${esc(name)} <span class="pill lvl-${s.level}">${esc(s.level_name)}</span></h4>
    <div class="ladder">${ladderHTML(s.level, s.target)}</div>
    <div class="bar"><div style="width:${pct}%"></div></div>
    <div class="small muted">${pct}% mastery · ${s.n} graded${s.avg_seconds ? ` · ${s.avg_seconds}s avg` : ""} · next: ${LEVEL_NAMES[s.target]}</div>
    ${sparkline(s.history, SKILL_INK[s.key])}
    ${subs ? `<div class="sub">${subs}</div>` : ""}
    ${full ? `<div class="skill-detail"><button class="ghost" data-drill="${s.key}">Drill ${esc(name)}</button></div>` : ""}
  </div>`;
}
function taskHTML(t, withBtn) {
  const meta = t.type === "drill" ? `${LEVEL_NAMES[t.level]} · ${t.minutes} min` : `${t.minutes} min · mixed questions`;
  return `<li class="task ${t.done ? "done" : ""}"><span class="tick">${t.done ? "✓" : ""}</span>
    <div><div class="ttl">${esc(t.title)}</div><div class="meta">${esc(meta)}</div></div>
    ${withBtn && !t.done ? `<button class="ghost" data-task="${t.id}">Start</button>` : "<span></span>"}</li>`;
}

async function loadDashboard() {
  try { S.dash = await api("/api/dashboard"); } catch (e) { toast(e.message); return; }
  const d = S.dash;
  $("#dash-hello").textContent = `Hi ${S.profile.name.split(" ")[0]}`;
  $("#dash-sub").textContent = `${d.group_name}${d.intake?.interview_date ? ` · interview ${d.intake.interview_date}` : ""}`;
  const cta = $("#dash-cta");
  if (!d.diagnostic_done) { cta.textContent = "Start placement interview"; cta.onclick = () => startSession("diagnostic", d.intake.persona || "associate"); }
  else if (d.progress?.next) { cta.textContent = `Next: ${d.progress.next.title}`; cta.onclick = () => startTask(d.progress.next); }
  else { cta.textContent = "Mock interview"; cta.onclick = () => startSession("mock", d.intake.persona || "vp"); }
  $("#lvl-now").textContent = d.diagnostic_done ? d.overall_label : "Not placed yet";
  $("#lvl-target").textContent = d.diagnostic_done ? `Target: ${d.target_label}` : "Take the 15-minute placement interview first";
  $("#lvl-ladder").innerHTML = ladderHTML(d.overall_level, Math.min(d.overall_level + 1, 3));
  const p = d.progress;
  $("#plan-ring").style.setProperty("--p", p ? p.pct : 0);
  $("#plan-pct").textContent = p ? `${p.pct}%` : "–";
  $("#plan-text").innerHTML = p ? `<b>${p.done} of ${p.total}</b> plan tasks done<br><span class="muted">${p.due_done}/${p.due} due so far · ${d.plan.days_left} days in plan</span>`
    : `<span class="muted">Your plan appears after the placement interview.</span>`;
  const st = $("#plan-status");
  st.textContent = p ? p.status : ""; st.className = `status ${p ? p.status.replace(" ", "-") : ""}`;
  $("#st-streak").textContent = d.streak; $("#st-sessions").textContent = d.sessions; $("#st-answers").textContent = d.answered;
  $("#dash-skills").innerHTML = d.skills.filter((s) => s.key !== "industry" || (d.intake.group && d.intake.group !== "generalist")).map((s) => skillCard(s, false)).join("");
  const today = p ? (p.today.length ? p.today : (p.next ? [p.next] : [])) : [];
  $("#today").innerHTML = today.length ? today.map((t) => taskHTML(t, true)).join("") : `<li class="muted small">${d.diagnostic_done ? "Nothing due today. Try a mock interview." : "Take the placement interview to get your plan."}</li>`;
}
$("#today").addEventListener("click", (e) => { const b = e.target.closest("[data-task]"); if (b) startTask(S.dash.plan.tasks.find((t) => t.id == b.dataset.task)); });
$("#dash-skills").addEventListener("click", () => show("skills"));

function buildQuickControls() {
  $("#q-persona").innerHTML = Object.entries(S.meta.personas).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#q-skill").innerHTML = Object.entries(S.meta.skills).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#q-level").innerHTML = `<option value="">My next level</option>` + [1, 2, 3].map((l) => `<option value="${l}">${LEVEL_NAMES[l]}</option>`).join("");
}
$("#q-mock").addEventListener("click", () => startSession("mock", $("#q-persona").value));
$("#q-practice").addEventListener("click", () => startSession("practice", $("#q-persona").value, $("#q-skill").value, Number($("#q-level").value) || null));

function startTask(t) {
  if (!t) return;
  const persona = S.dash?.intake?.persona || "associate";
  if (t.type === "mock") startSession("mock", t.final ? "md" : persona);
  else startSession("drill", persona);
}

// ------------------------------------------------------------------ plan
async function renderPlan() {
  if (!S.dash) S.dash = await api("/api/dashboard");
  const plan = S.dash.plan;
  if (!plan) { $("#plan-summary").innerHTML = `<p class="muted">Your plan appears after the placement interview.</p>`; $("#calendar").innerHTML = ""; $("#plan-ladder").innerHTML = ""; return; }
  const sm = plan.summary || {};
  $("#plan-summary").innerHTML = `<div class="card-title">Your action plan</div><h3>${esc(sm.headline)}</h3><p>${esc(sm.why)}</p>
    <p class="first">→ ${esc(sm.first_step)}</p>
    <div class="stat-row" style="margin-top:12px"><div class="stat"><b>${plan.hours_planned}h</b><span>total, of ${plan.hours_available}h available</span></div>
      <div class="stat"><b>${plan.drills}</b><span>targeted drills</span></div><div class="stat"><b>${plan.mocks}</b><span>mock interviews</span></div></div>
    <p class="small muted" style="margin-top:10px">${plan.questions} practice questions over ${plan.days_left} days · about ${plan.minutes_per_practice_day} min per practice day · one rest day a week.</p>
    ${plan.compressed ? `<div class="flag">Time is tight: the plan keeps the highest-priority work (weakest skills and sub-skills first).</div>` : ""}`;
  $("#plan-ladder").innerHTML = `<tr><th>Skill</th><th>Now</th><th></th><th>Target</th><th>Drills</th></tr>` + plan.skills.map((r) =>
    `<tr class="c-${r.skill}"><td><span class="pill">${esc(skillName(r.skill, r.name))}</span></td><td><span class="pill lvl-${r.current}">${LEVEL_NAMES[r.current]}</span></td>
     <td>→</td><td><span class="pill lvl-${r.target}">${LEVEL_NAMES[r.target]}</span></td><td>${r.drills}</td></tr>
     ${r.weak_subskills.length ? `<tr><td colspan="5" class="small muted" style="padding-top:0">Weak sub-skills: ${r.weak_subskills.map((w) => esc(w.name)).join(", ")}</td></tr>` : ""}`).join("");
  const byDay = {};
  plan.tasks.forEach((t) => (byDay[t.date] = byDay[t.date] || []).push(t));
  const today = new Date().toISOString().slice(0, 10);
  $("#calendar").innerHTML = Object.entries(byDay).map(([d, ts]) => {
    const dt = new Date(d + "T12:00:00");
    const label = dt.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    const mins = ts.reduce((a, t) => a + t.minutes, 0);
    return `<div class="day ${d === today ? "today" : ""}"><h5><span>${label}${d === today ? " · today" : ""}</span><span class="muted">${mins} min</span></h5>
      <ul style="padding:0;margin:0">${ts.map((t) => taskHTML(t, false)).join("")}</ul></div>`;
  }).join("");
}
$("#plan-rebuild").addEventListener("click", async () => {
  try { await api("/api/plan/rebuild", {}); S.dash = await api("/api/dashboard"); renderPlan(); toast("Plan rebuilt from your latest results."); } catch (e) { toast(e.message); }
});

// ------------------------------------------------------------------ interview
async function startSession(mode, persona, focus = null, level = null) {
  try {
    const s = await api("/api/session", { mode, persona, focus, level });
    S.session = s; S.events = s.events || [];
    $("#chat").innerHTML = ""; resetDiag(); show("interview");
    $("#sb-mode").textContent = { diagnostic: "Placement interview", drill: "Targeted drill", mock: "Mock interview", practice: "Practice" }[mode] + ` · ${s.persona_label}`;
    addMsg("ai", s.opener, s.persona_label);
    addQuestion(s.question);
    updateSessionBar(s.progress);
    updateMeter(s.usage);
    renderTurnTrace(s.events);
    speak(`${s.opener} ${s.question.text}`, s.persona);
    $("#answer").focus();
  } catch (e) { toast(e.message); }
}

function updateSessionBar(p) {
  if (!p) return;
  $("#sb-label").textContent = p.kind === "diagnostic" ? `${p.label} · skill ${Math.min(p.skills_done + 1, p.skills_total)} of ${p.skills_total}` : p.label;
  $("#sb-fill").style.width = `${p.pct}%`;
}

function addMsg(kind, text, who) {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  const btn = kind === "ai" ? ` <button class="speak-btn" title="Read aloud" type="button">🔊</button>` : "";
  el.innerHTML = `<div class="who">${esc(who || (kind === "me" ? "You" : "Interviewer"))}${btn}</div>${esc(text)}`;
  if (kind === "ai") el.querySelector(".speak-btn").addEventListener("click", () => speak(text, S.session?.persona, true));
  $("#chat").appendChild(el); el.scrollIntoView({ block: "end" });
}
function addQuestion(q) {
  const el = document.createElement("div");
  el.className = `qcard c-${q.skill}`;
  el.innerHTML = `<div class="qcard-head"><span class="pill">${esc(skillName(q.skill, S.meta.skills[q.skill]))}</span>
    <span class="pill lvl-${q.difficulty}">${esc(q.level)}</span>
    ${q.subskill_name ? `<span class="small muted">${esc(q.subskill_name)}</span>` : ""}
    <span class="timer" data-target="${q.target_seconds}">0:00</span></div>
    <div class="qcard-title">${esc(q.title)}</div><div class="qcard-text" style="margin-top:4px">${esc(q.text)}</div>`;
  $("#chat").appendChild(el); el.scrollIntoView({ block: "end" });
  startTimer(el.querySelector(".timer"), q.target_seconds);
  setHint();
}
function setHint() {
  const q = S.session?.question;
  if (!q) return;
  const phase = q.phase === "why" ? "Explain your reasoning" : q.attempts_allowed === 1 ? "One attempt (placement)" : `Attempt ${q.attempt} of ${q.attempts_allowed}`;
  $("#attempt-hint").textContent = `${phase} · target ${q.target_seconds}s`;
}
function startTimer(el, target) {
  stopTimer(); S.qStart = Date.now();
  S.timer = setInterval(() => { const s = Math.floor((Date.now() - S.qStart) / 1000);
    el.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; el.classList.toggle("over", s > target); }, 500);
}
function stopTimer() { clearInterval(S.timer); }
function thinking() {
  const el = document.createElement("div"); el.className = "msg ai thinking";
  el.innerHTML = `<span class="dots"><span></span><span></span><span></span></span> Checking your numbers…`;
  $("#chat").appendChild(el); el.scrollIntoView({ block: "end" }); return el;
}

$("#answer").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); } });
$("#composer").addEventListener("submit", (e) => { e.preventDefault(); submitAnswer(); });

async function submitAnswer() {
  if (S.busy || !S.session) return;
  if (MIC.on) stopMic();
  const text = $("#answer").value.trim();
  if (!text) return;
  const seconds = S.qStart ? (Date.now() - S.qStart) / 1000 : null;
  S.busy = true; $("#send-btn").disabled = true;
  addMsg("me", text, S.profile.name); $("#answer").value = "";
  const t = thinking();
  try {
    const r = await api(`/api/session/${S.session.id}/answer`, { text, seconds });
    t.remove(); await handleTurn(r);
  } catch (err) { t.remove(); toast(err.message); }
  finally { S.busy = false; $("#send-btn").disabled = false; $("#answer").focus(); }
}

async function handleTurn(r) {
  S.events = S.events.concat(r.events || []);
  renderShield(r.events || []); renderTurnTrace(r.events || []);
  if (r.blocked) { addMsg("ai", r.reason, "Tick & Tie"); updateMeter(r.session?.usage); return; }
  S.session = { ...S.session, ...r.session };
  addMsg("ai", r.interviewer, S.session.persona_label);
  renderDiag(r); updateMeter(r.session.usage); updateSessionBar(r.progress);
  if (r.complete) {
    stopTimer();
    addMsg("ai", "Session complete. Updating your skills map…", "Tick & Tie");
    await finishSession();
    return;
  }
  if (r.next_question) { stopTimer(); addQuestion(r.next_question); speak(`${r.interviewer} ${r.next_question.text}`, S.session.persona); }
  else { setHint(); speak(r.interviewer, S.session.persona); }
}

// ------------------------------------------------------------------ diagnosis panel
function resetDiag() { $("#diag-empty").hidden = false; $("#diag-body").hidden = true; $("#shield").hidden = true; $("#shield-list").innerHTML = ""; }
function renderDiag(r) {
  $("#diag-empty").hidden = true; $("#diag-body").hidden = false;
  const [title, sub] = VERDICT[r.verdict] || [r.verdict, ""];
  $("#verdict").className = `verdict v-${r.verdict}`;
  $("#verdict").innerHTML = `<span class="dot"></span><div>${esc(title)}${r.explain_only ? " (your explanation)" : ""}<div class="small muted" style="font-weight:500">${esc(sub)}</div></div>`;
  $("#checks").innerHTML = (r.checks || []).map((c) => {
    const cls = c.status === "correct" ? "ok" : c.status === "wrong" ? "bad" : "miss";
    const ic = c.status === "correct" ? "✓" : c.status === "wrong" ? "✗" : "–";
    let val = c.stated === null ? (c.required ? "not stated" : "optional") : `you: <b>${fmt(c.stated)}</b>`;
    if (c.expected !== null && c.expected !== undefined && c.status !== "correct") val += ` · key: <b>${fmt(c.expected)}</b>`;
    return `<li class="${cls}"><span class="ic">${ic}</span><span>${esc(c.name)}${c.required ? "" : ' <span class="muted">(optional)</span>'}</span><span class="val">${val}</span></li>`;
  }).join("");
  $("#mis-wrap").innerHTML = (r.misconceptions || []).map((m) => `<div class="mis"><b>${esc(m.name)}</b><p>${esc(m.fix)}</p></div>`).join("");
  $("#rationale").textContent = r.rationale ? `Grader's note: ${r.rationale}` : (!r.resolved && r.verdict !== "correct" ? "Details unlock after your second attempt, so you can fix it yourself first." : "");
  $("#solution-wrap").hidden = !r.solution; $("#solution").textContent = r.solution || "";
  $("#solution-label").textContent = r.answered_question?.kind === "numeric" ? "Worked solution (calculator)" : "Model answer";
  if (["reveal", "note_next", "diag_next"].includes(r.action) && r.verdict !== "correct") $("#solution-wrap").open = true;
}
function renderShield(events) {
  const safety = events.filter((e) => e.kind === "safety");
  if (!safety.length) return;
  $("#shield").hidden = false;
  $("#shield-list").insertAdjacentHTML("afterbegin", safety.map((e) => `<li>${esc(e.summary)}</li>`).join(""));
}
const actorClass = (a) => (["Director", "Guard", "Calculator", "Interviewer", "Coach", "Planner"].includes(a) ? a : "spec");
function traceItem(e, compact) {
  const tok = e.kind === "llm" ? `<span class="tok">${fmt(e.input_tokens)} in (${fmt(e.cached_tokens)} cached) · ${fmt(e.output_tokens)} out · ${money(e.cost_usd, 5)}</span>` : `<span class="tok"></span>`;
  const detail = !compact && e.detail && Object.keys(e.detail).length ? `<details><summary>details</summary><pre>${esc(JSON.stringify(e.detail, null, 2))}</pre></details>` : "";
  return `<li><span class="actor ${actorClass(e.actor)}">${esc(e.actor)}</span><span>${esc(e.summary)}</span>${tok}${detail}</li>`;
}
function renderTurnTrace(events) { $("#turn-trace").innerHTML = events.map((e) => traceItem(e, true)).join("") || `<li class="muted">—</li>`; }
function updateMeter(u) {
  if (!u) return;
  const total = (u.input_tokens || 0) + (u.output_tokens || 0);
  $("#meter-cost").textContent = money(u.cost_usd); $("#meter-tokens").textContent = total.toLocaleString();
  $("#meter-fill").style.width = `${Math.min(100, (100 * total) / (S.session?.budget || 120000))}%`;
}

// ------------------------------------------------------------------ end of session -> skills update screen
$("#end-btn").addEventListener("click", () => { if (S.session && !S.busy) finishSession(); });
async function finishSession() {
  S.busy = true; stopMic(); window.speechSynthesis?.cancel();
  try {
    const r = await api(`/api/session/${S.session.id}/end`, {});
    S.lastReport = r; S.dash = await api("/api/dashboard");
    renderResults(r);
  } catch (e) { toast(e.message); } finally { S.busy = false; }
}
function renderResults(r) {
  const mode = r.session.mode;
  $("#res-kind").textContent = { diagnostic: "Placement complete", drill: "Drill complete", mock: "Mock interview complete", practice: "Practice complete" }[mode] || "Session complete";
  $("#res-title").textContent = mode === "diagnostic" ? `You're at ${S.dash.overall_label} overall` : "Your skills, updated";
  $("#res-sub").textContent = mode === "diagnostic" ? `Target: ${S.dash.target_label}. Your personal plan is ready.` : `${r.turns.filter((t) => t.verdict).length} answers graded this session.`;
  $("#res-levelups").innerHTML = mode === "diagnostic"
    ? Object.entries(r.placement || {}).map(([k, l], i) => `<div class="levelup c-${k}" style="animation-delay:${0.15 + i * 0.12}s;background:var(--c);border-color:transparent;color:var(--ci)">${esc(skillName(k, S.meta.skills[k]))}: placed at ${LEVEL_NAMES[l]}</div>`).join("")
    : (r.level_ups || []).map((u, i) => `<div class="levelup" style="animation-delay:${0.2 + i * 0.15}s">⬆ Level up! ${esc(skillName(u.skill, u.name))}: ${esc(u.from)} → ${esc(u.to)}</div>`).join("");
  const skills = Object.keys(S.meta.skills).filter((k) => k !== "industry" || (S.dash.intake.group && S.dash.intake.group !== "generalist"));
  $("#res-deltas").innerHTML = skills.map((k) => {
    const a = Math.round(100 * (r.mastery_start?.[k]?.p ?? 0.3)), b = Math.round(100 * (r.mastery_end?.[k]?.p ?? 0.3));
    const la = LEVEL_NAMES[r.levels_start?.[k] ?? 0], lb = LEVEL_NAMES[r.levels_end?.[k] ?? 0];
    const dl = b - a;
    return `<div class="delta-row c-${k}"><span><b>${esc(skillName(k, S.meta.skills[k]))}</b><br><span class="small muted">${la}${la !== lb ? ` → ${lb}` : ""}</span></span>
      <div class="bar"><div class="before" style="width:${a}%"></div><div class="after" data-w="${b}"></div></div>
      <span class="${dl > 0 ? "delta-up" : dl < 0 ? "delta-down" : "muted"}">${a}% → ${b}% ${dl > 0 ? "▲" : dl < 0 ? "▼" : ""}</span></div>`;
  }).join("");
  requestAnimationFrame(() => setTimeout(() => $$("#res-deltas .after").forEach((el) => (el.style.width = `${el.dataset.w}%`)), 80));
  const p = r.plan_progress;
  const next = p?.next;
  $("#res-next").innerHTML = `<div><b>${mode === "diagnostic" ? "Your plan is ready" : "Plan progress"}: ${p ? `${p.done}/${p.total} tasks (${p.pct}%)` : "—"}</b>
    <div class="small muted">${next ? `Next up: ${esc(next.title)}` : "You've finished every task in your plan."}</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="ghost" data-goto="plan">See my plan</button>
    ${next ? `<button class="primary" id="res-start-next">Start: ${esc(next.title)}</button>` : `<button class="primary" data-goto="dashboard">Dashboard</button>`}</div>`;
  if (next) $("#res-start-next").addEventListener("click", () => startTask(next));
  const d = r.debrief || {};
  $("#db-headline").textContent = d.headline || "";
  $("#db-strengths").innerHTML = (d.strengths || []).map((s) => `<li>${esc(s)}</li>`).join("") || `<li class="muted">—</li>`;
  $("#db-focus").innerHTML = (d.focus_areas || []).map((f) => `<div class="focus"><b>${esc(f.name || f.misconception_id)}</b> · ${esc(f.why_it_matters)}<br>${esc(f.drill)}</div>`).join("") || `<p class="muted small">No misconceptions this session.</p>`;
  const u = r.usage || {};
  $("#db-foot").textContent = `${((u.input_tokens || 0) + (u.output_tokens || 0)).toLocaleString()} tokens (${(u.cached_tokens || 0).toLocaleString()} cached) · ${money(u.cost_usd)} for this session`;
  resetSurvey(); show("results");
}

// ------------------------------------------------------------------ survey
$("#rating").innerHTML = Array.from({ length: 10 }, (_, i) => `<button type="button">${i + 1}</button>`).join("");
$$("#rating button").forEach((b) => b.addEventListener("click", () => { $$("#rating button").forEach((x) => x.classList.remove("sel")); b.classList.add("sel"); S.rating = Number(b.textContent); }));
function resetSurvey() { S.rating = null; $$("#rating button").forEach((x) => x.classList.remove("sel")); $("#survey").reset(); $("#survey-status").textContent = ""; $("#survey button[type=submit]").disabled = false; }
$("#survey").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { session_id: S.lastReport?.session?.id || null, rating: S.rating, vs_current: $("#vs-current").value || null,
    found_new: $("#found-new").value || null, time_to_find: $("#time-to-find").value || null,
    prep_today: $("#prep-today").value.trim() || null, quote: $("#quote").value.trim() || null, consent: $("#consent").checked };
  if (!body.rating && !body.quote && !body.vs_current) { $("#survey-status").textContent = "Pick a rating or write a line first."; return; }
  try { await api("/api/feedback", body); $("#survey-status").textContent = "Thanks! Saved."; $("#survey button[type=submit]").disabled = true; } catch (err) { toast(err.message); }
});

// ------------------------------------------------------------------ skills page
async function renderSkillsPage() {
  if (!S.dash) S.dash = await api("/api/dashboard");
  const d = S.dash;
  $("#skills-full").innerHTML = d.skills.filter((s) => s.key !== "industry" || (d.intake.group && d.intake.group !== "generalist")).map((s) => skillCard(s, true)).join("");
  $("#mis-list").innerHTML = d.misconceptions.length ? d.misconceptions.map((x) => {
    const ev = (x.evidence || []).slice(-2).reverse().map((e) => (e.quote ? `<q>${esc(e.quote)}</q>` : "")).join("");
    return `<div class="mis-item"><div class="top"><span class="pill ${x.active ? "tag-active" : "tag-cleared"}">${x.active ? "active" : "cleared"}</span>
      <b>${esc(x.name)}</b><span class="small muted">seen ${x.hits}×</span></div>${ev}<p>${esc(x.fix)}</p></div>`;
  }).join("") : `<p class="muted">No misconceptions yet.</p>`;
}
$("#skills-full").addEventListener("click", (e) => { const b = e.target.closest("[data-drill]"); if (b) startSession("drill", S.dash?.intake?.persona || "associate", b.dataset.drill); });

// ------------------------------------------------------------------ trace & club
async function renderTrace() {
  if (S.session) {
    const r = await api(`/api/session/${S.session.id}/events`);
    $("#trace").innerHTML = r.events.map((e) => traceItem(e, false)).join("");
    const u = r.usage, total = u.input_tokens + u.output_tokens, cp = u.input_tokens ? Math.round((100 * u.cached_tokens) / u.input_tokens) : 0;
    $("#kpis").innerHTML = `<div class="kpi"><b>${money(u.cost_usd)}</b><span>cost this session</span></div><div class="kpi"><b>${total.toLocaleString()}</b><span>tokens (${u.llm_calls} model calls)</span></div>
      <div class="kpi"><b>${cp}%</b><span>input served from cache</span></div><div class="kpi"><b>${u.output_tokens.toLocaleString()}</b><span>output tokens</span></div>`;
  } else { $("#trace").innerHTML = `<li class="muted">Start a session to see its trace.</li>`; $("#kpis").innerHTML = ""; }
  const c = await api("/api/costs");
  $("#agent-tbl").innerHTML = `<tr><th>Agent</th><th>Calls</th><th>Input</th><th>Cached</th><th>Output</th><th>Cost</th></tr>` +
    c.per_agent.map((a) => `<tr><td><span class="actor ${actorClass(a.actor)}">${esc(a.actor)}</span></td><td>${a.calls}</td><td>${fmt(a.input_tokens)}</td><td>${fmt(a.cached_tokens)}</td><td>${fmt(a.output_tokens)}</td><td>${money(a.cost_usd, 4)}</td></tr>`).join("") +
    `<tr><td><b>Per graded answer</b></td><td></td><td>${fmt(Math.round(c.per_answer.i))}</td><td>${fmt(Math.round(c.per_answer.cch))}</td><td>${fmt(Math.round(c.per_answer.o))}</td><td><b>${money(c.per_answer.usd, 5)}</b></td></tr>`;
}
async function renderClub() {
  const c = await api("/api/club"); const n = Math.max(c.members, 1);
  $("#club-mis").innerHTML = c.misconceptions.length ? `<p class="small muted" style="margin-top:0">${c.members} members · ${c.answers} graded answers</p>` +
    c.misconceptions.slice(0, 10).map((m) => { const pct = Math.round((100 * m.members) / n);
      return `<div class="club-row"><div>${esc(m.name)}<small>${esc(m.skill)} · ${m.hits} occurrences</small><div class="bar"><div style="width:${pct}%"></div></div></div><b>${pct}%</b></div>`; }).join("") : `<p class="muted">No data yet.</p>`;
  $("#club-skills").innerHTML = c.skills.map((s) => { const pct = Math.round(100 * s.avg_p);
    return `<div class="club-row c-${s.skill}"><div>${esc(s.name)}<div class="mini-bar"><div style="width:${pct}%;background:var(--ci)"></div></div></div><b>${pct}%</b></div>`; }).join("");
}

// ------------------------------------------------------------------ voice: interviewer speaks (browser TTS), candidate speaks (browser STT)
const VOICE = { associate: { rate: 1.03, pitch: 1.05 }, vp: { rate: 1.14, pitch: 0.95 }, director: { rate: 0.98, pitch: 0.9 }, md: { rate: 0.92, pitch: 0.85 } };
function pickVoice(persona) {
  const vs = (window.speechSynthesis?.getVoices() || []).filter((v) => v.lang?.startsWith("en"));
  if (!vs.length) return null;
  const idx = { associate: 0, vp: 1, director: 2, md: 3 }[persona] || 0;
  return vs[idx % vs.length];
}
function speak(text, persona, force = false) {
  if (!("speechSynthesis" in window) || (!S.tts && !force) || !text) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/\$/g, " dollars ").replace(/mm\b/g, " million"));
  const v = pickVoice(persona); if (v) u.voice = v;
  Object.assign(u, VOICE[persona] || {});
  u.onend = () => { if (S.handsfree && S.session && !S.busy && !MIC.on) startMic(); };
  window.speechSynthesis.speak(u);
}
$("#tts-toggle").addEventListener("change", (e) => { S.tts = e.target.checked; localStorage.setItem("tt_tts", S.tts ? "1" : "0"); if (!S.tts) window.speechSynthesis?.cancel(); });
$("#handsfree-toggle").addEventListener("change", (e) => {
  S.handsfree = e.target.checked; localStorage.setItem("tt_hf", S.handsfree ? "1" : "0");
  if (S.handsfree && !S.tts) { S.tts = true; $("#tts-toggle").checked = true; localStorage.setItem("tt_tts", "1"); }
  if (S.handsfree) toast("Hands-free on: the interviewer speaks, the mic opens, and saying \"submit\" sends your answer.");
});

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const MIC = { rec: null, on: false, base: "" };
function setupMic() {
  const b = $("#mic-btn");
  if (!SR) { b.disabled = true; b.title = "Voice input needs Chrome or Edge"; return; }
  b.addEventListener("click", () => (MIC.on ? stopMic() : startMic()));
}
function startMic() {
  if (!SR || MIC.on) return;
  window.speechSynthesis?.cancel();
  MIC.rec = new SR(); MIC.rec.lang = "en-US"; MIC.rec.continuous = true; MIC.rec.interimResults = true;
  MIC.base = $("#answer").value.trim() ? $("#answer").value.trim() + " " : "";
  MIC.rec.onresult = (e) => {
    let text = "";
    for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
    const said = (MIC.base + text).trim();
    if (S.handsfree && /\b(submit|send it|final answer)\.?$/i.test(said)) {
      $("#answer").value = said.replace(/\b(submit|send it|final answer)\.?$/i, "").trim();
      stopMic(); submitAnswer(); return;
    }
    $("#answer").value = said;
  };
  MIC.rec.onerror = (e) => { if (e.error === "no-speech") return; toast(e.error === "not-allowed" ? "Microphone access is blocked. Allow it from the address bar." : `Voice input stopped (${e.error}).`); stopMic(); };
  MIC.rec.onend = () => { if (MIC.on) { MIC.base = $("#answer").value.trim() + " "; try { MIC.rec.start(); } catch {} } };
  MIC.rec.start(); MIC.on = true;
  $("#mic-btn").classList.add("rec"); $("#mic-label").textContent = S.handsfree ? "Listening… say \"submit\"" : "Listening… tap to stop";
}
function stopMic() { MIC.on = false; if (MIC.rec) try { MIC.rec.stop(); } catch {} $("#mic-btn").classList.remove("rec"); $("#mic-label").textContent = "Speak"; }
setupMic();

init().catch((e) => toast(e.message));
