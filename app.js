const statusEl = document.querySelector("#status");
const resultsEl = document.querySelector("#results");
const rerunButton = document.querySelector("#rerun");

function formatCriticalStep(step) {
  if (!step) return "none";
  const index = step.step_index === null || step.step_index === undefined ? "n/a" : `step ${step.step_index}`;
  return `${step.pattern} at ${index}: ${step.evidence || "no quote"}`;
}

function renderResult(item) {
  const patterns = item.failure_patterns.map((pattern) => pattern.name);
  const article = document.createElement("article");
  article.className = "result";
  article.innerHTML = `
    <h3>${item.example_label || item.run_id || item.task_family}</h3>
    <dl class="kv">
      <dt>Outcome</dt><dd>${item.outcome}</dd>
      <dt>Final failure</dt><dd>${item.final_failure || "none"}</dd>
      <dt>Critical step</dt><dd>${formatCriticalStep(item.critical_step)}</dd>
      <dt>Repair hint</dt><dd>${item.repair_hint || "none"}</dd>
    </dl>
    <div class="pill-row">${patterns.map((name) => `<span class="pill">${name}</span>`).join("")}</div>
  `;
  return article;
}

async function runDiagnostics() {
  rerunButton.disabled = true;
  statusEl.textContent = "Running examples through /api/diagnose...";
  resultsEl.replaceChildren();

  try {
    const response = await fetch("/api/diagnose?example=all", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || `Request failed with ${response.status}`);
    }
    const examples = payload.examples || [];
    for (const item of examples) {
      resultsEl.appendChild(renderResult(item));
    }
    statusEl.textContent = `Completed ${examples.length} diagnosis runs on Vercel.`;
  } catch (error) {
    statusEl.textContent = `Diagnosis run failed: ${error.message}`;
  } finally {
    rerunButton.disabled = false;
  }
}

rerunButton.addEventListener("click", runDiagnostics);
runDiagnostics();
