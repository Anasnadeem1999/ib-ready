// IB Ready front end: plain JavaScript, no build step, no external dependencies.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (x, dp = 4) => "$" + Number(x || 0).toFixed(dp);
const fmt = (x) => (x === null || x === undefined ? "—" : Number(x).toLocaleString(undefined, { maximumFractionDigits: 2 }));
const LEVEL_NAMES = ["Getting started", "Coffee-chat ready", "First-round ready", "Superday ready"];
const LEVEL_SHORT = ["Getting started", "Coffee chat", "First round", "Superday"];
const LEVEL_MEANING = [
  "You're learning the basics. Everyone starts here.",
  "You can handle the simple questions bankers ask in networking coffee chats.",
  "You can answer the standard technical questions in a first-round interview.",
  "You can handle the harder, multi-step questions in final-round Superdays.",
];
const OLD_LEVEL = { Foundations: 0, Basic: 1, Intermediate: 2, Advanced: 3 };
// Server text may still say Basic / Intermediate / Advanced: show the student-facing milestone names instead.
function mapLevels(text) {
  if (!text) return text;
  return String(text).replace(/\b(Foundations|Basic|Intermediate|Advanced)( level| drill)?\b/g, (m, w, suf) =>
    suf === " level" ? `${LEVEL_SHORT[OLD_LEVEL[w]].toLowerCase()} level` : suf === " drill" ? `${LEVEL_SHORT[OLD_LEVEL[w]]} drill` : LEVEL_NAMES[OLD_LEVEL[w]]);
}
function journey(level, { title = true } = {}) {
  const L = Math.max(0, Math.min(3, level || 0));
  const steps = LEVEL_SHORT.map((n, i) => {
    const cls = i < L ? "done" : i === L ? "here" : i === L + 1 ? "next" : "todo";
    const tag = i === L ? "You are here" : i === L + 1 ? "Next milestone" : "";
    return `<li class="${cls}"${i === L ? ' aria-current="step"' : ""}><span class="jdot" aria-hidden="true">${i < L ? "✓" : ""}</span><b>${esc(n)}</b>${tag ? `<small>${tag}</small>` : ""}</li>`;
  }).join("");
  const next = L < 3 ? `<p class="small mt-0"><b>Next milestone: ${esc(LEVEL_NAMES[L + 1])}.</b> ${esc(LEVEL_MEANING[L + 1])}</p>` : `<p class="small mt-0"><b>Top milestone reached.</b> Keep it fresh with mock interviews.</p>`;
  return `${title ? `<h2 class="section-title">Your journey ${tip("level")}</h2>` : ""}<ol class="journey">${steps}</ol>
    <p class="mt-0"><b>You are here: ${esc(LEVEL_NAMES[L])}.</b> ${esc(LEVEL_MEANING[L])}</p>${next}`;
}
const MODE_LABEL = { diagnostic: "Placement interview", drill: "Practice session", mock: "Mock interview", practice: "Topic practice" };
const MODE_TIP = { diagnostic: "placement interview", drill: "drill", mock: "mock interview", practice: "drill" };
const pick = (arr) => (Array.isArray(arr) && arr.length ? arr[Math.floor(Math.random() * arr.length)] : "");
const isMobile = () => window.matchMedia("(max-width: 900px)").matches;

// ------------------------------------------------------------------ dates (always the user's local calendar, never UTC)
function localISO(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const parseISO = (iso) => new Date(String(iso).slice(0, 10) + "T12:00:00");
const fmtDate = (iso, opts = { weekday: "short", month: "short", day: "numeric" }) => (iso ? parseISO(iso).toLocaleDateString("en-US", opts) : "");
const daysUntil = (iso) => (iso ? Math.round((parseISO(iso) - parseISO(localISO())) / 86400000) : null);

const S = {
  meta: null, content: {}, token: localStorage.getItem("tt_token"), profile: JSON.parse(localStorage.getItem("tt_profile") || "null"),
  dash: null, session: null, persona: "associate", group: "generalist", stage: "first_rounds", events: [],
  busy: false, qStart: null, timer: null, rating: null, lastReport: null, view: null, editing: false,
  tts: localStorage.getItem("tt_tts") === "1", handsfree: localStorage.getItem("tt_hf") === "1",
};

const VERDICT = {
  correct: ["Correct ✓", "Every graded number checks out and the reasoning holds."],
  correct_unexplained: ["Right answer, explain more", "The numbers are right. In an interview you'd be asked why."],
  incomplete: ["Almost there", "Some required points are missing."],
  incorrect: ["Not quite yet", "At least one number or key idea is off. See which below."],
  redirect: ["Let's get back to the question", "There was nothing to grade in that answer."],
};

// ------------------------------------------------------------------ content (web/content.json, with built-in fallbacks)
const FALLBACK = {
  primer: "**What are IB technical interviews?**\n\nInvestment banks advise companies on big money decisions: buying another company, selling one, or raising money from investors. Before hiring you as an analyst, bankers check that you understand the basics of how companies are measured and valued. That's the \"technical\" part of the interview.\n\nExpect four families of questions:\n- **Accounting**: how a change ripples through the three financial statements\n- **Valuation**: what a company is worth and why\n- **Deals**: mergers and leveraged buyouts\n- **You**: your story and why banking\n\nEarly conversations, such as coffee chats and first rounds, stick to the basics. Final rounds (\"Superdays\") go deeper. Nobody expects you to know everything. They want clear thinking, out loud, and honesty when you're unsure.",
  levels: null,
  misconception_explainer: "**What's a mistake pattern?** It's the specific wrong idea behind a wrong number, like \"forgot that interest is tax-deductible\". Fix the idea once and every question that uses it gets easier.",
  empty_states: {
    dashboard: "Let's find your starting point. A 15-minute placement interview shows where you already are and where to focus. There's no pass or fail, just a map.",
    plan: "It counts back from your interview date and fits the hours you have, so you only practice what moves the needle.",
    progress: "Your progress fills in as you answer questions. Each topic moves from Getting started to Superday ready, and the sub-skills that need work are where your next drills go.",
  },
  encouragement: {
    nudge: ["Small and steady is how this gets easy.", "One short session today beats a long one next week."],
    level_up: ["You've shown it twice in a row. It's yours."],
    keep_going: ["Hard sessions are where most of the learning happens. Your plan has already adjusted.",
      "A few questions today still counts. A short session tomorrow beats a long one next week."],
  },
};
const C = (k) => (S.content && S.content[k] != null ? S.content[k] : FALLBACK[k]);
function emptyCopy(k, sub) {
  const v = S.content?.empty_states?.[k];
  if (typeof v === "string" && !sub) return v;
  if (v && typeof v === "object") { const x = v[sub] || Object.values(v).find((y) => typeof y === "string" && y.length > 60); if (x) return x; }
  return FALLBACK.empty_states[k];
}
const lvlLabel = (x) => mapLevels(x || "Foundations");
function levelUpLine(skill, level) {
  const opts = (S.content?.encouragement?.level_up || []).filter((t) => t.includes("{skill}"));
  const t = pick(opts);
  return t ? t.replace(/\{skill\}/g, skill).replace(/\{level\}/g, level) : `Level up: ${skill} is now ${level}. You've shown it twice in a row. It's yours.`;
}
function misHTML(short) {
  const m = C("misconception_explainer");
  const body = typeof m === "string" ? m.replace(/^\*\*What's a (misconception|mistake pattern)\?\*\*\s*/i, "").replace(/A misconception is/, "A mistake pattern is") : "";
  return `${short ? "" : "<h3>What's a mistake pattern?</h3>"}${body ? `<p>${inline(body)}</p>` : rich(m)}`;
}
function levelsHTML(x) {
  const lv = x && typeof x === "object" && !Array.isArray(x) ? x : {};
  const rows = [lv.getting_started, lv.Basic, lv.Intermediate, lv.Advanced].map((v, i) => ({
    label: v?.label || LEVEL_NAMES[i], stage: v?.stage || "", text: v?.explanation || v?.meaning || LEVEL_MEANING[i] }));
  const how = typeof lv.how_you_level_up === "string" ? mapLevels(lv.how_you_level_up) : "You reach a milestone once you've shown it on at least two questions. Everyone starts at the beginning and moves up only when ready.";
  return `<h3>How milestones work</h3><p>${inline(mapLevels(lv.intro) || "Every topic moves through three milestones after Getting started, each named after the stage of recruiting you're ready for.")}</p>
    <ol class="journey static">${rows.map((r, i) => `<li class="${i ? "todo" : "here"}"><span class="jdot" aria-hidden="true"></span><b>${esc(LEVEL_SHORT[i])}</b></li>`).join("")}</ol>
    <ul>${rows.map((r) => `<li><b>${esc(r.label)}</b>${r.stage ? ` <span class="muted">(${esc(r.stage)})</span>` : ""}: ${inline(r.text)}</li>`).join("")}</ul><p>${inline(how)}</p>`;
}
const encourage = (k) => pick((S.content?.encouragement?.[k]?.length ? S.content.encouragement[k] : FALLBACK.encouragement[k]));

async function loadContent() {
  try {
    const r = await fetch("/static/content.json", { cache: "no-cache" });
    if (r.ok) S.content = await r.json();
  } catch { S.content = {}; }
  if (!S.content || typeof S.content !== "object") S.content = {};
  buildGlossary();
}

// tiny, safe markdown: escapes first, then **bold**, "- " bullets, "# " headings, blank-line paragraphs
function inline(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|\W)_(.+?)_(?=\W|$)/g, "$1<i>$2</i>"); }
function rich(x) {
  if (x == null || x === "") return "";
  if (typeof x === "string") {
    return x.trim().split(/\n\s*\n/).map((block) => {
      const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
      const out = []; let list = [];
      const flush = () => { if (list.length) { out.push(`<ul>${list.map((li) => `<li>${inline(li)}</li>`).join("")}</ul>`); list = []; } };
      lines.forEach((l) => {
        if (/^[-•*]\s+/.test(l)) list.push(l.replace(/^[-•*]\s+/, ""));
        else if (/^#{1,4}\s+/.test(l)) { flush(); out.push(`<h3>${inline(l.replace(/^#+\s+/, ""))}</h3>`); }
        else if (/^\*\*[^*]+\*\*$/.test(l) && lines.length > 1) { flush(); out.push(`<h3>${esc(l.slice(2, -2))}</h3>`); }
        else { flush(); out.push(`<p>${inline(l)}</p>`); }
      });
      flush(); return out.join("");
    }).join("");
  }
  if (Array.isArray(x)) {
    if (x.every((i) => typeof i === "string")) return `<ul>${x.map((i) => `<li>${inline(i)}</li>`).join("")}</ul>`;
    return `<ul>${x.map((o) => {
      if (typeof o !== "object" || !o) return `<li>${inline(String(o))}</li>`;
      const t = o.title || o.name || o.level || o.term || o.heading || "";
      const b = o.body || o.text || o.desc || o.description || o.definition || o.summary || o.when || "";
      return `<li>${t ? `<b>${esc(t)}</b>${b ? ": " : ""}` : ""}${typeof b === "string" ? inline(b) : rich(b)}</li>`;
    }).join("")}</ul>`;
  }
  if (typeof x === "object") {
    const t = x.title || x.heading || x.name;
    const b = x.body ?? x.text ?? x.content ?? x.items ?? x.levels ?? x.paragraphs;
    if (t || b) return `${t ? `<h3>${esc(t)}</h3>` : ""}${rich(b)}${x.footer || x.note ? rich(x.footer || x.note) : ""}`;
    return Object.entries(x).map(([k, v]) => `<p><b>${esc(k)}</b>: ${typeof v === "string" ? inline(v) : ""}</p>${typeof v === "string" ? "" : rich(v)}`).join("");
  }
  return esc(String(x));
}

// ------------------------------------------------------------------ glossary + "?" tooltips
const TIPS = {
  team: ["Which team?", "Banks are split into industry teams (coverage groups, such as Healthcare) and deal-type teams (product groups, such as M&A). If you don't know yet, pick \"Not sure yet\". You'll get general questions."],
  "coverage group": ["Coverage group", "An industry team (e.g. Healthcare). They advise companies in one sector."],
  "product group": ["Product group", "A deal-type team (e.g. M&A, Leveraged Finance). They specialise in one kind of transaction."],
  superday: ["Superday", "The final round: several back-to-back interviews in one day. Coffee chats and first rounds come before it and stick to the basics."],
  interviewer: ["Associate / VP / Director / MD", "Banker seniority, junior to senior. Associates focus on technical questions; Managing Directors focus on your story and fit. Start with Associate if you're unsure."],
  "placement interview": ["Placement interview", "A 15-minute check of your current level. It's not graded; it sets your starting point."],
  drill: ["Practice session", "A short (about 20 min) set of questions on one topic, pitched at your next milestone."],
  "mock interview": ["Mock interview", "A full practice interview across mixed topics, like the real thing."],
  confidence: ["Confidence", "How sure we are that you can answer this topic correctly, based on your recent answers."],
  "mistake pattern": ["Mistake pattern", "The specific wrong idea behind an answer (e.g. \"forgets the tax effect\"). Fixing the pattern fixes many questions."],
  "sub-skill": ["Sub-skill", "A smaller piece of a topic, like \"working capital\" inside Accounting."],
  "line item": ["Line item", "One number the interviewer expects in your answer, such as net income or cash."],
  level: ["Milestones", "Getting started → Coffee-chat ready (simple questions in networking chats) → First-round ready (standard technical questions) → Superday ready (harder final-round questions)."],
  "hands-free": ["Hands-free voice mode", "The interviewer reads each question aloud, then the microphone opens. Answer out loud and say \"submit\" to send. Works in Chrome and Edge."],
  "update plan": ["Update my plan", "Rebuilds the plan from your latest results. Finished tasks stay finished."],
  "plan status": ["Plan status", "Compares the tasks you've finished with the tasks scheduled up to today. Falling a little behind is normal; the plan adjusts."],
  accounting: ["Accounting", "How the income statement, balance sheet and cash flow statement link together."],
  ev: ["EV & valuation", "What a company is worth to all its investors, and how bankers compare companies."],
  dcf: ["DCF & WACC", "Valuing a company from its future cash flows, discounted at its cost of capital."],
  ma: ["M&A", "Mergers and acquisitions: one company buying another."],
  lbo: ["LBO", "Leveraged buyout: buying a company mostly with debt, as private equity firms do."],
  fit: ["Fit & behavioral", "\"Why banking?\", your story, strengths and weaknesses."],
  industry: ["Group specifics", "Questions particular to the team you're targeting, such as bank valuation for FIG or SaaS metrics for Tech."],
};
const GLOSS = { list: [], map: {} };
function buildGlossary() {
  const g = S.content?.glossary;
  const list = [];
  const add = (group, term, def) => { if (term && def) list.push({ group, term: String(term), def: typeof def === "string" ? def : (def.definition || def.def || def.text || "") }); };
  const defOf = (o) => o.definition || o.def || o.text || o.desc || o.description || o.meaning || "";
  const walk = (x, group) => {
    if (!x || typeof x !== "object") return;
    if (Array.isArray(x)) {
      x.forEach((o) => {
        if (!o || typeof o !== "object") return;
        if (o.term || o.name) add(o.group || o.category || group, o.term || o.name, defOf(o));
        else walk(o.terms || o.items || o, o.group || o.category || o.title || group);
      });
      return;
    }
    Object.entries(x).forEach(([k, v]) => {
      if (typeof v === "string") add(group, k, v);
      else if (v && !Array.isArray(v) && defOf(v)) add(group, k, defOf(v));
      else walk(v, k);
    });
  };
  walk(g, "");
  // de-duplicate (walk may add object-with-definition entries twice)
  const seen = new Set();
  GLOSS.list = list.filter((e) => e.def && !seen.has(e.term) && seen.add(e.term));
  GLOSS.map = {};
  GLOSS.list.forEach((e) => {
    const base = e.term.toLowerCase().replace(/\s*\(.*?\)\s*/g, " ").trim();
    const acr = (e.term.match(/\(([A-Za-z&]{2,6})\)/) || [])[1];
    [e.term.toLowerCase(), base, ...base.split(/\s*\/\s*/), acr && acr.toLowerCase()].forEach((k) => { if (k && !GLOSS.map[k]) GLOSS.map[k] = e; });
  });
}
function tipData(key) {
  const k = String(key).toLowerCase();
  const own = TIPS[k];
  const aliases = { "mistake pattern": "misconception", confidence: "mastery", sbc: "stock-based compensation" };
  const g = GLOSS.map[k] || (aliases[k] && GLOSS.map[aliases[k]]);
  if (own) return { label: own[0], def: own[1] };
  if (g) return { label: mapLevels(g.term), def: mapLevels(g.def) };
  return null;
}
function tip(key, label) {
  const d = tipData(key);
  if (!d) return "";
  return `<button type="button" class="tip" data-tip="${esc(key)}" aria-label="What is ${esc(label || d.label)}?" aria-expanded="false">?</button>`;
}
// Finance terms a newcomer may not know. In coach and plan prose the first use of each gets a "?" (QA D-10).
const JARGON = ["CAPM", "MOIC", "IRR", "D&A", "SBC", "WACC", "DCF", "EBITDA", "EBIT", "EV/EBITDA", "UFCF", "NOPAT", "LBO", "M&A", "EPS", "P/E",
  "treasury stock method", "paper LBO", "returns math", "terminal value", "enterprise value", "equity value", "diluted shares", "accretive", "dilutive",
  "goodwill", "working capital", "stock-based compensation", "mm"];
const reEsc = (t) => t.replace(/[.*+?^$()|[\]\\/{}]/g, "\\$&");
const JARGON_RE = new RegExp("(^|[^A-Za-z/&])(" + JARGON.slice().sort((a, b) => b.length - a.length)
  .map((t) => reEsc(t).replace(/&/g, "&amp;")).join("|") + ")(?![A-Za-z])", "gi");
// Takes text that is already HTML-escaped. Acronyms match case-sensitively; phrases match any case. "mm" only right after a number.
function linkTerms(html, seen = new Set()) {
  return html.replace(JARGON_RE, (m, pre, term) => {
    const raw = term.replace(/&amp;/g, "&");
    const canon = JARGON.find((t) => t.toLowerCase() === raw.toLowerCase());
    if (!canon) return m;
    if (/^[A-Z&/]+$/.test(canon) && raw !== canon) return m;
    if (canon === "mm" && !/\d$/.test(pre)) return m;
    const key = canon.toLowerCase();
    if (seen.has(key) || !tipData(key)) return m;
    seen.add(key);
    return `${pre}${term}${tip(key, canon)}`;
  });
}
// Coach prose: show milestone names, avoid internal words, explain jargon.
const plainWords = (t) => mapLevels(t || "").replace(/\bdiagnostics?\b/gi, "practice").replace(/\bpractise\b/g, "practice").replace(/\bmastery\b/g, "confidence");
const coachHTML = (t, seen) => linkTerms(esc(plainWords(t)), seen);
function hydrateTips(root = document) { $$("[data-tipkey]", root).forEach((el) => { el.outerHTML = tip(el.dataset.tipkey); }); }
const POP = { el: null, btn: null, pinned: false };
function openTip(btn, pinned) {
  const d = tipData(btn.dataset.tip); if (!d) return;
  if (POP.btn && POP.btn !== btn) POP.btn.setAttribute("aria-expanded", "false");
  const p = $("#popover"); p.innerHTML = `<b>${esc(d.label)}</b>${esc(d.def)}`; p.hidden = false;
  POP.btn = btn; POP.pinned = pinned; btn.setAttribute("aria-expanded", "true");
  const id = "popover"; btn.setAttribute("aria-describedby", id);
  const r = btn.getBoundingClientRect(), pr = p.getBoundingClientRect();
  let left = Math.min(Math.max(8, r.left + r.width / 2 - pr.width / 2), window.innerWidth - pr.width - 8);
  let top = r.bottom + 8;
  if (top + pr.height > window.innerHeight - 8) top = r.top - pr.height - 8;
  p.style.left = `${left}px`; p.style.top = `${Math.max(8, top)}px`;
}
function closeTip() { if (POP.btn) { POP.btn.setAttribute("aria-expanded", "false"); POP.btn.removeAttribute("aria-describedby"); } POP.btn = null; POP.pinned = false; $("#popover").hidden = true; }
document.addEventListener("click", (e) => {
  const b = e.target.closest(".tip");
  if (b) { e.preventDefault(); e.stopPropagation(); if (POP.btn === b && POP.pinned) closeTip(); else openTip(b, true); return; }
  if (!e.target.closest("#popover")) closeTip();
}, true);
document.addEventListener("mouseover", (e) => { const b = e.target.closest(".tip"); if (b && !POP.pinned) openTip(b, false); });
document.addEventListener("mouseout", (e) => { const b = e.target.closest(".tip"); if (b && POP.btn === b && !POP.pinned) closeTip(); });
document.addEventListener("focusin", (e) => { const b = e.target.closest?.(".tip"); if (b) openTip(b, false); else if (POP.btn && !POP.pinned && !b) closeTip(); });
window.addEventListener("scroll", () => { if (POP.btn) closeTip(); }, true);

// ------------------------------------------------------------------ api
const OFFLINE_MSG = "We can't reach IB Ready right now. Check your connection and try again. Nothing you've done is lost.";
async function api(path, body, { authRedirect = true } = {}) {
  const headers = { "Content-Type": "application/json", "X-TZ-Offset": String(new Date().getTimezoneOffset()) };
  if (S.token) headers["X-Auth-Token"] = S.token;
  let r;
  try { r = await fetch(path, body === undefined ? { headers } : { method: "POST", headers, body: JSON.stringify(body) }); }
  catch { const e = new Error(OFFLINE_MSG); e.offline = true; throw e; }  // the browser's "Failed to fetch" means a network problem
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && authRedirect && S.token) { signOut(); const e = new Error("Please sign in again."); e.status = 401; throw e; }
  if (!r.ok) {
    let msg = data.error || data.detail || `Request failed (${r.status})`;
    if (Array.isArray(msg)) msg = msg.map((m) => m.msg || m).join("; ");
    const e = new Error(msg); e.status = r.status; throw e;
  }
  return data;
}
function toast(msg, kind = "info") {
  const t = $("#toast"); $("#toast-msg").textContent = msg; t.hidden = false;
  t.className = `toast toast--${kind}`;
  t.setAttribute("role", kind === "error" ? "alert" : "status");
  clearTimeout(t._h); t._h = setTimeout(() => (t.hidden = true), 6000);
}
$("#toast-x").addEventListener("click", () => ($("#toast").hidden = true));

// ------------------------------------------------------------------ routing (hash URLs + history, so Back works)
const ROUTES = { home: "#home", plan: "#plan", practice: "#practice", progress: "#progress", how: "#how-it-works", results: "#results", intake: "#goals", welcome: "#welcome" };
function parseHash(h = location.hash) {
  const [head, sec] = h.replace(/^#/, "").split("/");
  const view = Object.keys(ROUTES).find((k) => ROUTES[k] === "#" + head) || null;
  return { view, sec: sec || null };
}
function go(view, { sec = null, replace = false } = {}) {
  const h = ROUTES[view] + (sec ? "/" + sec : "");
  if (location.hash !== h) history[replace ? "replaceState" : "pushState"]({ view, sec }, "", h);
  render(view, sec);
}
window.addEventListener("hashchange", () => { const r = parseHash(); render(r.view || (S.token ? "home" : "welcome"), r.sec); });

function allowed(view) {
  if (view === "how") return view;
  if (!S.token) return "welcome";
  if (S.dash?.needs_intake) return "intake";
  if (view === "welcome") return "home";
  if (view === "results" && !S.lastReport) return "home";
  if (!view) return "home";
  return view;
}
function render(view, sec) {
  const v0 = view;
  view = allowed(view);
  if (view !== v0) history.replaceState({ view }, "", ROUTES[view]);
  closeTip(); closeMenu(); hideCoach();
  const inInterview = view === "practice" && !!S.session;
  const section = inInterview ? "interview" : view;
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${section}`));
  const tabView = { results: null, intake: null, how: null }[view] === null ? null : view;
  $$(".tab, .btab").forEach((t) => (t.dataset.view === tabView ? t.setAttribute("aria-current", "page") : t.removeAttribute("aria-current")));
  view === "how" ? $("#how-link").setAttribute("aria-current", "page") : $("#how-link").removeAttribute("aria-current");
  document.body.classList.toggle("in-session", inInterview);
  if (!inInterview) closeSheet();
  const prev = S.view; S.view = view;
  if (view === "home") renderHome();
  if (view === "plan") renderPlan();
  if (view === "practice") (inInterview ? afterShowInterview() : renderLauncher());
  if (view === "progress") renderProgress();
  if (view === "how") renderHow(sec);
  if (view === "intake") fillIntake();
  // the interview is sized to the viewport: always show it from the top, so the session bar is never under the header (QA D-04)
  if (!(view === "how" && sec)) window.scrollTo({ top: 0 });
  if (prev !== view) { const h = $(`#view-${section} h1`); if (h && !inInterview) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); } }
}
$$(".tab, .btab").forEach((t) => t.addEventListener("click", () => go(t.dataset.view)));
$("#brand-link").addEventListener("click", (e) => { e.preventDefault(); go(S.token ? "home" : "welcome"); });

// ------------------------------------------------------------------ profile menu
function closeMenu() { $("#profile-menu").hidden = true; $("#profile-chip").setAttribute("aria-expanded", "false"); }
$("#profile-chip").addEventListener("click", (e) => {
  e.stopPropagation(); const m = $("#profile-menu"); m.hidden = !m.hidden;
  $("#profile-chip").setAttribute("aria-expanded", String(!m.hidden)); if (!m.hidden) m.querySelector("button").focus();
});
document.addEventListener("click", (e) => { if (!e.target.closest("#profile-wrap")) closeMenu(); });
$("#profile-menu").addEventListener("click", (e) => {
  const b = e.target.closest("[data-menu]"); if (!b) return; closeMenu();
  if (b.dataset.menu === "goals") openIntake(true);
  if (b.dataset.menu === "how") go("how");
  if (b.dataset.menu === "signout" && confirm("Sign out? Your progress is saved.")) signOut();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("#popover").hidden) { const b = POP.btn; closeTip(); b?.focus(); return; }
  if (!$("#profile-menu").hidden) { closeMenu(); $("#profile-chip").focus(); return; }
  if (!$("#coach-mark").hidden) { endTour(); return; }
  if ($("#side-col").classList.contains("open")) { closeSheet(); return; }
  if (!$("#sb-tools").hidden) closeVoiceMenu();
});

function signedInUI(on) {
  const ready = on && S.dash && !S.dash.needs_intake;
  $("#tabs").hidden = !ready; $("#bottom-tabs").hidden = !ready;
  document.body.classList.toggle("signed-in", !!ready);
  $("#profile-wrap").hidden = !on;
  if (on) { $("#avatar-name").textContent = S.profile.name; $("#avatar-initial").textContent = (S.profile.name[0] || "?").toUpperCase(); }
}
function signOut() {
  if (S.token) fetch("/api/signout", { method: "POST", headers: { "X-Auth-Token": S.token } }).catch(() => {});
  S.token = null; S.profile = null; S.session = null; S.dash = null; S.lastReport = null;
  localStorage.removeItem("tt_token"); localStorage.removeItem("tt_profile");
  stopTimer(); stopMic(); window.speechSynthesis?.cancel(); signedInUI(false); go("welcome", { replace: true });
}

// ------------------------------------------------------------------ boot
async function init() {
  const [meta] = await Promise.all([api("/api/meta"), loadContent()]);
  S.meta = meta;
  const name = S.meta.app_name || "IB Ready";
  $("#brand-name").textContent = name;
  document.title = `${name} · ${S.meta.tagline || "Investment banking interview practice"}`;
  $("#key-warning").hidden = S.meta.key_present !== false;
  const max = S.meta.limits?.answer_chars; if (max) $("#answer").maxLength = max;
  buildIntakeOptions();
  hydrateTips();
  $("#tts-toggle").checked = S.tts; $("#handsfree-toggle").checked = S.handsfree;
  if (S.token) { try { S.profile = await api("/api/me"); } catch { S.token = null; localStorage.removeItem("tt_token"); } }
  const r = parseHash();
  if (!S.token) { signedInUI(false); go(r.view === "how" ? "how" : "welcome", { sec: r.sec, replace: true }); return; }
  await afterSignIn(r.view, r.sec);
}
async function afterSignIn(view, sec) {
  S.dash = await api("/api/dashboard");
  signedInUI(true);
  await checkActive();
  if (S.dash.needs_intake) { openIntake(false, true); return; }
  go(view && view !== "welcome" && view !== "intake" ? view : "home", { sec, replace: true });
}
async function checkActive() {
  try {
    const r = await api("/api/session/active");
    const s = r && r.id ? r : r?.session && r.session.id ? r.session : null;
    if (s && !s.ended && s.question) { if (!S.session || S.session.id !== s.id) { S.session = s; S.needsChatRebuild = true; } }
    else if (!s && S.session && !S.busy) S.session = null;
  } catch { /* endpoint not available yet: keep whatever we have */ }
}

$("#signin").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = $("#signin-error"); err.hidden = true;
  const name = $("#name").value.trim(), pw = $("#password").value;
  if (name.length < 2) { err.textContent = "Pick a username of at least 2 characters."; err.hidden = false; $("#name").focus(); return; }
  if (pw.length < 6) { err.textContent = "Use at least 6 characters."; err.hidden = false; $("#password").focus(); return; }
  const btn = $("#signin-btn"); btn.disabled = true; btn.textContent = "Signing in…";
  try {
    const r = await api("/api/signin", { name, password: pw }, { authRedirect: false });
    S.token = r.token; S.profile = r.profile;
    localStorage.setItem("tt_token", r.token); localStorage.setItem("tt_profile", JSON.stringify(r.profile));
    $("#password").value = "";
    await afterSignIn(null);
  } catch (ex) {
    err.textContent = /password|taken|match/i.test(ex.message) && !/locked|at least/i.test(ex.message)
      ? "That username and password don't match. Check your password, or pick a different username to start fresh." : ex.message;
    err.hidden = false;
  } finally { btn.disabled = false; btn.textContent = "Continue"; }
});

// ------------------------------------------------------------------ intake
function optButton(v, label, sub, sel) {
  return `<button type="button" class="opt" aria-pressed="${sel ? "true" : "false"}" data-v="${esc(v)}"><b>${esc(label)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</button>`;
}
function selectOpt(scope, v) { $$(`${scope} .opt`).forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v))); }
function wireChoice(scope, key) {
  $(scope.split(",")[0].trim()).closest("fieldset, .card").addEventListener("click", (e) => {
    const b = e.target.closest(".opt"); if (!b || !b.closest(scope.split(",").map((s) => s.trim()).join(","))) return;
    S[key] = b.dataset.v; selectOpt(scope, b.dataset.v);
  });
}
function buildIntakeOptions() {
  const cov = S.meta.groups.filter((g) => g.kind === "coverage"), prod = S.meta.groups.filter((g) => g.kind === "product" && g.id !== "generalist");
  $("#groups-default").innerHTML = optButton("generalist", "Not sure yet / Generalist", "General questions only", true);
  $("#groups-coverage").innerHTML = cov.map((g) => optButton(g.id, g.name)).join("");
  $("#groups-product").innerHTML = prod.map((g) => optButton(g.id, g.name)).join("");
  wireChoice("#groups-default, #groups-coverage, #groups-product", "group");
  const stageSub = { networking: "No interviews scheduled yet", first_rounds: "Phone or video screens", superdays: "Final-round, back-to-back interviews", offer: "Staying sharp before you start" };
  const stageName = { networking: "Networking / coffee chats", first_rounds: "First-round interviews", superdays: "Superdays", offer: "Have an offer" };
  $("#stages").innerHTML = Object.entries(S.meta.stages).map(([k, v]) => optButton(k, stageName[k] || v, stageSub[k], k === S.stage)).join("");
  wireChoice("#stages", "stage");
  selectOpt("#persona-choice", S.persona);
  wireChoice("#persona-choice", "persona");
  $("#hours").addEventListener("input", () => ($("#hours-val").textContent = `${$("#hours").value} hours / week`));
  const d = new Date(); d.setDate(d.getDate() + 21); $("#interview-date").value = localISO(d);
  $("#interview-date").min = localISO();
  $("#interview-date").addEventListener("input", updateDaysAway); updateDaysAway();
}
function updateDaysAway() {
  const n = daysUntil($("#interview-date").value);
  $("#days-away").textContent = n == null || isNaN(n) ? "" : n < 0 ? "in the past" : n === 0 ? "today" : n === 1 ? "tomorrow" : `${n} days away`;
}
function openIntake(editing, replace = false) { S.editing = editing; go("intake", { replace }); }
function fillIntake() {
  const i = S.dash?.intake || {};
  if (i.group) S.group = i.group; selectOpt("#groups-default, #groups-coverage, #groups-product", S.group);
  if (i.stage) S.stage = i.stage; selectOpt("#stages", S.stage);
  if (i.persona) S.persona = i.persona; selectOpt("#persona-choice", S.persona);
  if (i.interview_date) $("#interview-date").value = i.interview_date;
  updateDaysAway();
  if (i.hours_per_week) { $("#hours").value = i.hours_per_week; $("#hours-val").textContent = `${i.hours_per_week} hours / week`; }
  const placed = S.dash?.diagnostic_done;
  $("#intake-btn").textContent = placed ? "Save and update my plan" : "Start my 15-minute placement interview";
  $("#intake-help").hidden = !!placed;
  $("#intake-cancel").hidden = !S.dash || S.dash.needs_intake;
  $("#intake-h1").textContent = S.dash?.needs_intake ? "Tell us about your interviews" : "Edit my goals";
}
$("#intake-cancel").addEventListener("click", () => history.length > 1 ? history.back() : go("home"));
$("#intake").addEventListener("submit", async (e) => {
  e.preventDefault();
  const date = $("#interview-date").value;
  if (date && daysUntil(date) < 0) { toast("That date is in the past. Pick your next interview date.", "error"); $("#interview-date").focus(); return; }
  const btn = $("#intake-btn"); btn.disabled = true;
  try {
    await api("/api/intake", { group: S.group || "generalist", stage: S.stage, interview_date: date || null,
      hours_per_week: Number($("#hours").value), persona: S.persona });
    if (S.dash?.diagnostic_done) {
      await api("/api/plan/rebuild", {}); S.dash = await api("/api/dashboard"); signedInUI(true);
      toast("Plan updated with your new goals.", "success"); go("plan");
    } else {
      S.dash = await api("/api/dashboard"); signedInUI(true);
      await startSession("diagnostic", S.persona);
    }
  } catch (err) { toast(err.message, "error"); } finally { btn.disabled = false; }
});

// ------------------------------------------------------------------ shared bits
function showIndustry() { const g = S.dash?.intake?.group; return !!g && g !== "generalist"; }
function skillName(key, name) {
  if (key === "industry") { const g = S.dash?.group_name?.split(" (")[0]; return g && showIndustry() ? `${g} specifics` : "Group specifics"; }
  return name || S.meta?.skills?.[key] || key;
}
function visibleSkills(list) { return list.filter((s) => (s.key || s.skill) !== "industry" || showIndustry()); }
function levelMeter(level, p, { ink = null, label = "" } = {}) {
  // 3 segments; earned levels full, the next one partly filled by confidence
  const segs = [1, 2, 3].map((l) => {
    const w = l <= level ? 100 : l === level + 1 && p != null ? Math.round(Math.max(0, Math.min(1, p)) * 100) : 0;
    return `<span><i style="width:${w}%"></i></span>`;
  }).join("");
  return `<div class="level-meter" role="img" aria-label="${esc(label || LEVEL_NAMES[level] || "")}"${ink ? ` style="--ci:${ink}"` : ""}>${segs}</div>`;
}
function taskTitle(t) {
  if (!t) return "";
  if (t.type === "mock") return t.final ? "Final mock interview" : "Mock interview";
  return `${skillName(t.skill)} practice`;
}
function taskSub(t) {
  if (!t) return "";
  if (t.type === "mock") return `Mixed questions · about ${t.minutes} min`;
  const sub = t.subskill && S.meta?.subskills?.[t.subskill]?.name;
  return `${sub ? sub + " · " : ""}${LEVEL_SHORT[t.level] ? LEVEL_SHORT[t.level].toLowerCase() + " level · " : ""}about ${t.minutes} min`;
}
function taskRow(t, withBtn) {
  return `<li class="task-row ${t.done ? "done" : ""}"><span class="tick" aria-hidden="true">${t.done ? "✓" : ""}</span>
    <div><div class="ttl">${esc(taskTitle(t))}${t.done ? '<span class="sr-only"> (done)</span>' : ""}</div><div class="meta">${esc(taskSub(t))}</div></div>
    ${withBtn && !t.done ? `<button class="secondary small-btn" data-task="${t.id}" aria-label="Start ${esc(taskTitle(t))}">Start</button>` : "<span></span>"}</li>`;
}
function persona() { return S.dash?.intake?.persona || "associate"; }
function startTask(t) {
  if (!t) return;
  if (t.type === "mock") return startSession("mock", t.final ? "md" : persona(), null, null, t.id);
  return startSession("drill", persona(), t.skill || null, t.level || null, t.id);
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-task]");
  if (b && S.dash?.plan) { e.preventDefault(); startTask(S.dash.plan.tasks.find((t) => String(t.id) === b.dataset.task)); }
  const g = e.target.closest("[data-go]"); if (g) { e.preventDefault(); go(g.dataset.go, { sec: g.dataset.sec || null }); }
  const p = e.target.closest("[data-start-placement]"); if (p) { e.preventDefault(); startSession("diagnostic", persona()); }
  const r = e.target.closest("[data-resume]"); if (r) { e.preventDefault(); go("practice"); }
  const d = e.target.closest("[data-drill]"); if (d) { e.preventDefault(); startSession("practice", persona(), d.dataset.drill); }
});
async function refreshDash() { try { S.dash = await api("/api/dashboard"); } catch (e) { if (e.status !== 401) toast(e.message, "error"); } return S.dash; }
function greeting() { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; }
function emptyState(title, body, btnHTML) { return `<div class="card empty-state"><h2>${esc(title)}</h2><p>${inline(body)}</p>${btnHTML || ""}</div>`; }
function resumeBanner() {
  if (!S.session) return "";
  return `<span>You have an unfinished <b>${esc((MODE_LABEL[S.session.mode] || "session").toLowerCase())}</b>. Pick up where you left off.</span><button class="primary" data-resume>Resume session</button>`;
}

// ------------------------------------------------------------------ home
async function renderHome() {
  const d = await refreshDash(); if (!d || S.view !== "home") return;
  const first = (S.profile?.name || "").split(" ")[0];
  $("#home-h1").textContent = `${greeting()}, ${first}`;
  const n = daysUntil(d.intake?.interview_date);
  $("#home-sub").textContent = d.intake?.interview_date && n != null && n >= 0
    ? `Your interview is ${n === 0 ? "today" : n === 1 ? "tomorrow" : `in ${n} days (${fmtDate(d.intake.interview_date)})`}.` : "";
  const pid = S.profile?.id || S.profile?.name;
  const panelDone = localStorage.getItem(`ibr_firstrun:${pid}`) === "1";
  const fr = $("#firstrun");
  if (!d.diagnostic_done && !panelDone && !S.session) {
    fr.hidden = false; $("#home-main").hidden = true;
    fr.innerHTML = `<div class="card card--hero firstrun"><h2>Welcome, ${esc(first)}. Here's how this works.</h2>
      <p class="mt-0 muted">No finance background needed. ${inline(emptyCopy("dashboard", "not_placed"))}</p>
      <ol class="fr-steps"><li><b>Find your starting point ${tip("placement interview")}</b><span>A 15-minute placement interview. It's not graded.</span></li>
        <li><b>Get your plan</b><span>A short practice each day until your interview.</span></li>
        <li><b>Practice and improve</b><span>Every session shows what you got right and what to fix.</span></li></ol>
      <div class="row-gap-2"><button class="primary big" data-start-placement>Start</button><button class="textlink" id="fr-notnow">Not now</button></div></div>`;
    $("#fr-notnow").addEventListener("click", () => { localStorage.setItem(`ibr_firstrun:${pid}`, "1"); renderHome(); });
    return;
  }
  fr.hidden = true; $("#home-main").hidden = false;
  const p = d.progress;
  // ONE "Up next" card with ONE button
  const up = $("#upnext");
  let title, subline, btn, extra = "";
  if (S.session) {
    title = esc(`Continue your ${(MODE_LABEL[S.session.mode] || "session").toLowerCase()}`);
    subline = "You stopped partway through. Pick up where you left off.";
    btn = `<button class="primary big" data-resume>Continue</button>`;
  } else if (!d.diagnostic_done) {
    title = `Placement interview ${tip("placement interview")}`;
    subline = "15 minutes to find your starting point in each topic. It's a check, not a test.";
    btn = `<button class="primary big" data-start-placement>Start</button>`;
  } else if (p?.next) {
    const later = (p.today || []).filter((t) => !t.done && t.id !== p.next.id);
    title = `${esc(taskTitle(p.next))} ${p.next.type === "mock" ? tip("mock interview") : tip("drill")}`;
    subline = esc(taskSub(p.next));
    btn = `<button class="primary big" data-task="${p.next.id}">Start</button>`;
    extra = later.length ? `Later today: ${later.map((t) => esc(taskTitle(t))).join(", ")}.` : "That's everything planned for today.";
  } else {
    title = "You've finished your plan";
    subline = "A full mock interview keeps you sharp.";
    btn = `<button class="primary big" id="up-mock">Start</button>`;
  }
  up.innerHTML = `<div class="upnext"><div><span class="eyebrow">Up next</span><h2>${title}</h2>
    <div class="sub">${subline}</div>${extra ? `<div class="then">${extra}</div>` : ""}</div>
    <div class="upnext-actions">${btn}${d.diagnostic_done && !S.session ? `<a class="textlink" href="#plan">See my plan</a>` : ""}</div></div>`;
  $("#up-mock")?.addEventListener("click", () => startSession("mock", persona()));
  const facts = [];
  if (p) facts.push(`${p.done} of ${p.total} plan tasks done`);
  if (d.streak) facts.push(`${d.streak}-day streak`);
  if (d.answered) facts.push(`${d.answered} answers so far`);
  $("#home-journey").innerHTML = journey(d.diagnostic_done ? d.overall_level : 0) + (facts.length ? `<p class="small muted mt-0">${facts.join(" · ")}</p>` : "");
  $("#home-skills").innerHTML = visibleSkills(d.skills).map((s) => {
    const lv = LEVEL_SHORT[s.level] || LEVEL_SHORT[0];
    return `<li class="c-${s.key}"><span class="nm"><span class="dotc" aria-hidden="true"></span>${esc(skillName(s.key, s.name))} ${tip(s.key)}</span>
      ${levelMeter(s.level, s.n ? s.p : null, { label: LEVEL_NAMES[s.level] || LEVEL_NAMES[0] })}<span class="lv">${esc(lv)}${s.level >= 3 ? " ✓" : ""}</span></li>`;
  }).join("");
  if (d.diagnostic_done && !S.session) maybeTour();
}

// ------------------------------------------------------------------ first-run coach marks (after placement)
const TOUR = { steps: [], i: 0, el: null };
function visibleEl(sels) { return sels.map((s) => $(s)).find((el) => el && el.offsetParent !== null && el.getClientRects().length); }
function maybeTour() {
  const key = `ibr_tour_done:${S.profile?.id || S.profile?.name}`;
  if (localStorage.getItem(key) === "1" || TOUR.active) return;
  TOUR.key = key;
  const planDate = S.dash?.intake?.interview_date ? fmtDate(S.dash.intake.interview_date) : "your interview";
  TOUR.steps = [
    { sel: ["#upnext"], text: "This is always your next step. Just press Start." },
    { sel: [".tab[data-view=plan]", ".btab[data-view=plan]"], text: `Your day-by-day schedule until ${planDate}.` },
    { sel: [".tab[data-view=progress]", ".btab[data-view=progress]"], text: "See where each topic stands and the mistakes you keep repeating." },
  ];
  TOUR.i = 0; TOUR.active = true; setTimeout(showStep, 350);
}
function showStep() {
  if (!TOUR.active || S.view !== "home") return hideCoach();
  const step = TOUR.steps[TOUR.i]; const el = visibleEl(step.sel);
  if (!el) { TOUR.i++; return TOUR.i < TOUR.steps.length ? showStep() : endTour(); }
  $$(".cm-highlight").forEach((x) => x.classList.remove("cm-highlight")); el.classList.add("cm-highlight");
  if (el.id === "upnext") el.scrollIntoView({ block: "nearest" });
  const cm = $("#coach-mark"); $("#cm-text").textContent = step.text; $("#cm-count").textContent = `${TOUR.i + 1} of ${TOUR.steps.length}`;
  $("#cm-next").textContent = TOUR.i === TOUR.steps.length - 1 ? "Done" : "Next"; cm.hidden = false;
  const r = el.getBoundingClientRect(), cr = cm.getBoundingClientRect(), arrow = $(".cm-arrow", cm);
  const below = r.bottom + cr.height + 16 < window.innerHeight;
  const top = below ? r.bottom + 12 : r.top - cr.height - 12;
  const left = Math.min(Math.max(12, r.left + Math.min(r.width / 2, 160) - 30), window.innerWidth - cr.width - 12);
  cm.style.top = `${Math.max(8, top)}px`; cm.style.left = `${left}px`;
  const ax = Math.min(Math.max(14, r.left + Math.min(r.width / 2, 160) - left - 7), cr.width - 28);
  Object.assign(arrow.style, below ? { top: "-7px", bottom: "", left: `${ax}px` } : { bottom: "-7px", top: "", left: `${ax}px` });
  cm.focus();
}
function hideCoach() { $("#coach-mark").hidden = true; $$(".cm-highlight").forEach((x) => x.classList.remove("cm-highlight")); }
function endTour() { TOUR.active = false; if (TOUR.key) localStorage.setItem(TOUR.key, "1"); hideCoach(); }
$("#cm-next").addEventListener("click", () => { TOUR.i++; TOUR.i < TOUR.steps.length ? showStep() : endTour(); });
$("#cm-skip").addEventListener("click", endTour);
window.addEventListener("resize", () => { if (TOUR.active && !$("#coach-mark").hidden) showStep(); });

// ------------------------------------------------------------------ plan
function weekLabel(iso, todayISO) {
  const monday = (x) => { const d = parseISO(x); const k = (d.getDay() + 6) % 7; d.setDate(d.getDate() - k); return d; };
  const diff = Math.round((monday(iso) - monday(todayISO)) / (7 * 86400000));
  return diff === 0 ? "This week" : diff === 1 ? "Next week" : `Week of ${monday(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
}
async function renderPlan() {
  const d = await refreshDash(); if (!d || S.view !== "plan") return;
  const plan = d.plan;
  $("#plan-body-wrap").hidden = !plan; $("#plan-actions").hidden = !plan; $("#plan-empty").hidden = !!plan;
  if (!plan) {
    $("#plan-h1").textContent = "Your plan"; $("#plan-lead").textContent = "";
    $("#plan-empty").innerHTML = emptyState("Your plan appears after your placement interview.", emptyCopy("plan", "no_plan") + " The placement interview takes about 15 minutes.",
      `<button class="primary big" data-start-placement>Start placement interview</button>`);
    return;
  }
  const todayISO = d.today || localISO();
  $("#plan-h1").textContent = d.overall_level >= 3 ? "Your plan: stay Superday ready" : `Your plan to ${LEVEL_NAMES[Math.min(3, (d.overall_level || 0) + 1)]}`;
  $("#plan-lead").textContent = `${plan.days_left} days · ${plan.practice_days ? `${plan.practice_days} practice days · ` : ""}about ${plan.minutes_per_practice_day} min a practice day · 1 rest day a week`;
  // Today
  const todays = plan.tasks.filter((t) => t.date === todayISO);
  const next = plan.tasks.find((t) => !t.done);
  $("#plan-today").innerHTML = `<h2 class="section-title">Today · ${esc(fmtDate(todayISO))}</h2>` + (todays.length
    ? `<ul class="task-list">${todays.map((t) => taskRow(t, next && t.id === next.id)).join("")}</ul>`
    : next ? `<p class="mt-0">Nothing scheduled today. Want to get ahead?</p><ul class="task-list">${taskRow(next, true)}</ul>` : `<p class="mt-0">Every task is done. Nice work.</p>`);
  // Summary
  const sm = plan.summary || {};
  const until = daysUntil(d.intake?.interview_date);
  const flags = [];
  if (plan.final_prep) flags.push("Your interview is very soon, so this is a short final-prep plan: a light warm-up, then rest. You've done the work.");
  if (plan.interview_passed || d.interview_status === "past" || (until != null && until < 0)) flags.push(`Your interview date has passed. We hope it went well! <button class="textlink" data-go="intake">Set a new date</button> and we'll rebuild the plan around it.`);
  else if (plan.horizon_capped || (plan.horizon_capped === undefined && until != null && until > plan.days_left + 1)) flags.push(`Plans cover up to ${plan.days_left} days at a time. We'll extend it as you get closer to ${esc(fmtDate(d.intake.interview_date))}.`);
  if (plan.compressed) flags.push("Time is tight, so the plan keeps the highest-priority work: your weakest topics first.");
  $("#plan-summary").innerHTML = `<h2 class="section-title">Why this plan</h2><h3>${esc(plainWords(sm.headline))}</h3><p>${coachHTML(sm.why)}</p>
    <div class="stat-row mt-4"><div class="stat"><b>${plan.hours_planned}h</b><span>of practice on the calendar${plan.review_hours ? `, plus about ${plan.review_hours}h of review` : ""} (${plan.hours_available}h available)</span></div>
      <div class="stat"><b>${plan.drills}</b><span>short practices ${tip("drill")}</span></div><div class="stat"><b>${plan.mocks}</b><span>mock interviews ${tip("mock interview")}</span></div></div>
    ${flags.map((f) => `<div class="flag">${f}</div>`).join("")}`;
  // Ladder
  const counts = {}; plan.tasks.forEach((t) => { if (t.type === "drill") counts[t.skill] = (counts[t.skill] || 0) + 1; });
  $("#plan-ladder").innerHTML = `<thead><tr><th>Topic</th><th>Now</th><th>Goal</th><th>Practices</th></tr></thead><tbody>` + visibleSkills(plan.skills).map((r) =>
    `<tr class="c-${r.skill}"><td><span class="skillcell">${esc(skillName(r.skill, r.name))} ${tip(r.skill)}</span></td><td>${esc(LEVEL_SHORT[r.current] || LEVEL_SHORT[0])}</td>
     <td>${r.current >= 3 ? "Top ✓" : esc(LEVEL_SHORT[r.target] || "")}</td><td class="tnum">${counts[r.skill] ?? 0}</td></tr>
     ${r.weak_subskills?.length ? `<tr class="subrow"><td colspan="4">↳ Focus on: ${r.weak_subskills.map((w) => esc(w.name)).join(", ")}</td></tr>` : ""}`).join("") + "</tbody>";
  // Calendar grouped by week, past days collapsed
  const byDay = {}; plan.tasks.forEach((t) => (byDay[t.date] = byDay[t.date] || []).push(t));
  const dayCard = (dt, ts) => `<div class="day ${dt === todayISO ? "is-today" : ""}"><h4><span>${esc(fmtDate(dt))}${dt === todayISO ? " · today" : ""}</span><span class="muted">${ts.reduce((a, t) => a + t.minutes, 0)} min</span></h4>
      <ul class="task-list">${ts.map((t) => taskRow(t, false)).join("")}</ul></div>`;
  const days = Object.keys(byDay).sort();
  const past = days.filter((x) => x < todayISO), upcoming = days.filter((x) => x >= todayISO);
  const weeks = {}; upcoming.forEach((x) => (weeks[weekLabel(x, todayISO)] = weeks[weekLabel(x, todayISO)] || []).push(x));
  $("#calendar").innerHTML = (past.length ? `<details class="past"><summary>Earlier days (${past.length})</summary><div class="calendar">${past.map((x) => dayCard(x, byDay[x])).join("")}</div></details>` : "") +
    Object.entries(weeks).map(([w, ds], i) => i < 2
      ? `<div class="week"><h3>${esc(w)}</h3><div class="calendar">${ds.map((x) => dayCard(x, byDay[x])).join("")}</div></div>`
      : `<details class="week past"><summary>${esc(w)} · ${ds.reduce((a, x) => a + byDay[x].length, 0)} tasks</summary><div class="calendar">${ds.map((x) => dayCard(x, byDay[x])).join("")}</div></details>`).join("");
}
$("#plan-rebuild").addEventListener("click", async () => {
  const b = $("#plan-rebuild"); b.disabled = true; b.textContent = "Updating…";
  try { await api("/api/plan/rebuild", {}); await renderPlan(); toast("Plan updated with your latest results.", "success"); }
  catch (e) { toast(e.message, "error"); } finally { b.disabled = false; b.textContent = "Update my plan"; }
});

// ------------------------------------------------------------------ practice launcher
async function renderLauncher() {
  await checkActive();
  if (S.session && S.view === "practice") return render("practice");
  const d = await refreshDash(); if (!d || S.view !== "practice") return;
  const p = d.progress;
  const lt = $("#lt-plan");
  if (!d.diagnostic_done) {
    lt.innerHTML = `<span class="eyebrow">Start here</span><h2>Placement interview ${tip("placement interview")}</h2>
      <p class="muted mt-0">15 minutes to find your starting point. It's not graded, and "I don't know" is a fine answer.</p><button class="primary big" data-start-placement>Start</button>`;
  } else if (p?.next) {
    lt.innerHTML = `<span class="eyebrow">Next in your plan</span><h2>${esc(taskTitle(p.next))}</h2>
      <p class="muted mt-0">${esc(taskSub(p.next))}</p><button class="primary big" data-task="${p.next.id}">Start</button>`;
  } else {
    lt.innerHTML = `<span class="eyebrow">Your plan is done</span><h2>Full mock interview</h2><p class="muted mt-0">Mixed questions, like a real interview.</p><button class="primary big" id="lt-mock">Start</button>`;
    $("#lt-mock").addEventListener("click", () => startSession("mock", persona()));
  }
  $("#lt-retake").hidden = !(d.diagnostic_done && d.can_retake_placement !== false);
  const ps = $("#q-persona");
  if (!ps.options.length) ps.innerHTML = Object.entries(S.meta.personas).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  ps.value = persona();
  const sk = $("#q-skill"), cur = sk.value;
  sk.innerHTML = Object.entries(S.meta.skills).filter(([k]) => k !== "industry" || showIndustry()).map(([k, v]) => `<option value="${k}">${esc(skillName(k, v))}</option>`).join("");
  if (cur && [...sk.options].some((o) => o.value === cur)) sk.value = cur;
  const lv = $("#q-level");
  if (!lv.options.length) lv.innerHTML = `<option value="">My next milestone</option>` + [1, 2, 3].map((l) => `<option value="${l}">${LEVEL_SHORT[l]} level</option>`).join("");
}
$("#q-mock").addEventListener("click", () => startSession("mock", $("#q-persona").value));
$("#q-practice").addEventListener("click", () => startSession("practice", $("#q-persona").value || persona(), $("#q-skill").value, Number($("#q-level").value) || null));

// ------------------------------------------------------------------ interview
async function startSession(mode, personaKey, focus = null, level = null, taskId = null) {
  if (S.busy) return;
  if (S.session && !confirm("You have an unfinished session. Start a new one instead? Your answers so far are saved.")) { go("practice"); return; }
  S.busy = true;
  try {
    const body = { mode, persona: personaKey, focus, level };
    if (taskId !== null && taskId !== undefined) body.task_id = taskId;
    const s = await api("/api/session", body);
    S.session = s; S.needsChatRebuild = false; S.busy = false;
    setupInterview(s, false);
    go("practice");
    speak(`${s.opener || ""} ${s.question?.text || ""}`, s.persona);
  } catch (e) { toast(e.message, "error"); } finally { S.busy = false; }
}
function setupInterview(s, resumed) {
  S.events = s.events || [];
  $("#chat").innerHTML = ""; resetDiag();
  const diag = s.mode === "diagnostic";
  $("#sb-mode").innerHTML = `${esc(MODE_LABEL[s.mode] || "Session")}${diag ? "" : `<span class="hide-m"> · ${esc((s.persona_label || "").split(" (")[0])}</span>`}`;
  const tipHost = $("#sb-mode-tip"); if (tipHost) tipHost.remove();
  $("#sb-mode").insertAdjacentHTML("afterend", `<span id="sb-mode-tip">${tip(MODE_TIP[s.mode] || "drill")}</span>`);
  $("#idk-btn").hidden = !diag;
  if (diag) {
    const el = document.createElement("div"); el.className = "intro-card";
    el.innerHTML = `<b>This is a check, not a test.</b> About 15 minutes, one try per question. If you don't know something, say so and we'll move on. That's useful information too.`;
    $("#chat").appendChild(el);
  }
  if (resumed) {
    (s.transcript || []).forEach((t) => {
      if (t.question) addMsg("ai", t.question, "Earlier question").classList.add("past-msg");
      if (t.answer) addMsg("me", t.answer, S.profile?.name);
      if (t.interviewer) addMsg("ai", t.interviewer, s.persona_label);
    });
    addMsg("ai", "Welcome back. Here's where you left off.", "IB Ready");
  }
  else if (s.opener) addMsg("ai", s.opener, s.persona_label);
  if (s.question) addQuestion(s.question);
  updateSessionBar(s.progress);
  updateMeter(s.usage);
  renderTurnTrace(S.events);
  $("#bts").open = localStorage.getItem("ibr_bts") === "1";
}
function afterShowInterview() {
  if (S.needsChatRebuild && S.session) { S.needsChatRebuild = false; setupInterview(S.session, true); }
  setTimeout(() => { const c = $("#chat"); c.scrollTop = c.scrollHeight; if (!isMobile()) $("#answer").focus(); }, 30);
}
$("#bts").addEventListener("toggle", () => localStorage.setItem("ibr_bts", $("#bts").open ? "1" : "0"));
function closeVoiceMenu() { $("#sb-tools").hidden = true; $("#sb-more").setAttribute("aria-expanded", "false"); }
$("#sb-more").addEventListener("click", (e) => { e.stopPropagation(); const t = $("#sb-tools"); t.hidden = !t.hidden; $("#sb-more").setAttribute("aria-expanded", String(!t.hidden)); });
document.addEventListener("click", (e) => { if (!e.target.closest("#sb-tools, #sb-more")) closeVoiceMenu(); });

function updateSessionBar(p) {
  if (!p) return;
  let label = p.label;
  if (p.kind === "diagnostic") {
    const q = S.session?.question;
    const n = Math.min((p.skills_done || 0) + 1, p.skills_total || 1);
    label = p.label === "Placement complete" ? "Placement complete" : `Topic ${n} of ${p.skills_total}${q ? `: ${skillName(q.skill)}` : ""}`;
  }
  $("#sb-label").textContent = label || "";
  $("#sb-fill").style.width = `${p.pct || 0}%`;
}
function addMsg(kind, text, who) {
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.innerHTML = `<div class="who">${esc(who || (kind === "me" ? "You" : "Interviewer"))}</div>${esc(kind === "ai" ? mapLevels(text) : text)}`;
  $("#chat").appendChild(el); chatToEnd();
  return el;
}
// Scroll only the chat box, never the page: scrolling the page pushed the session bar under the sticky header (QA D-04).
function chatToEnd() { const c = $("#chat"); c.scrollTop = c.scrollHeight; }
// Bring an element fully into the chat box; if it is taller than the box, show its top.
function chatShow(el) {
  const c = $("#chat"), cr = c.getBoundingClientRect(), er = el.getBoundingClientRect();
  const bottom = c.scrollTop + er.bottom - cr.bottom + 4, top = c.scrollTop + er.top - cr.top - 8;
  c.scrollTop = Math.min(Math.max(bottom, c.scrollTop), top);
}
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
function addQuestion(q) {
  const el = document.createElement("div");
  const diag = S.session?.mode === "diagnostic";
  el.className = `qcard c-${q.skill}`;
  el.innerHTML = `<div class="qcard-head"><span class="pill">${esc(skillName(q.skill))}</span>${tip(q.skill)}
    ${diag ? "" : `<span class="pill lvl-${q.difficulty}">${esc(LEVEL_SHORT[q.difficulty] ? LEVEL_SHORT[q.difficulty] + " level" : mapLevels(q.level || ""))}</span>`}
    ${q.subskill_name ? `<span class="small muted">${esc(q.subskill_name)}</span>` : ""}
    <span class="timer" aria-label="Time on this question">0:00 / ${mmss(q.target_seconds || 60)}</span></div>
    <div class="qcard-title">${esc(q.title)}</div><div class="qcard-text">${esc(q.text)}</div>`;
  $("#chat").appendChild(el); chatToEnd();
  clearAnswerBox();
  startTimer(el.querySelector(".timer"), q.target_seconds || 60);
  setHint();
  return el;
}
function setHint(over = false) {
  const q = S.session?.question;
  if (!q) return;
  const phase = q.phase === "why" ? "Explain your reasoning" : q.attempts_allowed === 1 ? "One try" : `Attempt ${q.attempt} of ${q.attempts_allowed}`;
  $("#attempt-hint").innerHTML = over ? `<span class="over">Over time. That's fine, finish your thought.</span>` : `${esc(phase)} · aim for ${mmss(q.target_seconds || 60)}`;
  updateCounter();
}
function startTimer(el, target) {
  stopTimer(); S.qStart = Date.now(); let wasOver = false;
  S.timer = setInterval(() => {
    const s = Math.floor((Date.now() - S.qStart) / 1000);
    el.textContent = `${mmss(s)} / ${mmss(target)}`;
    const over = s > target; el.classList.toggle("over", over);
    if (over !== wasOver) { wasOver = over; setHint(over); }
  }, 500);
}
function stopTimer() { clearInterval(S.timer); }
function thinking() {
  const el = document.createElement("div"); el.className = "msg ai thinking"; el.setAttribute("role", "status");
  el.innerHTML = `<span class="dots" aria-hidden="true"><span></span><span></span><span></span></span> Checking your numbers…`;
  $("#chat").appendChild(el); chatToEnd();
  el._t = setTimeout(() => el.insertAdjacentHTML("beforeend", " <span>Still working, thanks for waiting.</span>"), 8000);
  return el;
}
function updateCounter() {
  const max = $("#answer").maxLength > 0 ? $("#answer").maxLength : 0, n = $("#answer").value.length;
  let c = $("#char-counter");
  if (!max || n < max * 0.7) { if (c) c.remove(); return; }
  if (!c) { $("#attempt-hint").insertAdjacentHTML("beforeend", `<span class="counter" id="char-counter"></span>`); c = $("#char-counter"); }
  c.textContent = `${n} / ${max} characters`; c.classList.toggle("near", n >= max * 0.9);
}
$("#answer").addEventListener("input", () => {
  updateCounter();
  const t = $("#answer"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 160) + "px";
});
$("#answer").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#composer").requestSubmit(); } });
$("#composer").addEventListener("submit", (e) => { e.preventDefault(); submitAnswer(); });
$("#idk-btn").addEventListener("click", () => submitAnswer("I don't know"));

function clearAnswerBox() {
  stopMic();                      // aborts recognition and bumps MIC.turn, so late results are ignored
  const a = $("#answer"); a.value = ""; a.style.height = ""; updateCounter();
}
async function submitAnswer(override) {
  if (S.busy || !S.session) return;
  const text = (override ?? $("#answer").value).trim();
  stopMic();
  if (!text) { $("#answer").focus(); return; }
  const seconds = S.qStart ? (Date.now() - S.qStart) / 1000 : null;
  S.busy = true; $("#send-btn").disabled = true; $("#idk-btn").disabled = true;
  const draft = override ? "" : $("#answer").value;
  addMsg("me", text, S.profile.name); clearAnswerBox();
  closeSheet();
  const t = thinking();
  try {
    const r = await api(`/api/session/${S.session.id}/answer`, { text, seconds });
    clearTimeout(t._t); t.remove(); await handleTurn(r);
  } catch (err) {
    clearTimeout(t._t); t.remove();
    if (draft) $("#answer").value = draft;
    const rate = err.status === 429 || /too (fast|many|quick)|slow down|rate/i.test(err.message);
    const el = document.createElement("div"); el.className = "msg ai err"; el.setAttribute("role", "alert");
    el.innerHTML = `<div class="who">IB Ready</div>${rate ? "Easy, that was fast! Give it a second and press Submit again."
      : err.offline ? `${esc(OFFLINE_MSG)} ${draft ? "Your answer is still in the box." : ""}`
      : `We couldn't grade that one. ${draft ? "Your answer is still in the box." : ""} <span class="small muted">(${esc(err.message)})</span>`}
      ${rate ? "" : ` <button class="secondary small-btn" type="button">Try again</button>`}`;
    el.querySelector("button")?.addEventListener("click", () => { el.remove(); submitAnswer(override); });
    $("#chat").appendChild(el); chatToEnd();
  } finally { S.busy = false; $("#send-btn").disabled = false; $("#idk-btn").disabled = false; if (!isMobile()) $("#answer").focus(); }
}

async function handleTurn(r) {
  S.events = S.events.concat(r.events || []);
  renderShield(r.events || []); renderTurnTrace(r.events || []);
  if (r.blocked) {
    const el = addMsg("ai", r.reason || "That answer couldn't be sent.", "IB Ready");
    if (r.session) updateMeter(r.session.usage);
    const finished = r.session?.complete || r.session?.ended || /finished|ended|complete|over/i.test(r.reason || "");
    if (finished) {
      el.insertAdjacentHTML("beforeend", `<div class="mt-2"><button class="primary small-btn" type="button">See my results</button></div>`);
      el.querySelector(".primary").addEventListener("click", () => finishSession(true));
    }
    return;
  }
  S.session = { ...S.session, ...r.session };
  addMsg("ai", r.interviewer, S.session.persona_label);
  renderDiag(r); updateMeter(r.session?.usage); updateSessionBar(r.progress);
  if (r.complete) {
    stopTimer();
    addMsg("ai", "Session complete. Updating your progress…", "IB Ready");
    await finishSession(true);
    return;
  }
  if (r.next_question) {
    stopTimer(); const qEl = addQuestion(r.next_question);
    setTimeout(() => chatShow(qEl), 50);  // QA D-02: the whole new question in view, never under the composer
    speak(`${r.interviewer} ${r.next_question.text}`, S.session.persona); }
  else { setHint(); speak(r.interviewer, S.session.persona); }
}

// ------------------------------------------------------------------ feedback panel (side column on desktop, bottom sheet on mobile)
function resetDiag() { $("#diag-empty").hidden = false; $("#diag-body").hidden = true; $("#shield").hidden = true; $("#shield-list").innerHTML = ""; $("#sheet-btn").hidden = true; }
function renderDiag(r) {
  $("#diag-empty").hidden = true; $("#diag-body").hidden = false;
  const diag = S.session?.mode === "diagnostic";
  const [title, sub0] = VERDICT[r.verdict] || [r.verdict, ""];
  const numeric = (r.checks || []).length > 0;
  const sub = diag ? "Noted. Full explanations come in your practice sessions." : !numeric && r.verdict === "incorrect" ? "A key idea is missing or off. Have another go." : sub0;
  $("#verdict").className = `verdict v-${r.verdict}`;
  $("#verdict").innerHTML = `<span class="dot" aria-hidden="true"></span><div>${esc(title)}${r.explain_only ? " (your explanation)" : ""}<div class="vsub">${esc(sub)}</div></div>`;
  const checks = diag ? [] : (r.checks || []);
  $("#checks-wrap").hidden = !checks.length;
  $("#checks").innerHTML = checks.map((c) => {
    const cls = c.status === "correct" ? "ok" : c.status === "wrong" ? "bad" : "miss";
    const ic = c.status === "correct" ? "✓" : c.status === "wrong" ? "✗" : "–";
    const st = c.status === "correct" ? "right" : c.status === "wrong" ? "off" : "missing";
    let val = c.stated === null || c.stated === undefined ? (c.required ? "not stated" : "optional") : `you: <b>${fmt(c.stated)}</b>`;
    if (c.expected !== null && c.expected !== undefined && c.status !== "correct") val += ` · answer: <b>${fmt(c.expected)}</b>`;
    return `<li class="${cls}"><span class="ic" aria-hidden="true">${ic}</span><span>${esc(c.name)}${c.required ? "" : ' <span class="muted">(optional)</span>'}<span class="sr-only"> (${st})</span></span><span class="val">${val}</span></li>`;
  }).join("");
  $("#mis-wrap").innerHTML = diag ? "" : (r.misconceptions || []).map((m) => `<div class="mis"><span class="lbl">Mistake pattern</span> ${tip("mistake pattern")}<b>${esc(m.name)}</b><p>${esc(m.fix)}</p></div>`).join("") + lengthHTML(r.length);
  $("#rationale").textContent = diag ? "" : r.rationale ? `Why: ${r.rationale}` : (!r.resolved && r.verdict !== "correct" ? "Details unlock after your next try, so you can fix it yourself first." : "");
  $("#solution-wrap").hidden = diag || !r.solution; $("#solution").textContent = r.solution || "";
  $("#solution-label").textContent = r.answered_question?.kind === "numeric" ? "Worked solution (calculator)" : "Model answer";
  $("#solution-wrap").open = ["reveal", "note_next", "diag_next"].includes(r.action) && r.verdict !== "correct" && !diag;
  // mobile: a compact verdict chip in the chat that opens the feedback sheet
  if (isMobile()) {
    const right = checks.filter((c) => c.status === "correct").length;
    const el = document.createElement("div"); el.className = `msg ai v-${r.verdict}`;
    el.innerHTML = `<div class="verdict mt-0" style="margin:0"><span class="dot" aria-hidden="true"></span><div>${esc(title)}<div class="vsub">${checks.length ? `${right} of ${checks.length} numbers right. ` : ""}${diag ? esc(sub) : ""}</div></div></div>
      ${diag ? "" : `<button class="secondary small-btn mt-2" type="button">See feedback ▴</button>`}`;
    el.querySelector("button")?.addEventListener("click", openSheet);
    $("#chat").appendChild(el);
    // when a new question follows, handleTurn scrolls to it instead (QA D-02: never hide it under the composer)
    if (!r.next_question) setTimeout(chatToEnd, 0);
  }
}
// answer length: computed by the app from the model answer, coaching only (it never changes the grade)
function lengthHTML(ln) {
  if (!ln) return "";
  if (!ln.too_long) return `<div class="len ok"><span class="lbl">Answer length</span> <b>Nicely concise</b><p>${ln.words} words, within the ${ln.target}-word target.</p></div>`;
  return `<div class="len long"><span class="lbl">Answer length</span> <b>Too long: ${ln.words} words (target about ${ln.target})</b><p>${esc(ln.tip || "")}</p></div>`;
}
function deliveryHTML(dl) {
  if (!dl) return "";
  const title = dl.long ? `${dl.long} of ${dl.of} answers ran long` : `All ${dl.of} answers were concise`;
  return `<h3>Answer length</h3><div class="focus"><b class="nm">${esc(title)}</b><p>${esc(dl.tip || "")}</p></div>`;
}
function conciseHTML(c) {
  if (!c) return "";
  const trend = c.pct_long_before == null ? "" : c.pct_long < c.pct_long_before ? ` Down from ${c.pct_long_before}% before. ▼ Getting tighter.` : c.pct_long > c.pct_long_before ? ` Up from ${c.pct_long_before}% before.` : "";
  return `<div class="mis-item len-trend"><div class="top"><span class="chip ${c.pct_long > 30 ? "working" : "fixed"}">${c.pct_long > 30 ? "Still working on it" : "On track ✓"}</span>
    <b>Concise answers</b><span class="small muted">last ${c.answers} technical answers</span></div>
    <p>${c.pct_long}% ran longer than the target.${trend} Lead with the result, then one line of why.</p></div>`;
}
function openSheet() { if (!isMobile()) return; $("#side-col").classList.add("open"); $("#sheet-scrim").hidden = false; $("#sheet-close").focus(); }
function closeSheet() { $("#side-col").classList.remove("open"); $("#sheet-scrim").hidden = true; }
$("#sheet-btn").addEventListener("click", () => (isMobile() ? openSheet() : $("#diag").scrollIntoView({ block: "nearest" })));
$("#sheet-close").addEventListener("click", closeSheet);
$("#sheet-scrim").addEventListener("click", closeSheet);
function renderShield(events) {
  const safety = events.filter((e) => e.kind === "safety");
  if (!safety.length) return;
  $("#shield").hidden = false;
  $("#shield-list").insertAdjacentHTML("afterbegin", safety.map((e) => `<li>${esc(e.summary)}</li>`).join(""));
  if (safety.some((e) => /truncat/i.test(e.summary))) toast("Your answer was long, so only the first part was graded.", "info");
}
const actorClass = (a) => (["Director", "Guard", "Calculator", "Interviewer", "Coach", "Planner"].includes(a) ? a : "spec");
function traceItem(e, compact) {
  const tok = e.kind === "llm" ? `<span class="tok">${fmt(e.input_tokens)} in (${fmt(e.cached_tokens)} cached) · ${fmt(e.output_tokens)} out · ${money(e.cost_usd, 5)}</span>` : `<span class="tok"></span>`;
  const detail = !compact && e.detail && Object.keys(e.detail).length ? `<details><summary>details</summary><pre>${esc(JSON.stringify(e.detail, null, 2))}</pre></details>` : "";
  return `<li><span class="actor ${actorClass(e.actor)}">${esc(e.actor)}</span><span>${esc(e.summary)}</span>${tok}${detail}</li>`;
}
function renderTurnTrace(events) { $("#turn-trace").innerHTML = events.map((e) => traceItem(e, true)).join("") || `<li class="empty">Nothing yet.</li>`; }
function updateMeter(u) {
  if (!u) return;
  const total = (u.input_tokens || 0) + (u.output_tokens || 0);
  $("#meter-cost").textContent = money(u.cost_usd); $("#meter-tokens").textContent = total.toLocaleString();
  $("#meter-fill").style.width = `${Math.min(100, (100 * total) / (S.session?.budget || 120000))}%`;
}

// ------------------------------------------------------------------ end of session -> results
$("#end-btn").addEventListener("click", () => { closeVoiceMenu(); if (S.session && !S.busy) finishSession(false); });
async function finishSession(auto) {
  const answered = S.session?.progress?.answered ?? 0;
  if (!auto && answered < 3 && !confirm("End now? We'll update your skills with what you've answered so far.")) return;
  S.busy = true; stopMic(); stopTimer(); window.speechSynthesis?.cancel();
  try {
    let r = null;
    for (let i = 0; i < 8 && !r; i++) {
      try { r = await api(`/api/session/${S.session.id}/end`, {}); }
      catch (e) { if (e.status !== 409) throw e; await new Promise((ok) => setTimeout(ok, 1500)); }
    }
    if (!r) throw new Error("Still wrapping up your session. Give it a moment and try again.");
    S.lastReport = r; S.session = null;
    await refreshDash();
    renderResults(r);
    go("results");
  } catch (e) { toast(e.message, "error"); } finally { S.busy = false; }
}
function normDebrief(d = {}) {
  return {
    headline: d.headline || "",
    went_well: d.went_well || d.strengths || [],
    work_on: d.work_on || (d.focus_areas || []).map((f) => ({ misconception_id: f.misconception_id, name: f.name || f.misconception_id, why: f.why_it_matters, try_this: f.drill })),
    next_step: d.next_step || d.next_session || "",
    encouragement: d.encouragement || "",
  };
}
function focusHTML(f, seen) {
  return `<div class="focus"><b class="nm">${esc(f.name || f.misconception_id)}</b>${f.why ? `<p><span class="k">Why it matters:</span> ${coachHTML(f.why, seen)}</p>` : ""}${f.try_this ? `<p><span class="k">Try this:</span> ${coachHTML(f.try_this, seen)}</p>` : ""}</div>`;
}
function renderResults(r) {
  const mode = r.session?.mode;
  const placement = r.is_placement ?? mode === "diagnostic";
  const d = normDebrief(r.debrief || {});
  const turns = (r.turns || []).filter((t) => t.verdict);
  const n = turns.length;
  const st = Number(r.session?.started), en = Number(r.session?.ended);
  const mins = st && en && en > st ? Math.max(1, Math.round((en - st) / 60)) : null;
  const p = r.plan_progress, next = p?.next;
  const dd = S.dash || {};
  $("#res-levelups").innerHTML = "";
  let enc = d.encouragement;

  if (placement) {
    const placed = r.placement || {};
    const keys = Object.keys(placed);
    $("#res-kind").textContent = keys.length ? "Placement complete" : "Placement paused";
    $("#res-notes").parentElement.hidden = !keys.length;
    if (!keys.length) {
      $("#res-title").textContent = "Let's finish your placement next time.";
      $("#res-sub").textContent = "You ended before we could place any topic. It takes about 15 minutes, and you can start again whenever you're ready.";
      $("#res-changes").innerHTML = `<button class="primary big" data-start-placement>Restart placement interview</button>`;
    } else {
      const overall = dd.overall_label || LEVEL_NAMES[Math.round(keys.reduce((a, k) => a + placed[k], 0) / keys.length)];
      const lvl = dd.overall_level ?? 1;
      $("#res-title").textContent = ["You're getting started. That's a normal place to begin.", "You're coffee-chat ready. Nice foundation.",
        "You're first-round ready. Strong start.", "You're Superday ready. Impressive."][Math.max(0, Math.min(3, lvl))];
      const days = daysUntil(dd.intake?.interview_date);
      $("#res-sub").textContent = `${days != null && days >= 0 ? `Your interview is in ${days} day${days === 1 ? "" : "s"}. ` : ""}Here's where you stand and what to do first.` +
        (r.placement_partial ? " You ended early, so topics you didn't reach are marked Getting started." : "");
      const sorted = visibleSkills(keys.map((k) => ({ key: k, level: placed[k] }))).sort((a, b) => b.level - a.level);
      const maxL = sorted[0]?.level, minL = sorted.at(-1)?.level;
      $("#res-changes").innerHTML = journey(lvl) + `<h3 class="section-title mt-4">By topic</h3>` + sorted.map((s) =>
        `<div class="placement-row c-${s.key}"><span class="nm">${esc(skillName(s.key))} ${tip(s.key)}</span>${levelMeter(s.level, null, { label: LEVEL_NAMES[s.level] })}
         <span class="lvname">${esc(LEVEL_SHORT[s.level] || LEVEL_SHORT[0])} ${maxL !== minL && s.level === maxL ? '<span class="chip strong">Strongest</span>' : maxL !== minL && s.level === minL ? '<span class="chip start">Start here</span>' : ""}</span></div>`).join("");
    }
    const seen = new Set();
    $("#res-notes").innerHTML = `<div class="notes"><h2 class="section-title">Your coach's notes</h2>${d.headline ? `<p class="headline">${coachHTML(d.headline, seen)}</p>` : ""}
      ${d.went_well.length ? `<h3>What went well</h3><ul>${d.went_well.map((s) => `<li>${coachHTML(s, seen)}</li>`).join("")}</ul>` : ""}
      ${d.work_on.length ? `<h3>Where to start</h3>${d.work_on.slice(0, 2).map((f) => focusHTML(f, seen)).join("")}` : ""}</div>`;
    $("#res-next").innerHTML = next ? `<span class="eyebrow">Your first step</span>
      <p class="task-line">${esc(taskTitle(next))}</p><p class="small muted mt-0">${esc(taskSub(next))}</p>
      ${r.next_why ? `<p class="nstep">${coachHTML(r.next_why)}</p>` : ""}
      <button class="primary big" data-task="${next.id}">Start</button>
      <button class="textlink" data-go="plan">See my plan</button>`
      : `<span class="eyebrow">Your next step</span><p class="nstep">${coachHTML(d.next_step || "Head home to see what's next.")}</p><button class="primary big" data-go="home">Continue</button>`;
    
  } else {
    // questions = finished questions (done_q); answers = every graded reply, including second attempts and follow-ups
    const nq = r.questions_done ?? n;
    $("#res-kind").textContent = `${(MODE_LABEL[mode] || "Session").replace("Topic practice", "Practice")} complete · ${nq} question${nq === 1 ? "" : "s"}` +
      (n > nq ? ` · ${n} answers` : "");
    $("#res-notes").parentElement.hidden = false;
    const touched = (r.touched_skills && r.touched_skills.length ? r.touched_skills : [...new Set(turns.map((t) => t.skill))]).filter(Boolean);
    $("#res-sub").textContent = n < 3
      ? "Short session, so this is a light read. A few more answers next time will sharpen your picture."
      : `You practiced ${touched.map((k) => skillName(k)).join(", ")}${mins ? ` for ${mins} minute${mins === 1 ? "" : "s"}` : ""}.`;
    const ups = r.level_ups || [];
    // "Good work" only when something actually went up (a milestone, or earned confidence on a topic)
    const improved = ups.length > 0 || touched.some((k) => Math.round(100 * (r.mastery_end?.[k]?.p ?? 0)) > Math.round(100 * (r.mastery_start?.[k]?.p ?? 0)));
    $("#res-title").textContent = !n ? "Session ended" : improved ? "Good work. Here's what changed." : "Session complete. Here's what to work on next.";
    $("#res-levelups").innerHTML = ups.map((u, i) => `<div class="levelup" style="animation-delay:${0.2 + i * 0.15}s">⬆ ${esc(skillName(u.skill, u.name))}: ${esc(lvlLabel(u.from))} → ${esc(lvlLabel(u.to))}<div class="small" style="font-weight:500">${esc(levelUpLine(skillName(u.skill, u.name), u.to))}</div></div>`).join("");
    const row = (k) => {
      const a = r.mastery_start?.[k]?.p, b = r.mastery_end?.[k]?.p;
      const la = r.levels_start?.[k] ?? 0, lb = r.levels_end?.[k] ?? la;
      const fresh = (r.mastery_start?.[k]?.n ?? 1) === 0;  // the "before" value is a default, not earned
      const pa = a == null || fresh ? null : Math.round(100 * a), pb = b == null ? null : Math.round(100 * b);
      const up = ups.some((u) => u.skill === k), diff = pa != null && pb != null ? pb - pa : 0;
      const chip = up ? '<span class="chip levelup">⬆ Level up</span>' : diff > 0 ? '<span class="chip up">▲ Up</span>' : diff < 0 ? '<span class="chip dipped">Dipped this time</span>' : "";
      return `<div class="change-row c-${k}"><span class="nm">${esc(skillName(k))} ${tip(k)} <span class="lvname">${esc(LEVEL_SHORT[lb] || LEVEL_SHORT[0])}${la !== lb ? ` (was ${esc(LEVEL_SHORT[la] || LEVEL_SHORT[0])})` : ""}</span></span>
        ${levelMeter(lb, pb != null ? pb / 100 : null, { label: LEVEL_NAMES[lb] })}
        <span class="nums">${pa != null && pb != null ? `<span>Confidence ${pa}% → ${pb}%</span>` : pb != null ? `<span>Confidence now ${pb}%</span>` : ""}${chip}</span>
        ${diff < 0 && !up ? `<p class="helper">Early dips are normal. One tough answer moves a new topic a lot. It recovers as you practice.</p>` : ""}</div>`;
    };
    const others = visibleSkills(Object.keys(S.meta.skills).map((k) => ({ key: k }))).map((s) => s.key).filter((k) => !touched.includes(k));
    $("#res-changes").innerHTML = `<h2 class="section-title">What changed ${tip("confidence")}</h2>` + (touched.length ? touched.map(row).join("") : `<p class="muted mt-0">No answers were graded, so nothing changed.</p>`) +
      (others.length ? `<details class="more-focus"><summary>Show all topics</summary>${others.map(row).join("")}</details>` : "");
    const dipped = touched.some((k) => (r.mastery_end?.[k]?.p ?? 0) < (r.mastery_start?.[k]?.p ?? 0));
    const seen = new Set();
    $("#res-notes").innerHTML = `<div class="notes"><h2 class="section-title">Your coach's notes</h2>${d.headline ? `<p class="headline">${coachHTML(d.headline, seen)}</p>` : ""}
      ${d.went_well.length ? `<h3>What went well</h3><ul>${d.went_well.map((s) => `<li>${coachHTML(s, seen)}</li>`).join("")}</ul>` : ""}
      <h3>One thing to work on ${tip("mistake pattern")}</h3>${d.work_on.length ? focusHTML(d.work_on[0], seen) : `<p class="mt-0">No mistake patterns this session. That's a clean run.</p>`}
      ${d.work_on.length > 1 ? `<details class="more-focus"><summary>${d.work_on.length - 1} more thing${d.work_on.length > 2 ? "s" : ""} to work on</summary>${d.work_on.slice(1).map((f) => focusHTML(f, seen)).join("")}</details>` : ""}
      ${deliveryHTML(r.debrief?.delivery)}</div>`;
    $("#res-next").innerHTML = `<span class="eyebrow">Your next step</span>
      ${next ? `<p class="task-line">${esc(taskTitle(next))}</p><p class="small muted mt-0">${esc(taskSub(next))}</p>
        ${r.next_why ? `<p class="nstep">${coachHTML(r.next_why)}</p>` : ""}
        <button class="primary big" data-task="${next.id}">Start</button>`
      : `<p class="task-line">Full mock interview</p><p class="nstep">${p ? "You've finished every task on your plan. " : ""}Mixed questions, like the real interview, keep everything fresh.</p>
        <button class="primary big" id="res-mock">Start</button>`}
      <button class="textlink" data-go="home">Back to Home</button>
      ${p ? `<p class="small muted mt-0">Plan: ${p.done} of ${p.total} tasks done${r.debrief?.plan_event?.startsWith?.("ticked") ? " (this session counted ✓)" : ""}</p>` : ""}`;
    $("#res-mock")?.addEventListener("click", () => startSession("mock", persona()));
    enc = enc || (dipped || n < 3 ? encourage("keep_going") : "");
  }
  if (placement && !Object.keys(r.placement || {}).length) enc = "";
  $("#res-encourage").textContent = enc || ""; $("#res-encourage").hidden = !enc;
  const u = r.usage || {};
  $("#res-bts-body").innerHTML = `<div class="kpis"><div class="kpi"><b>${money(u.cost_usd)}</b><span>model cost for this session</span></div>
    <div class="kpi"><b>${((u.input_tokens || 0) + (u.output_tokens || 0)).toLocaleString()}</b><span>tokens (${(u.cached_tokens || 0).toLocaleString()} cached input)</span></div></div>
    <p class="small mt-2"><button class="textlink" data-go="how" data-sec="behind">See every step on How it works →</button></p>`;
  $("#res-bts").open = false; $("#survey-wrap").open = false;
  resetSurvey();
}

// ------------------------------------------------------------------ survey
$("#rating").innerHTML = Array.from({ length: 10 }, (_, i) => `<button type="button" aria-pressed="false" aria-label="${i + 1} out of 10">${i + 1}</button>`).join("");
$$("#rating button").forEach((b) => b.addEventListener("click", () => { $$("#rating button").forEach((x) => x.setAttribute("aria-pressed", "false")); b.setAttribute("aria-pressed", "true"); S.rating = Number(b.textContent); }));
function resetSurvey() { S.rating = null; $$("#rating button").forEach((x) => x.setAttribute("aria-pressed", "false")); $("#survey").reset(); $("#survey-status").textContent = ""; $("#survey button[type=submit]").disabled = false; }
$("#survey").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { session_id: S.lastReport?.session?.id || null, rating: S.rating, vs_current: $("#vs-current").value || null,
    found_new: $("#found-new").value || null, time_to_find: $("#time-to-find").value || null,
    prep_today: $("#prep-today").value.trim() || null, quote: $("#quote").value.trim() || null, consent: $("#consent").checked };
  if (!Object.entries(body).some(([k, v]) => !["session_id", "consent"].includes(k) && v)) { $("#survey-status").textContent = "Answer at least one question first."; return; }
  try { await api("/api/feedback", body); $("#survey-status").textContent = "Thanks! Saved."; $("#survey button[type=submit]").disabled = true; } catch (err) { toast(err.message, "error"); }
});

// ------------------------------------------------------------------ progress
function sparkline(hist, color) {
  const pts = (hist || []).map((h) => h.p);
  if (pts.length < 2) return `<p class="spark-empty">Your trend line appears after your next session.</p>`;
  const xs = pts.map((_, i) => (i / (pts.length - 1)) * 196 + 2), ys = pts.map((p) => 40 - p * 36);
  const dpath = xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 200 44" preserveAspectRatio="none" role="img" aria-label="Confidence trend, now ${Math.round(pts.at(-1) * 100)}%"><path d="${dpath} L198,44 L2,44 Z" fill="${color}" opacity=".16"/>
    <path d="${dpath}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>`;
}
const SKILL_INK = { accounting: "#2a6fa6", ev: "#5e4cc2", dcf: "#237e5b", ma: "#a8521f", lbo: "#b83d62", industry: "#7f5f00", fit: "#7a4fc4" };
function skillCard(s, d) {
  const name = skillName(s.key, s.name);
  const subs = (s.subskills || []).slice(0, 12).map((x) => {
    const cls = x.p < 0.5 ? "weak" : x.p >= 0.75 ? "ok" : "";
    return `<span class="subchip ${cls}" title="${Math.round(x.p * 100)}% confidence on ${x.n} answer(s)">${cls === "weak" ? "! " : cls === "ok" ? "✓ " : ""}${esc(x.name)}</span>`;
  }).join("");
  const L = s.level || 0;
  return `<article class="card skill-card c-${s.key}">
    <h3><span class="nm">${esc(name)} ${tip(s.key)}</span><span class="pill lvl-${L}">${esc(LEVEL_SHORT[L])}</span></h3>
    ${levelMeter(L, s.n ? s.p : null, { ink: SKILL_INK[s.key], label: LEVEL_NAMES[L] })}
    <p class="small mt-0">${L >= 3 ? "Top milestone reached ✓" : `<b>Next:</b> ${esc(LEVEL_NAMES[L + 1])}`}</p>
    <div class="meta">${s.n ? `${s.n} answered · confidence ${Math.round(s.p * 100)}% ${tip("confidence")}` : "No answers yet"}</div>
    ${s.n ? sparkline(s.history, SKILL_INK[s.key]) : ""}
    ${subs ? `<div class="sub">${subs}</div>` : ""}
    <div class="skill-detail"><button class="textlink" data-drill="${s.key}">Practice this topic →</button></div>
  </article>`;
}
async function renderProgress() {
  const d = await refreshDash(); if (!d || S.view !== "progress") return;
  const nothing = !d.diagnostic_done && !d.answered;
  $("#progress-empty").hidden = !nothing; $("#progress-main").hidden = nothing; $("#progress-journey").hidden = nothing;
  if (nothing) {
    $("#progress-empty").innerHTML = emptyState("Nothing to show yet.", emptyCopy("progress", "no_skills"), `<button class="primary big" data-start-placement>Start</button>`);
    return;
  }
  $("#progress-journey").innerHTML = journey(d.diagnostic_done ? d.overall_level : 0).replace("Your journey", "Overall");
  $("#skills-full").innerHTML = visibleSkills(d.skills).map((s) => skillCard(s, d)).join("");
  const mis = d.misconceptions || [];
  $("#mis-list").innerHTML = mis.length ? mis.map((x) => {
    const ev = (x.evidence || []).slice(-2).reverse().map((e) => (e.quote ? `<q>${esc(e.quote)}</q>` : "")).join("");
    return `<div class="mis-item"><div class="top"><span class="chip ${x.active ? "working" : "fixed"}">${x.active ? "Still working on it" : "Fixed ✓"}</span>
      <b>${esc(x.name)}</b><span class="small muted">seen ${x.hits}×</span></div>${ev}<p>${esc(x.fix)}</p></div>`;
  }).join("") : `<div><p class="mt-0"><b>No mistake patterns yet.</b></p><p class="small muted">That's either a clean run or you're just getting started.</p></div>`;
  $("#mis-list").insertAdjacentHTML("afterbegin", conciseHTML(d.concise));
  $("#mis-list").insertAdjacentHTML("beforeend", `<details class="more-focus"><summary>What's a mistake pattern?</summary><div class="prose small">${misHTML(true)}</div></details>`);
}

// ------------------------------------------------------------------ how it works (primer, checks, behind the scenes, clubs)
async function renderHow(sec) {
  $("#primer").innerHTML = rich(C("primer"));
  $("#levels-explainer").innerHTML = levelsHTML(C("levels"));
  $("#mis-explainer").innerHTML = misHTML();
  const groups = {};
  (GLOSS.list.length ? GLOSS.list : Object.values(TIPS).map(([t, def]) => ({ group: "", term: t, def })))
    .forEach((e) => (groups[e.group || ""] = groups[e.group || ""] || []).push(e));
  $("#glossary-list").innerHTML = Object.entries(groups).map(([g, es]) => `${g ? `<h4>${esc(g)}</h4>` : ""}${es.map((e) => `<div><b>${esc(mapLevels(e.term))}:</b> ${esc(mapLevels(e.def))}</div>`).join("")}`).join("");
  if (sec) { const target = $(`#sec-${sec}`); if (target) setTimeout(() => target.scrollIntoView({ block: "start" }), 30); }
  if (!S.token) {
    $("#behind-body").innerHTML = `<div class="card"><p class="mt-0 muted">Sign in and run any session to see its step-by-step trace and cost here.</p></div>`;
    $("#club-body").innerHTML = `<div class="card"><p class="mt-0 muted">Sign in to see the anonymised club view.</p></div>`;
    return;
  }
  const prices = S.meta?.prices;
  if (prices) $("#price-line").textContent = `Every step of your latest session: what the director decided, what each agent did, what the calculator checked, what the safety guard blocked, and what it cost (${S.meta.model || "the model"} price per million tokens: ${Object.entries(prices).map(([k, v]) => `${k.replace(/_/g, " ")} $${Number(v).toFixed(2)}`).join(" · ")}).`;
  const sid = S.session?.id || S.lastReport?.session?.id;
  try {
    if (sid) {
      const r = await api(`/api/session/${sid}/events`);
      $("#trace").innerHTML = r.events.map((e) => traceItem(e, false)).join("") || `<li class="empty">No steps yet.</li>`;
      const u = r.usage, total = u.input_tokens + u.output_tokens, cp = u.input_tokens ? Math.round((100 * u.cached_tokens) / u.input_tokens) : 0;
      $("#kpis").innerHTML = `<div class="kpi"><b>${money(u.cost_usd)}</b><span>cost this session</span></div><div class="kpi"><b>${total.toLocaleString()}</b><span>tokens (${u.llm_calls ?? "?"} model calls)</span></div>
        <div class="kpi"><b>${cp}%</b><span>input served from cache</span></div><div class="kpi"><b>${u.output_tokens.toLocaleString()}</b><span>output tokens</span></div>`;
    } else { $("#trace").innerHTML = `<li class="empty">Run any session to see its step-by-step trace here.</li>`; $("#kpis").innerHTML = `<p class="small muted mt-0">No session yet.</p>`; }
  } catch (e) { $("#trace").innerHTML = `<li class="empty">Couldn't load the trace (${esc(e.message)}).</li>`; }
  try {
    const c = await api("/api/costs");
    const per = c.per_answer?.usd || 0;
    $("#cost-kpi").innerHTML = per ? `Cost per graded answer: <b>${money(per, 4)}</b>, about <b>${Math.round(1 / per).toLocaleString()}</b> answers for $1. <span class="small muted">(${c.answers} answers across ${c.sessions} sessions on this install)</span>`
      : `No graded answers on this install yet.`;
    $("#agent-tbl").innerHTML = `<thead><tr><th>Agent</th><th>Calls</th><th>Input</th><th>Cached</th><th>Output</th><th>Cost</th></tr></thead><tbody>` +
      c.per_agent.map((a) => `<tr><td><span class="actor ${actorClass(a.actor)}">${esc(a.actor)}</span></td><td>${a.calls}</td><td>${fmt(a.input_tokens)}</td><td>${fmt(a.cached_tokens)}</td><td>${fmt(a.output_tokens)}</td><td>${money(a.cost_usd, 4)}</td></tr>`).join("") +
      `<tr><td><b>Per graded answer</b></td><td></td><td>${fmt(Math.round(c.per_answer.i))}</td><td>${fmt(Math.round(c.per_answer.cch))}</td><td>${fmt(Math.round(c.per_answer.o))}</td><td><b>${money(per, 5)}</b></td></tr></tbody>`;
  } catch (e) { $("#cost-kpi").textContent = `Cost data unavailable (${e.message}).`; }
  try {
    const c = await api("/api/club"); const n = Math.max(c.members, 1);
    if (c.too_few_members) {
      $("#club-mis").innerHTML = `<p class="muted mt-0">Not enough members yet (${c.members} so far). To keep everyone anonymous, this view appears once at least 3 members have practiced.</p>`;
      $("#club-skills").innerHTML = `<p class="muted mt-0">Averages appear with 3 or more members.</p>`;
      return;
    }
    $("#club-mis").innerHTML = c.misconceptions.length ? `<p class="small muted mt-0">${c.members} members · ${c.answers} graded answers</p>` +
      c.misconceptions.slice(0, 10).map((m) => { const pct = Math.round((100 * m.members) / n);
        return `<div class="club-row"><div>${esc(m.name)}<small>${esc(m.skill)} · ${m.hits} times · ${pct}% of members</small><div class="bar"><div style="width:${pct}%"></div></div></div><b>${pct}%</b></div>`; }).join("")
      : `<p class="muted mt-0">No answers yet across the club. Data appears as members practice.</p>`;
    $("#club-skills").innerHTML = c.skills.length ? c.skills.map((s) => { const pct = Math.round(100 * s.avg_p);
      return `<div class="club-row c-${s.skill}"><div>${esc(s.name)}<div class="mini-bar"><div style="width:${pct}%;background:var(--ci)"></div></div></div><b>${pct}%</b></div>`; }).join("")
      : `<p class="muted mt-0">No data yet.</p>`;
  } catch (e) { $("#club-mis").innerHTML = `<p class="muted mt-0">Club data unavailable (${esc(e.message)}).</p>`; $("#club-skills").innerHTML = ""; }
}

// ------------------------------------------------------------------ voice: interviewer speaks (browser TTS), candidate speaks (browser STT)
const VOICE = { associate: { rate: 1.03, pitch: 1.05 }, vp: { rate: 1.14, pitch: 0.95 }, director: { rate: 0.98, pitch: 0.9 }, md: { rate: 0.92, pitch: 0.85 } };
function pickVoice(p) {
  const vs = (window.speechSynthesis?.getVoices() || []).filter((v) => v.lang?.startsWith("en"));
  if (!vs.length) return null;
  const idx = { associate: 0, vp: 1, director: 2, md: 3 }[p] || 0;
  return vs[idx % vs.length];
}
function speak(text, p, force = false) {
  if (!("speechSynthesis" in window) || (!S.tts && !force) || !text) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/\$/g, " dollars ").replace(/mm\b/g, " million"));
  const v = pickVoice(p); if (v) u.voice = v;
  Object.assign(u, VOICE[p] || {});
  u.onend = () => { if (S.handsfree && S.session && !S.busy && !MIC.on) startMic(); };
  window.speechSynthesis.speak(u);
}
$("#tts-toggle").addEventListener("change", (e) => { S.tts = e.target.checked; localStorage.setItem("tt_tts", S.tts ? "1" : "0"); if (!S.tts) window.speechSynthesis?.cancel(); });
$("#handsfree-toggle").addEventListener("change", (e) => {
  S.handsfree = e.target.checked; localStorage.setItem("tt_hf", S.handsfree ? "1" : "0");
  if (S.handsfree && !S.tts) { S.tts = true; $("#tts-toggle").checked = true; localStorage.setItem("tt_tts", "1"); }
  if (S.handsfree) toast("Hands-free on: the interviewer speaks, the mic opens, and saying \"submit\" sends your answer.", "info");
});

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const MIC = { rec: null, on: false, base: "", turn: 0 };
function setupMic() {
  const b = $("#mic-btn");
  if (!SR) { b.disabled = true; b.title = "Voice input needs Chrome or Edge"; return; }
  b.addEventListener("click", () => (MIC.on ? stopMic() : startMic()));
}
function startMic() {
  if (!SR || MIC.on || !S.session) return;
  window.speechSynthesis?.cancel();
  const turn = MIC.turn;                 // results from an older turn are ignored
  const rec = new SR(); rec.lang = "en-US"; rec.continuous = true; rec.interimResults = true;
  MIC.rec = rec;
  MIC.base = $("#answer").value.trim() ? $("#answer").value.trim() + " " : "";
  const live = () => MIC.on && MIC.rec === rec && MIC.turn === turn;
  rec.onresult = (e) => {
    if (!live()) return;
    let text = "";
    for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
    const said = (MIC.base + text).trim();
    if (S.handsfree && /\b(submit|send it|final answer)\.?$/i.test(said)) {
      $("#answer").value = said.replace(/\b(submit|send it|final answer)\.?$/i, "").trim();
      submitAnswer(); return;
    }
    $("#answer").value = said;
  };
  rec.onerror = (e) => { if (!live() || e.error === "no-speech" || e.error === "aborted") return; toast(e.error === "not-allowed" ? "Microphone access is blocked. Allow it from the address bar." : `Voice input stopped (${e.error}).`, "info"); stopMic(); };
  rec.onend = () => { if (live()) { MIC.base = $("#answer").value.trim() ? $("#answer").value.trim() + " " : ""; try { rec.start(); } catch {} } };
  rec.start(); MIC.on = true;
  $("#mic-btn").classList.add("rec"); $("#mic-label").textContent = S.handsfree ? "Listening… say \"submit\"" : "Listening… tap to stop";
}
function stopMic() {
  MIC.turn++; MIC.on = false;
  const rec = MIC.rec; MIC.rec = null;
  if (rec) { rec.onresult = rec.onend = rec.onerror = null; try { rec.abort(); } catch {} }
  $("#mic-btn").classList.remove("rec"); $("#mic-label").textContent = "Speak";
}
setupMic();

init().catch((e) => toast(e.message, "error"));
