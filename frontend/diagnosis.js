const content = document.getElementById("content");
const id = getPatientId();

async function load() {
  content.innerHTML = LOADING("Writing your Diagnosis Report...");
  try {
    const d = await api("/diagnose/" + id);
    const color = d.score >= 80 ? "var(--green)" : d.score >= 60 ? "var(--amber)" : "var(--red)";
    const problems = d.problems.map((p) => `
      <div class="card problem">
        <h3>${esc(p.title)}<span class="badge ${esc(p.severity)}">${esc(p.severity)}</span></h3>
        <p><b>What is wrong:</b> ${esc(p.what)}</p>
        <p><b>Why it matters:</b> ${esc(p.why)}</p>
      </div>`).join("");
    content.innerHTML = `
      <h1>Diagnosis Report</h1>
      <div class="card score-row">
        <div class="ring" style="--pct:${d.score}; --color:${color}"><div><span><b>${d.score}</b><small>out of 100</small></span></div></div>
        <div>
          <h2>${esc(d.label)}</h2>
          <p>${esc(d.summary)}</p>
          <div class="stats">
            <span class="stat">${d.rows} rows</span><span class="stat">${d.cols} columns</span>
            <span class="stat">${d.missing_cells} empty cells</span><span class="stat">${d.duplicates} duplicate rows</span>
            <span class="stat">${d.problem_count} problems</span>
          </div>
          ${d.ai_used ? "" : '<p class="muted" style="margin-top:.8rem">Explanations are the built-in ones (Gemini was not used).</p>'}
        </div>
      </div>
      ${problems || '<div class="card"><h3>No problems found</h3><p>Your dataset is already in great shape.</p></div>'}
      <div class="actions">${d.fixes.length ? `<a class="btn" href="treatment.html?id=${id}">See treatment plan</a>` : ""}
      <a class="btn light" href="index.html">Check another file</a></div>`;
  } catch (err) { showError(content, err.message); }
}
load();
