const content = document.getElementById("content");
const id = getPatientId();

function previewTable(data) {
  return `<div class="scroll"><table>
    <tr>${data.columns.map((column) => `<th>${esc(column)}</th>`).join("")}</tr>
    ${data.rows.map((row) => `<tr>${row.map((value) => `<td>${esc(value)}</td>`).join("")}</tr>`).join("")}
  </table></div>`;
}

function issueCard(problem, index) {
  return `<div class="card problem">
    <h3>${esc(problem.title)}<span class="badge ${esc(problem.severity)}">${esc(problem.severity)}</span></h3>
    <p><b>What remains:</b> ${esc(problem.what)}</p>
    <p><b>Why it matters:</b> ${esc(problem.why)}</p>
    ${problem.fix ? `<p><b>Possible treatment:</b> ${esc(problem.fix.description)}</p>` :
      '<p class="muted">No automatic fix is offered; this may need a rule from you or a manual review.</p>'}
    <form class="guidance-form" data-problem-id="${esc(problem.id)}">
      <label for="question-${index}">What would you like to understand or resolve?</label>
      <textarea id="question-${index}" name="question" rows="3" maxlength="1000"
        placeholder="For example: Why is this still happening, and what should I check?"></textarea>
      <div class="actions"><button class="btn light" type="submit">Get more explanation</button></div>
      <div class="guidance-result status" aria-live="polite"></div>
    </form>
  </div>`;
}

async function load() {
  content.innerHTML = LOADING("Loading your Recovery Report...");
  try {
    const [r, c] = await Promise.all([api("/recovery/" + id), api("/code/" + id)]);
    const row = (label, before, after, lowerIsBetter) => {
      const better = lowerIsBetter ? after < before : after > before;
      return `<tr><td>${label}</td><td>${before}</td><td class="${better ? "better" : ""}">${after}</td></tr>`;
    };
    const p = r.after.preview;
    const problems = r.after.problems || [];
    const remaining = problems.length
      ? `<h2>Issues still present</h2>
        <p class="lead">Ask for an explanation or review more treatments. Any new treatment is previewed before you apply it.</p>
        ${problems.map(issueCard).join("")}`
      : '<div class="card"><h2>No detected issues remain</h2><p>The checks found no remaining problems in this file.</p></div>';
    content.innerHTML = `
      <h1>Recovery Report</h1>
      <p class="lead">Here is how <b>${esc(r.filename)}</b> looks after treatment.</p>
      <div class="card scroll"><table>
        <tr><th>Measure</th><th>Before</th><th>After</th></tr>
        ${row("Health Score", r.before.score, r.after.score, false)}
        ${row("Problems found", r.before.problem_count, r.after.problem_count, true)}
        ${row("Empty cells", r.before.missing_cells, r.after.missing_cells, true)}
        ${row("Duplicate rows", r.before.duplicates, r.after.duplicates, true)}
        ${row("Rows", r.before.rows, r.after.rows, false)}
      </table></div>
      <div class="card"><h3>Treatments applied</h3><ul>${r.applied.map((t) => `<li>${esc(t)}</li>`).join("")}</ul></div>
      ${remaining}
      <div class="card"><h3>Preview of the cleaned data (first 10 rows)</h3>${previewTable(p)}</div>
      <div class="actions">
        <a class="btn" href="/api/download/${id}">Download cleaned file</a>
        ${problems.length ? `<a class="btn light" href="treatment.html?id=${id}">Review treatment plan</a>` : ""}
        <a class="btn light" href="history.html">View history</a>
        <a class="btn light" href="index.html">Check another file</a>
      </div>
      <h2 style="margin-top:2rem">The Python code behind the cleaning</h2>
      <p class="lead">Run this script yourself to repeat the same cleaning and see exactly how it was done.</p>
      <pre id="code">${esc(c.code)}</pre>
      <div class="actions"><button class="btn light" id="copyBtn">Copy code</button>
      <a class="btn light" href="/api/download-code/${id}">Download .py file</a></div>`;
    document.getElementById("copyBtn").addEventListener("click", async (event) => {
      try { await navigator.clipboard.writeText(c.code); event.target.textContent = "Copied"; }
      catch (err) { event.target.textContent = "Select the code and copy it by hand"; }
    });
    content.addEventListener("submit", requestGuidance);
  } catch (err) { showError(content, err.message); }
}

async function requestGuidance(event) {
  const form = event.target.closest(".guidance-form");
  if (!form) return;
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  const result = form.querySelector(".guidance-result");
  button.disabled = true;
  result.innerHTML = LOADING("Preparing issue-specific guidance...");
  try {
    const answer = await api("/guidance/" + id, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        problem_id: form.dataset.problemId,
        question: form.elements.question.value
      })
    });
    result.innerHTML = `<div class="guidance-answer">
      <b>${answer.ai_used ? "AI-assisted explanation" : "Suggested next steps"}</b>
      <p>${esc(answer.answer)}</p>
      ${answer.ai_used ? '<p class="muted">Check suggestions against your data before making changes.</p>' : ""}
    </div>`;
  } catch (err) {
    showError(result, err.message);
  } finally {
    button.disabled = false;
  }
}

load();
