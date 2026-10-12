"use strict";

const $ = (selector) => document.querySelector(selector);
const h = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const money = (cents) => new Intl.NumberFormat("en-US", {style:"currency",currency:"USD"}).format(cents / 100);
const initials = (name) => name.split(" ").map((part) => part[0]).slice(0, 2).join("");
const dateLabel = (date) => new Date(date).toLocaleString(undefined, {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
const paths = {
  home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
  team:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.9M15 3.2a4 4 0 0 1 0 7.6"/><circle cx="9" cy="7" r="4"/>',
  activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9m-8 13h4"/>',
  sliders:'<path d="M4 7h7m4 0h5M4 17h3m4 0h9"/><circle cx="13" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  refresh:'<path d="M20 7V3l-3 3a8 8 0 1 0 3 9m0-8h-5"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  checkCircle:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/>',
  unlock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 7.5-2M12 15v2"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
  card:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h3"/>',
  layers:'<path d="m12 3 10 5-10 5L2 8Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  code:'<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 20"/>',
  alert:'<path d="M10.3 4.6a2 2 0 0 1 3.4 0l8 13.9a2 2 0 0 1-1.7 3H4a2 2 0 0 1-1.7-3Z"/><path d="M12 9v4m0 4v.1"/>',
  inbox:'<path d="M4 4h16l2 11v5H2v-5Zm-2 11h6l2 3h4l2-3h6"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.info}</svg>`;
let storedActor = "maya";
try { storedActor = sessionStorage.getItem("access-lab-persona") || "maya"; } catch (_) { /* A private tab may deny storage. */ }
const state = { actorId:storedActor, view:"workspace", workspace:null, demo:null, review:null, sample:null, busy:false, refreshId:0 };
let toastTimer;

async function api(path, body, actorId = state.actorId) {
  let response;
  try {
    response = await fetch(path, {method:body === undefined ? "GET" : "POST", headers:{"X-Demo-User":actorId, ...(body === undefined ? {} : {"Content-Type":"application/json"})}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  } catch (_) {
    const error = new Error("The local app could not be reached. Check that the server is running, then try again.");
    error.code = "network_error";
    throw error;
  }
  let data;
  try { data = await response.json(); } catch (_) { throw new Error("The server returned an unreadable response. Refresh and try again."); }
  if (!response.ok) {
    const error = new Error(data.error?.message || "This action could not be completed.");
    error.code = data.error?.code;
    error.status = response.status;
    throw error;
  }
  return data;
}

function announce(message) { $("#announcer").textContent = message; }
function toast(message, error = false) {
  clearTimeout(toastTimer);
  const target = $("#toast");
  target.textContent = message;
  target.classList.toggle("error", error);
  target.hidden = false;
  toastTimer = setTimeout(() => { target.hidden = true; }, error ? 12000 : 7500);
}
function savePersona() { try { sessionStorage.setItem("access-lab-persona", state.actorId); } catch (_) {} }
function closeReview() { $("#review-dialog").close(); state.review = null; }

async function refresh({quiet = false} = {}) {
  const refreshId = ++state.refreshId;
  const actorId = state.actorId;
  try {
    const [workspace, demo] = await Promise.all([api("/api/workspace", undefined, actorId), api("/api/demo/info", undefined, actorId)]);
    if (refreshId !== state.refreshId || actorId !== state.actorId) return;
    state.workspace = workspace;
    state.demo = demo;
    if (!workspace.access.enabled) state.sample = null;
    render();
    renderDemo();
  } catch (error) {
    if (refreshId !== state.refreshId) return;
    if (quiet && state.workspace) return;
    $("#main-content").innerHTML = `<section class="error-panel"><p class="eyebrow">LET’S RECONNECT</p><h1>Your workspace is unavailable.</h1><p>${h(error.message)}</p><button class="button" data-action="refresh">Try again ${icon("refresh")}</button><button class="button text" data-action="restore-persona">Use the Maya demo identity</button></section>`;
    announce(error.message);
  }
}

function statusBadge(status) {
  const labels = {pending:"Awaiting review",payment_failed:"Payment needs attention",approved:"Access granted",denied:"Declined"};
  return `<span class="status-badge ${h(status)}">${h(labels[status] || status)}</span>`;
}
function emptyState(title, message, symbol = "inbox") {
  return `<div class="empty-state"><div class="empty-icon">${icon(symbol)}</div><h3>${h(title)}</h3><p>${h(message)}</p></div>`;
}
function heading(eyebrow, title, subtitle, tag = "") {
  return `<div class="page-heading"><div><p class="eyebrow">${h(eyebrow)}</p><h1>${h(title)}</h1><p class="page-subtitle">${h(subtitle)}</p></div>${tag ? `<span class="heading-tag">${h(tag)}</span>` : ""}</div>`;
}
function summary() {
  const {organization:org, actor, requests} = state.workspace;
  const pending = requests.filter((r) => ["pending","payment_failed"].includes(r.status)).length;
  const used = Math.min(org.assigned_seats, 12);
  const total = Math.min(org.seat_count, 12);
  return `<div class="summary-grid">
    <section class="summary-card" aria-label="Seat usage"><p class="summary-label">Paid seats</p><span class="card-corner">${icon("team")}</span><div class="summary-value">${org.assigned_seats}<small>of ${org.seat_count} assigned</small></div><div class="seats-track" aria-hidden="true">${Array.from({length:total}, (_, i) => `<span class="${i < used ? "used" : ""}"></span>`).join("")}</div></section>
    <section class="summary-card" aria-label="${actor.role === "admin" ? "Pending requests" : "Available seats"}"><p class="summary-label">${actor.role === "admin" ? "Open requests" : "Available seats"}</p><span class="card-corner">${icon(actor.role === "admin" ? "inbox" : "layers")}</span><div class="summary-value">${actor.role === "admin" ? pending : org.available_seats}</div><p class="summary-description">${actor.role === "admin" ? (pending ? `${pending} teammate${pending === 1 ? " needs" : "s need"} your review` : "All requests are resolved") : (org.available_seats ? "Ready for an admin to assign" : "An admin can add another seat")}</p></section>
    <section class="summary-card" aria-label="Next period cost"><p class="summary-label">Next period</p><span class="card-corner">${icon("card")}</span><div class="summary-value">${money(org.next_period_cents).replace(".00", "")}<small>/ month</small></div><p class="summary-description">${org.seat_count} × $12 per seat · sample pricing</p></section>
  </div>`;
}

function render() {
  const w = state.workspace;
  if (!w) return;
  const admin = w.actor.role === "admin";
  const unread = w.notifications.filter((n) => !n.read_at).length;
  const pending = w.requests.filter((r) => ["pending","payment_failed"].includes(r.status)).length;
  const views = [{id:"workspace",label:admin ? "Team access" : "My workspace",icon:admin ? "team" : "home",count:admin ? pending : 0},{id:"activity",label:"Activity",icon:"activity"},{id:"notifications",label:"Notifications",icon:"bell",count:unread}];
  $("#navigation").innerHTML = views.map((v) => `<button class="nav-item ${state.view === v.id ? "active" : ""}" data-action="nav" data-view="${v.id}" ${state.view === v.id ? 'aria-current="page"' : ""}>${icon(v.icon)}<span>${v.label}</span>${v.count ? `<span class="nav-counter">${v.count}</span>` : ""}</button>`).join("");
  $("#sidebar-org").textContent = w.organization.name;
  $("#org-monogram").textContent = initials(w.organization.name);
  $("#breadcrumb-org").textContent = w.organization.name;
  $("#breadcrumb-view").textContent = views.find((v) => v.id === state.view)?.label || "Workspace";
  $("#persona-label").textContent = `${w.actor.name.split(" ")[0]} · ${admin ? "administrator" : "developer"}`;
  $("#top-avatar").textContent = initials(w.actor.name);
  $("#top-avatar").setAttribute("aria-label", `${w.actor.name}, selected demo identity`);
  $("#notifications-button").classList.toggle("has-unread", unread > 0);
  $("#notifications-button").setAttribute("aria-label", `View notifications${unread ? `, ${unread} unread` : ""}`);
  if (state.view === "activity") $("#main-content").innerHTML = activityPage();
  else if (state.view === "notifications") $("#main-content").innerHTML = notificationsPage();
  else $("#main-content").innerHTML = admin ? adminPage() : developerPage();
}

function developerPage() {
  const {actor, access, organization:org, requests} = state.workspace;
  const latest = requests[0];
  const active = latest && ["pending","payment_failed"].includes(latest.status);
  const denied = latest?.status === "denied";
  let title, detail, color, symbol;
  if (access.enabled) {
    title = "Your team seat is ready."; detail = "You have access to the shared review workspace. Time to join your team."; color = "success"; symbol = "checkCircle";
  } else if (latest?.status === "payment_failed") {
    title = "Your request is open. Your admin has the next step."; detail = "A payment issue prevented a new seat from being added. You do not need to send another request."; color = "error"; symbol = "info";
  } else if (active) {
    title = "Your request is with an administrator."; detail = "They will review seat availability and any cost before granting access. We’ll let you know here."; color = "neutral"; symbol = "clock";
  } else if (denied) {
    title = "Your administrator declined this request."; detail = "You can discuss access with your administrator or send a new request when you’re ready."; color = "neutral"; symbol = "info";
  } else if (org.available_seats > 0) {
    title = "A paid seat is available for you."; detail = "Your administrator can assign an available seat at no additional cost. Send them a request to get started."; color = "neutral"; symbol = "info";
  } else {
    title = `All ${org.seat_count} paid seats are currently assigned.`; detail = "You’re invited to the team, but need a seat for the shared review workspace. Your administrator can add one."; color = ""; symbol = "lock";
  }
  const stage = access.enabled ? 3 : active ? 2 : 1;
  const steps = [
    {title:"Your team invitation",copy:`You’re connected to ${org.name}.`,complete:true},
    {title:access.enabled ? "Your request was approved" : active ? "Access request sent" : "Request your workspace access",copy:access.enabled ? "Your administrator assigned a paid seat to you." : active ? "Your administrator can review and approve your request." : "Your administrator reviews the request and confirms any cost.",complete:stage === 3,current:stage < 3,button:!active && !access.enabled},
    {title:access.enabled ? "You’re ready to collaborate" : "Join the shared workspace",copy:access.enabled ? "Your seat unlocks the team’s shared review workspace." : "Your access is ready as soon as a seat is assigned.",complete:stage === 3},
  ];
  return `${heading("YOUR WORKSPACE", access.enabled ? "You’re in. Let’s build something." : "Good work starts with access.", access.enabled ? `You’re all set, ${actor.name.split(" ")[0]}. Your team workspace is ready when you are.` : `Welcome, ${actor.name.split(" ")[0]}. Here’s what you need to join your team’s shared workspace.`, "Team plan")}${summary()}
    <div class="content-grid"><div><section class="panel"><div class="panel-head"><div><h2>Your path to the workspace</h2><p>A clear next step, every step of the way.</p></div><span class="small-label">${access.enabled ? "Access ready" : "Team access"}</span></div><div class="panel-body"><div class="status-line ${color}">${icon(symbol)}<div><strong>${h(title)}</strong><p>${h(detail)}</p></div></div><ol class="access-journey">${steps.map((s, i) => `<li class="journey-step ${s.complete ? "complete" : s.current ? "current" : "future"}"><span class="step-circle">${s.complete ? icon("check") : i + 1}</span><div class="step-text"><h3>${h(s.title)}</h3><p>${h(s.copy)}</p>${s.button ? `<button class="button" data-action="request">${denied ? "Send a new request" : "Request access"} ${icon("arrow")}</button>` : ""}${i === 2 && access.enabled ? `<button class="button" data-action="open-workspace">Open workspace ${icon("arrow")}</button>` : ""}</div></li>`).join("")}</ol>${state.sample ? sampleWorkspace() : ""}</div><div class="panel-bottom">${icon("shield")}<span>Only an administrator can assign seats and approve changes to your plan.</span></div></section>${miniActivity()}</div>
    <div class="side-column"><div><section class="workspace-preview"><p class="eyebrow">WHAT’S WAITING FOR YOU</p><div class="preview-icon">${icon("layers")}</div><h2>A shared space.<br>A connected team.</h2><p>Bring reviews, feedback, and your next great idea together.</p><ul class="feature-list"><li>${icon("check")}Review changes together</li><li>${icon("check")}Keep feedback in context</li><li>${icon("check")}Move work forward as a team</li></ul><div class="preview-foot"><div class="avatar-stack" aria-hidden="true"><span>EB</span><span>AM</span><span>SR</span></div><span>${access.enabled ? "Your team seat is assigned" : "Your team is already here"}</span></div></section><div class="support-note">${icon("info")}<div><h3>No surprise purchases</h3><p>Your administrator sees the seat cost before approving. Sending a request does not trigger a payment.</p></div></div></div></div></div>`;
}

function sampleWorkspace() {
  const sample = state.sample;
  return `<section class="unlocked-workspace" aria-label="Opened shared workspace"><div class="workspace-sample-head"><span>${h(sample.title)}</span>${icon("unlock")}</div><div class="workspace-sample-body"><h3>You’re connected to your team.</h3><p>Fictional preview · no repository connected</p><div class="sample-review">${icon("code")}<span>${h(sample.review.title)}</span><span>${h(sample.review.status)}</span></div></div></section>`;
}

function adminPage() {
  const {requests, organization:org, members} = state.workspace;
  const open = requests.filter((r) => ["pending","payment_failed"].includes(r.status));
  const closed = requests.filter((r) => !["pending","payment_failed"].includes(r.status));
  const newSeat = org.available_seats === 0;
  return `${heading("TEAM ACCESS", "Make room for good work.", "Give teammates the access they need, with the cost clear up front.", "Administrator")}${summary()}
    <div class="content-grid"><div><section class="panel"><div class="panel-head"><div><h2>Access requests ${open.length ? `<span class="small-label">${open.length} open</span>` : ""}</h2><p>Review the people and the price before you approve.</p></div></div>${open.length ? `<div class="request-list">${open.map(requestRow).join("")}</div>` : emptyState("You’re all caught up.", "New teammate requests will appear here when they need workspace access.", "checkCircle")}${closed.length ? `<div class="panel-bottom">${icon("checkCircle")}<span>${closed.length} resolved request${closed.length === 1 ? "" : "s"}. See the activity timeline for details.</span></div>` : ""}</section>
    <section class="panel team-panel"><div class="panel-head"><div><h2>Your team</h2><p>${org.assigned_seats} assigned seats · ${org.available_seats} available</p></div><span class="small-label">${members.length} people</span></div><div class="table-wrap"><table class="team-table"><thead><tr><th scope="col">TEAMMATE</th><th scope="col">ROLE</th><th scope="col">WORKSPACE ACCESS</th></tr></thead><tbody>${members.map((m) => `<tr><td><div class="table-person"><span class="avatar">${h(initials(m.name))}</span><div><strong>${h(m.name)}${m.id === state.actorId ? " (you)" : ""}</strong><small>${h(m.email)}</small></div></div></td><td>${m.role === "admin" ? "Admin" : "Developer"}</td><td>${m.assigned && m.membership === "member" ? `<span class="seat-assigned">${icon("checkCircle")}Seat assigned</span>` : `<span class="muted">Needs a seat</span>`}</td></tr>`).join("")}</tbody></table></div></section></div>
    <div class="side-column"><section class="admin-note"><p class="eyebrow">A LITTLE CLARITY GOES A LONG WAY</p><h2>Know what changes.<br>Before you approve.</h2><p>${newSeat ? "Adding a teammate adds one seat to your plan. You only pay for the time left in this sample billing period." : "There’s room on your current plan. Assign an available paid seat with no additional charge."}</p><div class="cost-example"><div><span>${newSeat ? "One new seat today" : "Use an available seat"}</span><strong>${newSeat ? "$6.00" : "$0.00"}</strong></div><div><span>Then per seat / month</span><strong>$12.00</strong></div><small>Sample pricing · ${newSeat ? "15 of 30 days remaining" : "No new purchase needed"}</small></div><div class="support-note">${icon("shield")}<div><h3>You stay in control</h3><p>Every approval includes a current cost preview and a clear record of the outcome.</p></div></div></section>${miniActivity()}</div></div>`;
}

function requestRow(r) {
  const failed = r.status === "payment_failed";
  return `<article class="request-row"><div class="request-person"><span class="avatar requester">${h(initials(r.requester_name))}</span><div><strong>${h(r.requester_name)}</strong><p class="email">${h(r.requester_email)}</p></div></div>${statusBadge(r.status)}<div class="request-actions"><p>${failed ? "No payment succeeded. The request is ready for another review." : "Needs a seat for the shared review workspace."}</p><button class="button small" data-action="review" data-id="${r.id}">${failed ? "Review & retry" : "Review request"} ${icon("arrow")}</button></div></article>`;
}

function miniActivity() {
  const events = state.workspace.activity.slice(0, 3);
  if (!events.length) return "";
  return `<section class="activity-mini"><h2>Recent activity</h2>${events.map((e) => `<div class="activity-line"><span class="activity-dot"></span><p>${h(e.summary)}</p><time datetime="${h(e.created_at)}">${h(dateLabel(e.created_at))}</time></div>`).join("")}<button class="button text small" data-action="nav" data-view="activity">View all activity ${icon("arrow")}</button></section>`;
}

function activityPage() {
  const {activity, actor, payments = []} = state.workspace;
  const eventNames = {scenario_ready:"Sample workspace",access_requested:"Access request",payment_failed:"Payment needs attention",access_approved:"Access granted",access_denied:"Request declined"};
  return `${heading("WORKSPACE HISTORY", "Every step, accounted for.", "A shared record of requests, decisions, and access changes.")}
    <section class="panel"><div class="panel-head"><div><h2>${actor.role === "admin" ? "Team activity" : "Your activity"}</h2><p>Saved in this workspace. Most recent first.</p></div><span class="small-label">${activity.length} events</span></div>${activity.length ? `<div class="activity-page">${activity.map((e) => `<article class="timeline-item"><span class="timeline-symbol">${icon(e.kind === "access_approved" ? "check" : e.kind === "payment_failed" ? "card" : "activity")}</span><div class="timeline-content"><strong>${h(e.summary)}</strong><p>${h(eventNames[e.kind] || "Workspace update")}${e.request_id ? ` · Request #${e.request_id}` : ""}</p></div><time datetime="${h(e.created_at)}">${h(dateLabel(e.created_at))}</time></article>`).join("")}</div>` : emptyState("Your story starts here.", "Requests and access updates will appear here as they happen.", "activity")}</section>
    ${actor.role === "admin" ? `<section class="panel section-gap"><div class="panel-head"><div><h2>Payment history</h2><p>Simulated payments only. No real money is charged.</p></div><span class="small-label">Sample transactions</span></div>${payments.length ? `<div class="table-wrap"><table class="team-table"><thead><tr><th scope="col">ATTEMPT</th><th scope="col">TEAMMATE</th><th scope="col">AMOUNT</th><th scope="col">OUTCOME</th></tr></thead><tbody>${payments.map((p) => `<tr><td>#${p.id}<br><small>${h(dateLabel(p.created_at))}</small></td><td>${h(p.requester_name)}</td><td>${money(p.amount_cents)}</td><td><span class="status-badge ${p.status === "succeeded" ? "approved" : "payment_failed"}">${p.status === "succeeded" ? "Simulated success" : "Failed · no charge"}</span></td></tr>`).join("")}</tbody></table></div>` : emptyState("No payment attempts yet.", "Purchases and payment failures will appear here. Assigning an available paid seat has no charge.", "card")}</section>` : ""}`;
}

function notificationsPage() {
  const notifications = state.workspace.notifications;
  const unread = notifications.some((n) => !n.read_at);
  return `${heading("YOUR UPDATES", "The next step won’t get lost.", "Stay in the loop as your requests and team access change.")}
    <section class="panel"><div class="panel-head"><div><h2>Notifications</h2><p>In-app updates for ${h(state.workspace.actor.name.split(" ")[0])}. No emails are sent.</p></div>${unread ? `<button class="button secondary small" data-action="read-notifications">Mark all as read</button>` : `<span class="small-label">All read</span>`}</div>${notifications.length ? `<div class="notification-list">${notifications.map((n) => `<article class="notification-item ${n.read_at ? "" : "unread"}"><span class="notification-mark" aria-label="${n.read_at ? "Read" : "Unread"}"></span><div><h3>${h(n.title)}</h3><p>${h(n.message)}</p><time datetime="${h(n.created_at)}">${h(dateLabel(n.created_at))}</time></div></article>`).join("")}</div>` : emptyState("You’re up to date.", "We’ll keep your access updates here when there’s something to share.", "bell")}</section>`;
}

function renderDemo() {
  if (!state.demo) return;
  $("#persona-select").innerHTML = state.demo.personas.map((p) => `<option value="${h(p.id)}" ${p.id === state.actorId ? "selected" : ""}>${h(p.name)} — ${p.role === "admin" ? "administrator" : "developer"} · ${h(p.organization)}</option>`).join("");
  $("#payment-select").value = state.demo.payment_result;
  $("#scenario-select").value = state.demo.scenario;
}

async function openReview(requestId, notice = "") {
  const request = state.workspace.requests.find((r) => r.id === requestId);
  if (!request) return;
  const dialog = $("#review-dialog");
  $("#review-content").innerHTML = `<div class="dialog-heading"><h2 id="review-title">Review access</h2><button class="icon-button" data-action="close-review" aria-label="Close cost review">×</button></div><div class="loading-panel"><span class="loading-dot"></span>Checking the current seat cost…</div>`;
  if (!dialog.open) dialog.showModal();
  try {
    const quote = await api(`/api/requests/${requestId}/quote`);
    if (!dialog.open) return;
    state.review = {request,quote,key:crypto.randomUUID(),notice};
    renderReview();
  } catch (error) {
    closeReview();
    toast(error.message, true);
    await refresh();
  }
}

function renderReview({retryNetwork = false} = {}) {
  const {request:r,quote:q,notice} = state.review;
  const newSeat = q.added_seats > 0;
  $("#review-content").innerHTML = `<div class="dialog-heading"><div><p class="eyebrow">REVIEW ACCESS & COST</p><h2 id="review-title">${newSeat ? "One seat. A clear next step." : "A seat is already waiting."}</h2></div><button class="icon-button" data-action="close-review" aria-label="Close cost review">×</button></div><p class="dialog-intro">${newSeat ? "Approve this request to add a seat and connect your teammate." : "Assign an available paid seat. Your plan total stays the same."}</p><div class="review-person"><span class="avatar requester">${h(initials(r.requester_name))}</span><div><strong>${h(r.requester_name)}</strong><p>Shared review workspace · ${h(state.workspace.organization.name)}</p></div></div>
    <div class="quote-box"><div class="quote-main"><div><p>${newSeat ? "Due now" : "Additional cost today"}</p><small>${newSeat ? "1 new seat · partial billing period" : "1 existing paid seat · no purchase"}</small></div><strong class="amount">${money(q.immediate_cents)}</strong></div><p class="quote-formula">${newSeat ? `${money(q.seat_price_cents)} × ${q.days_remaining} / ${q.period_days} days × 1 new seat = ${money(q.immediate_cents)}` : `Use 1 of ${q.available_seats} available paid seats. No additional payment.`}</p><div class="quote-next"><div>Next ${q.period_days}-day period<small>${q.seats_after} seats × ${money(q.seat_price_cents)} / month</small></div><strong>${money(q.next_period_cents)}</strong></div></div><div class="quote-outcome">${icon("checkCircle")}<p>${h(r.requester_name.split(" ")[0])} gets workspace access immediately after approval. Your team will have <strong>${q.assigned_after} assigned seats out of ${q.seats_after}</strong>.</p></div><p class="simulation-note">Sample pricing and fixed demo billing period. ${newSeat ? "Payment is simulated. No real money will be charged." : "No payment is needed for this assignment."}</p>${notice ? `<p class="dialog-error" role="alert">${h(notice)}</p>` : ""}<div class="dialog-actions"><button class="button text" data-action="confirm-deny">Decline this request</button><button class="button" data-action="approve">${retryNetwork ? "Retry same approval" : newSeat ? `Approve access · ${money(q.immediate_cents)}` : "Assign seat · $0.00"} ${icon("arrow")}</button></div>`;
}

async function approve(button) {
  if (state.busy || !state.review) return;
  state.busy = true;
  button.disabled = true;
  button.textContent = "Confirming access…";
  const review = state.review;
  $("#review-content").querySelectorAll("button").forEach((b) => { b.disabled = true; });
  try {
    const result = await api(`/api/requests/${review.request.id}/approve`, {quote_token:review.quote.token,idempotency_key:review.key});
    closeReview();
    await refresh();
    if (result.outcome === "payment_failed") toast("Simulated payment failed. No charge succeeded and the request is still open. Review it again when ready.", true);
    else toast(result.outcome === "already_approved" ? result.message : `${review.request.requester_name.split(" ")[0]} now has workspace access. ${result.added_seats ? `A ${money(result.charged_cents)} sample payment succeeded.` : "An existing seat was assigned at no extra charge."}`);
  } catch (error) {
    if (error.code === "stale_quote") {
      await refresh();
      await openReview(review.request.id, "The team or request changed while you were reviewing. Check this updated cost and approve again when ready.");
    } else if (["request_closed","request_not_found","admin_required"].includes(error.code)) {
      closeReview();
      toast(error.message, true);
      await refresh();
    } else {
      // Keep the same request, quote, and attempt key when the outcome is unknown.
      state.review = {...review,notice:error.message + " Retrying sends the same approval attempt, so a completed purchase is not repeated."};
      renderReview({retryNetwork:true});
    }
  } finally { state.busy = false; }
}

function confirmDeny() {
  const r = state.review.request;
  $("#review-content").innerHTML = `<div class="dialog-heading"><div><p class="eyebrow">REVIEW YOUR DECISION</p><h2 id="review-title">Decline this access request?</h2></div><button class="icon-button" data-action="close-review" aria-label="Close cost review">×</button></div><p class="dialog-intro">${h(r.requester_name)} will be notified that a seat was not assigned. They can discuss access with you or submit a new request. Your plan and charges will stay the same.</p><div class="dialog-actions"><button class="button secondary" data-action="back-review">Keep reviewing</button><button class="button danger" data-action="deny">Decline request</button></div>`;
}

async function ordinaryAction(button, work) {
  if (state.busy) return;
  state.busy = true;
  const originalLabel = button?.innerHTML;
  if (button) button.disabled = true;
  try { await work(); }
  catch (error) {
    // A failed request must return to its actionable label, not stay "Sending…".
    if (button?.isConnected && originalLabel !== undefined) button.innerHTML = originalLabel;
    toast(error.message, true);
  }
  finally { state.busy = false; if (button?.isConnected) button.disabled = false; }
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button || button.disabled) return;
  const action = button.dataset.action;
  if (action === "nav") {
    state.view = button.dataset.view;
    render();
    $("#main-content").focus({preventScroll:true});
    window.scrollTo({top:0,behavior:"instant"});
  } else if (action === "demo") {
    renderDemo(); $("#demo-dialog").showModal();
  } else if (action === "close-demo") {
    $("#demo-dialog").close();
  } else if (action === "close-review") {
    if (!state.busy) closeReview();
  } else if (action === "refresh") {
    await ordinaryAction(button, async () => { await refresh(); announce("Workspace refreshed."); });
  } else if (action === "restore-persona") {
    state.actorId = "maya"; savePersona(); await refresh();
  } else if (action === "request") {
    await ordinaryAction(button, async () => { button.textContent = "Sending request…"; const result = await api("/api/requests", {}); await refresh(); toast(result.created ? "Your request is sent. Your administrator has the next step." : "Your request is already open. Your administrator has the next step."); });
  } else if (action === "review") {
    await openReview(Number(button.dataset.id));
  } else if (action === "approve") {
    await approve(button);
  } else if (action === "confirm-deny") {
    confirmDeny();
  } else if (action === "back-review") {
    renderReview();
  } else if (action === "deny") {
    await ordinaryAction(button, async () => { const name = state.review.request.requester_name; await api(`/api/requests/${state.review.request.id}/deny`, {}); closeReview(); await refresh(); toast(`${name} was notified that the request was declined.`); });
  } else if (action === "read-notifications") {
    await ordinaryAction(button, async () => { await api("/api/notifications/read", {}); await refresh(); announce("All notifications marked as read."); });
  } else if (action === "open-workspace") {
    await ordinaryAction(button, async () => { state.sample = await api("/api/shared-workspace"); render(); announce("Your shared review workspace is open."); $(".unlocked-workspace")?.scrollIntoView({behavior:"smooth",block:"nearest"}); });
  } else if (action === "reset") {
    if (!$("#reset-confirm").checked) return;
    await ordinaryAction(button, async () => { await api("/api/demo/reset", {scenario:$("#scenario-select").value,confirm:"RESET DEMO"}); state.actorId = "maya"; state.view = "workspace"; state.sample = null; savePersona(); $("#reset-confirm").checked = false; $("#reset-button").disabled = true; $("#demo-dialog").close(); await refresh(); toast("Sample data reset. You’re viewing Maya’s starting point; simulated payments are set to success."); });
    $("#reset-button").disabled = !$("#reset-confirm").checked;
  }
});

$("#persona-select").addEventListener("change", async (event) => {
  if (state.busy) return;
  state.actorId = event.target.value; state.view = "workspace"; state.sample = null; savePersona();
  $("#demo-dialog").close();
  await refresh();
  announce(`Viewing ${state.workspace?.actor.name || "selected identity"}’s perspective.`);
});
$("#payment-select").addEventListener("change", async (event) => {
  const select = event.target;
  await ordinaryAction(select, async () => { const result = await api("/api/demo/payment", {result:select.value}); state.demo.payment_result = result.payment_result; toast(`New simulated purchase attempts will ${result.payment_result === "success" ? "succeed" : "fail"}.`); });
  select.value = state.demo.payment_result;
});
$("#reset-confirm").addEventListener("change", (event) => { $("#reset-button").disabled = !event.target.checked; });
$("#review-dialog").addEventListener("cancel", (event) => { if (state.busy) event.preventDefault(); else state.review = null; });
$("#demo-dialog").addEventListener("cancel", (event) => { if (state.busy) event.preventDefault(); });
$("#refresh-button").innerHTML = icon("refresh");
$("#notifications-button").innerHTML = icon("bell");
$("#demo-button-icon").innerHTML = icon("sliders");
window.addEventListener("focus", () => { if (!state.busy && !$("dialog[open]")) refresh({quiet:true}); });
refresh();
