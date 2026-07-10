const states = ["Intent", "Context", "Contract", "Plan", "Simulation", "Approval", "Execution", "Verification", "Evidence", "MemoryPatch", "Evaluation", "Completed"];

function esc(value) {
  return String(value ?? "").replace(/[&<>\"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[char]));
}

function stateRail(state) {
  return states.map((item) => `<span class="stage ${item === state ? "active" : states.indexOf(item) < states.indexOf(state) ? "done" : ""}">${item}</span>`).join("");
}

async function load() {
  const response = await fetch("/api/runtime/overview");
  if (!response.ok) throw new Error(`API ${response.status}`);
  const data = await response.json();
  document.querySelector("#system-badge").textContent = `${data.system.mode} · human control on`;
  document.querySelector("#evidence-count").textContent = data.evidence.length;
  document.querySelector("#missions").innerHTML = data.missions.length ? data.missions.slice().reverse().map((mission) => `
    <div class="mission-card" data-mission-id="${esc(mission.mission_id)}">
      <div class="row"><b>${esc(mission.spec?.title || mission.mission_id)}</b><span class="status">${esc(mission.state)}</span></div>
      <p>${esc(mission.spec?.objective)}</p>
      <div class="rail">${stateRail(mission.state)}</div>
      <div class="row tiny"><span>${esc(mission.mission_id)}</span><span>${mission.paused ? "Paused" : "Live"}</span></div>
    </div>`).join("") : `<div class="empty">Create a mission through the CLI or API.</div>`;
  document.querySelector("#approvals").innerHTML = data.approvals.filter((item) => item.status === "pending").map((item) => `
    <div class="approval-card"><div class="row"><b>${esc(item.action)}</b><span class="risk">${esc(item.risk_level)}</span></div><p>${esc(item.rationale)}</p><small>${esc(item.mission_id)}</small></div>`).join("") || `<div class="empty">No pending approvals.</div>`;
  document.querySelector("#evidence").innerHTML = data.evidence.slice().reverse().slice(0, 10).map((item) => `<div class="evidence-row"><span class="dot"></span><div><b>${esc(item.title)}</b><small>${esc(item.kind)} · ${esc(item.sha256).slice(0, 12)}…</small></div></div>`).join("") || `<div class="empty">No evidence yet.</div>`;
  document.querySelector("#tools").innerHTML = data.tools.slice().reverse().slice(0, 10).map((item) => `<div class="evidence-row"><span class="dot blue"></span><div><b>${esc(item.tool_name)}</b><small>${esc(item.status)} · ${esc(item.duration_ms)}ms</small></div></div>`).join("") || `<div class="empty">No tool calls yet.</div>`;
  document.querySelector("#layers").innerHTML = ["Intent", "Context", "Contract", "Plan", "Reasoning", "Tools", "Execution", "Verification", "Evidence", "Memory", "Governance", "Evolution"].map((item, index) => `<span>L${String(index + 1).padStart(2, "0")} ${item}</span>`).join("");
}

load().catch((error) => { document.querySelector("#system-badge").textContent = "API offline"; console.warn(error); });
setInterval(() => load().catch(() => {}), 5000);
