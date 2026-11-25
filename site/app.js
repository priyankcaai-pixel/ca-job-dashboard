"use strict";

const $ = (id) => document.getElementById(id);
const stages = ["Review", "Ready for approval", "Applied", "Interview", "Offer", "Closed"];
const inProgress = ["Applied", "Interview", "Offer"];
const storageKey = "ca-portal-v1";
const state = JSON.parse(localStorage.getItem(storageKey) || '{"added":[],"stages":{},"tracked":{}}');
state.tracked ||= {};
const snapshot = window.vacancies || {jobs: [], status: []};
const workbook = window.workbookJobs || [];

function element(tag, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

function webUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function urlKey(value) {
  const href = webUrl(value);
  if (!href) return "";
  const url = new URL(href);
  let path = url.pathname.replace(/\/$/, "");
  if (url.hostname.endsWith("linkedin.com") && path.includes("/jobs/view/")) {
    path = path.replace(/\/jobs\/view\/.*?(\d+)$/, "/jobs/view/$1");
  }
  const identifier = ["jk", "vjk", "gh_jid"].map((key) => url.searchParams.get(key)).find(Boolean);
  return url.hostname.replace(/^www\./, "") + path + (identifier ? "?" + identifier : "");
}

function jobs() {
  const urls = new Set();
  const liveByUrl = new Map(snapshot.jobs.map((job) => [urlKey(job.url), job]));
  return [...workbook, ...state.added, ...snapshot.jobs, ...Object.values(state.tracked)]
    .filter((job) => {
      const url = urlKey(job.url);
      if (!url) return true;
      if (urls.has(url)) return false;
      urls.add(url);
      return true;
    })
    .map((job) => ({
      ...job,
      caEvidence: job.caEvidence || liveByUrl.get(urlKey(job.url))?.caEvidence,
      stage: state.stages[job.id] || job.stage || "Review",
    }));
}

function save() {
  localStorage.setItem(storageKey, JSON.stringify(state));
}

function populate(id, values, label) {
  const select = $(id);
  const selection = select.value;
  select.replaceChildren(new Option(label, ""));
  for (const value of [...new Set(values.filter(Boolean))].sort()) select.add(new Option(value));
  select.value = [...select.options].some((option) => option.value === selection) ? selection : "";
}

function showDetails(job) {
  $("job-title").textContent = job.role;
  const fields = [
    ["Company", job.company], ["Location", job.location], ["Source", job.source], ["Role family", job.family],
    ["CA requirement", job.caEvidence], ["Stage", job.stage], ["Fit", job.fit], ["Resume status", job.resume], ["Work mode", job.mode],
    ["Experience", job.experience], ["Salary", job.salary], ["Posted", job.posted], ["Freshness", job.freshness],
    ["Listing status", job.listing], ["Next action", job.action], ["Notes", job.notes],
  ];
  $("job-details").replaceChildren();
  for (const [label, value] of fields) {
    if (value) $("job-details").append(element("dt", label), element("dd", value));
  }
  $("job-links").replaceChildren();
  for (const [label, value] of [["Open original listing", job.url], ["Open resume", job.resumeUrl]]) {
    const href = webUrl(value);
    if (!href) continue;
    const link = element("a", label);
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    $("job-links").append(link);
  }
  $("job-dialog").showModal();
}

function summaryList(id, counts) {
  $(id).replaceChildren(...counts.map(([label, count]) => {
    const row = element("li");
    row.append(element("span", label), element("strong", count));
    return row;
  }));
}

function renderSummary(list) {
  const locations = new Map();
  for (const job of list) {
    const location = job.location || "Unspecified";
    locations.set(location, (locations.get(location) || 0) + 1);
  }
  summaryList("location-summary", [...locations].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])));
  summaryList("stage-summary", [...new Set([...stages, ...list.map((j) => j.stage)])].map((stage) =>
    [stage, list.filter((job) => job.stage === stage).length]));
  const now = Date.now();
  summaryList("freshness-summary", [
    ["Posted within 24 hours", list.filter((job) => {
      if (!/^\d{4}-\d{2}-\d{2}T/.test(job.posted || "")) return false;
      const age = now - Date.parse(job.posted);
      return age >= 0 && age < 86400000;
    }).length],
    ["Workbook snapshot: within 24 hours", list.filter((j) => /24\s*(?:hours?|hrs?|h)\b/i.test(j.freshness || "")).length],
    ["Published in imported feed", snapshot.jobs.length],
    ["Closed", list.filter((j) => j.stage === "Closed" || j.listing === "Closed").length],
  ]);
}

function render() {
  const list = jobs();
  populate("location", list.map((j) => j.location), "All locations");
  populate("source", list.map((j) => j.source), "All sources");
  populate("stage", list.map((j) => j.stage), "All stages");
  $("total").textContent = list.length;
  $("live").textContent = snapshot.jobs.length;
  $("progress").textContent = list.filter((j) => inProgress.includes(j.stage)).length;
  $("fit-count").textContent = list.filter((j) => /^(top(?: fit)?|high)$/i.test(j.fit || "")).length;
  $("resume-count").textContent = list.filter((j) => /^(draft( ready)?|ready|drafted)$/i.test(j.resume || "")).length;
  renderSummary(list);
  const query = $("search").value.trim().toLowerCase();
  const shown = list.filter((j) =>
    (!$("qualification").value || j.caEvidence) &&
    [$("location").value, $("source").value, $("stage").value].every((value, index) =>
      !value || value === [j.location, j.source, j.stage][index]) &&
    [j.role, j.company, j.location, j.family, j.notes].join(" ").toLowerCase().includes(query)
  );
  $("count").textContent = shown.length + " of " + list.length;
  const rows = shown.map((job) => {
    const row = element("tr");
    const title = element("td");
    title.append(element("strong", job.role), element("span", job.company));
    const select = element("select");
    select.setAttribute("aria-label", "Application stage for " + job.role + " at " + job.company);
    for (const stage of new Set([...stages, job.stage])) select.add(new Option(stage));
    select.value = job.stage;
    select.addEventListener("change", () => {
      state.stages[job.id] = select.value;
      if (snapshot.jobs.some((entry) => entry.id === job.id)) state.tracked[job.id] = job;
      save();
      render();
      const replacement = [...$("rows").querySelectorAll("select")].find(
        (entry) => entry.getAttribute("aria-label") === select.getAttribute("aria-label")
      );
      (replacement || $("stage")).focus();
    });
    const stage = element("td");
    stage.append(select);
    const action = element("td");
    const button = element("button", "View");
    button.type = "button";
    button.setAttribute("aria-label", "View " + job.role + " at " + job.company);
    button.addEventListener("click", () => showDetails(job));
    action.append(button);
    row.append(title, element("td", job.location || "Unspecified"), element("td", job.source), stage, action);
    ["Role", "Location", "Source", "Stage", "Details"].forEach((label, index) => {
      row.cells[index].dataset.label = label;
    });
    return row;
  });
  if (!rows.length) {
    const row = element("tr");
    const cell = element("td", "No vacancies match your filters.");
    cell.colSpan = 5;
    row.append(cell);
    rows.push(row);
  }
  $("rows").replaceChildren(...rows);
}

for (const id of ["location", "source", "stage", "qualification"]) $(id).addEventListener("change", render);
$("search").addEventListener("input", render);
if (window.location.origin === "http://127.0.0.1:8765") {
  const button = $("reload");
  const note = $("refresh-note");
  button.textContent = "Fetch vacancies";
  note.textContent = "Fetch the latest listings from the configured company feeds.";
  button.addEventListener("click", async () => {
    button.disabled = true;
    note.textContent = "Fetching vacancies...";
    try {
      const response = await fetch("/refresh", {method: "POST"});
      if (!response.ok) throw new Error();
      window.location.reload();
    } catch {
      note.textContent = "Could not refresh vacancies. Try again or check the local server.";
      button.disabled = false;
    }
  });
} else {
  $("refresh-note").textContent = "This page shows the latest published vacancy snapshot.";
  $("reload").addEventListener("click", () => window.location.reload());
}
$("open-add").addEventListener("click", () => $("add-dialog").showModal());
$("cancel-add").addEventListener("click", () => $("add-dialog").close());
$("close-job").addEventListener("click", () => $("job-dialog").close());
$("add-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const data = Object.fromEntries([...new FormData(event.currentTarget)].map(([key, value]) => [key, value.trim()]));
  const url = webUrl(data.url);
  if (!data.role || !data.company || !url) {
    $("add-error").textContent = "Enter a role, company and valid web address.";
    return;
  }
  if (jobs().some((job) => urlKey(job.url) === urlKey(url))) {
    $("add-error").textContent = "This listing is already in your dashboard.";
    return;
  }
  state.added.unshift({...data, id: "manual:" + url, url, stage: "Review"});
  save();
  event.currentTarget.reset();
  $("add-error").textContent = "";
  $("add-dialog").close();
  for (const id of ["search", "location", "source", "stage"]) $(id).value = "";
  $("qualification").value = data.caEvidence ? "required" : "";
  render();
});

$("export-tracker").addEventListener("click", () => {
  const saved = [...workbook, ...state.added, ...Object.values(state.tracked)];
  const file = new Blob([JSON.stringify({version: 1, jobs: saved, stages: state.stages})], {type: "application/json"});
  const url = URL.createObjectURL(file);
  const link = element("a");
  link.href = url;
  link.download = "ca-job-tracker.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

$("import-tracker").addEventListener("change", async (event) => {
  const input = event.currentTarget;
  if (!input.files.length) return;
  try {
    const data = JSON.parse(await input.files[0].text());
    if (data.version !== 1 || !Array.isArray(data.jobs) || !data.stages || typeof data.stages !== "object" ||
        !data.jobs.every((job) => job && typeof job.id === "string" && typeof job.role === "string" && typeof job.company === "string")) {
      throw new Error("Invalid tracker");
    }
    const saved = new Map([...state.added, ...data.jobs].map((job) => [job.id, job]));
    const workbookIds = new Set(workbook.map((job) => job.id));
    state.added = [...saved.values()].filter((job) => !workbookIds.has(job.id));
    state.stages = {...state.stages, ...Object.fromEntries(Object.entries(data.stages).filter(([, stage]) => typeof stage === "string"))};
    save();
    $("qualification").value = "";
    render();
    $("transfer-status").textContent = "Tracker imported.";
  } catch {
    $("transfer-status").textContent = "Choose a valid CA Job Dashboard tracker file.";
  } finally {
    input.value = "";
  }
});

for (const feed of snapshot.status) {
  const checked = feed.checked ? " Â· Last successful refresh " + new Date(feed.checked).toLocaleString() : "";
  const status = feed.ok ? feed.count + " matches" : "Refresh failed Â· " + feed.count + " cached matches";
  $("feeds").append(element("li", feed.label + " Â· " + status + checked));
}
render();

