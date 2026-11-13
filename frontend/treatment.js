const content = document.getElementById("content");
const id = getPatientId();

function previewTable(data) {
  return `<div class="scroll"><table>
    <tr>${data.columns.map((column) => `<th>${esc(column)}</th>`).join("")}</tr>
    ${data.rows.map((row) => `<tr>${row.map((value) => `<td>${esc(value)}</td>`).join("")}</tr>`).join("")}
  </table></div>`;
}

async function load() {
  content.innerHTML = LOADING("Preparing your Treatment Plan...");
  try {
    const plan = await api("/treatment-plan/" + id);
    const hasAppliedFixes = plan.applied_fix_ids.length > 0;
    if (!plan.fixes.length) {
      content.innerHTML = `<div class="card"><h2>No safe automatic fixes available</h2>
        <p>Review the remaining issue guidance to decide what to check or change manually.</p>
        <div class="actions">
          ${hasAppliedFixes ? `<a class="btn light" href="recovery.html?id=${id}">Back to recovery report</a>` : `<a class="btn light" href="diagnosis.html?id=${id}">Back to diagnosis</a>`}
          <a class="btn light" href="history.html">View history</a>
        </div></div>`;
      return;
    }
    const items = plan.fixes.map((f) => {
      const previouslyApplied = plan.applied_fix_ids.includes(f.id);
      return `
        <label class="card fix">
          <input type="checkbox" value="${esc(f.id)}" ${f.default && !previouslyApplied ? "checked" : ""}>
          <span><h3>${esc(f.title)}</h3><p>${esc(f.description)}</p><p class="muted"><i>Why this fix?</i> ${esc(f.why)}</p>
            ${previouslyApplied ? '<p class="muted">This fix was already applied, but the issue remains. Select it only if you want to try it again.</p>' : ""}
          </span>
        </label>`;
    }).join("");
    content.innerHTML = `
      <h1>Treatment Plan</h1>
      <p class="lead">${hasAppliedFixes
        ? "Your previous treatments are already included. Select new treatments to apply them to the currently cleaned file."
        : "Tick the treatments you approve. Nothing happens to your data until you press the button."}</p>
      ${items}
      <div class="actions"><button class="btn light" id="previewBtn">Preview selected changes</button>
      <button class="btn" id="applyBtn">Apply selected treatments</button>
      <a class="btn light" href="diagnosis.html?id=${id}">Back to diagnosis</a></div>
      <div id="previewResult"></div>
      <div class="status" id="status" aria-live="polite"></div>`;
    document.getElementById("previewBtn").addEventListener("click", preview);
    document.getElementById("applyBtn").addEventListener("click", apply);
    content.addEventListener("change", (event) => {
      if (event.target.matches('input[type="checkbox"]')) {
        document.getElementById("previewResult").replaceChildren();
      }
    });
  } catch (err) { showError(content, err.message); }
}

async function preview() {
  const result = document.getElementById("previewResult");
  const status = document.getElementById("status");
  const btn = document.getElementById("previewBtn");
  const ids = [...document.querySelectorAll("input[type=checkbox]:checked")].map((c) => c.value);
  if (!ids.length) { showError(status, "Please tick at least one treatment."); return; }
  btn.disabled = true;
  result.innerHTML = LOADING("Preparing a preview. Your files will not be changed...");
  status.replaceChildren();
  try {
    const report = await api("/preview/" + id, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fix_ids: ids })
    });
    result.innerHTML = `
      <div class="card">
        <h2>Preview only — nothing has been saved</h2>
        <p class="muted">Compare the first five rows and dataset checks before deciding to apply these changes.</p>
        <div class="stats">
          <span class="stat">Rows: ${report.before.rows} → ${report.after.rows}</span>
          <span class="stat">Empty cells: ${report.before.missing_cells} → ${report.after.missing_cells}</span>
          <span class="stat">Duplicates: ${report.before.duplicates} → ${report.after.duplicates}</span>
          <span class="stat">Health score: ${report.before.score} → ${report.after.score}</span>
        </div>
        <div class="preview-grid">
          <section><h3>Before</h3>${previewTable(report.before_preview)}</section>
          <section><h3>After selected changes</h3>${previewTable(report.after_preview)}</section>
        </div>
      </div>`;
  } catch (err) { showError(status, err.message); result.replaceChildren(); }
  finally { btn.disabled = false; }
}

async function apply() {
  const status = document.getElementById("status");
  const btn = document.getElementById("applyBtn");
  const ids = [...document.querySelectorAll("input[type=checkbox]:checked")].map((c) => c.value);
  if (!ids.length) { showError(status, "Please tick at least one treatment."); return; }
  btn.disabled = true;
  status.innerHTML = LOADING("Treating your dataset and writing the Python code...");
  try {
    await api("/treat/" + id, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fix_ids: ids }) });
    location.href = "recovery.html?id=" + id;
  } catch (err) { showError(status, err.message); btn.disabled = false; }
}
load();
