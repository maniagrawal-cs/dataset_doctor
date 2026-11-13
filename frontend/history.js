const content = document.getElementById("content");

function eventDetails(event) {
  const details = event.details || {};
  if (event.event_type === "uploaded") {
    return `<p>Uploaded ${details.rows} rows and ${details.columns} columns.</p>`;
  }
  if (event.event_type === "diagnosed") {
    return `<p>Health score: ${details.score}; issues found: ${details.problem_count}.</p>`;
  }
  if (event.event_type === "treated") {
    return `<p>${details.before_problem_count} issues before; ${details.after_problem_count} after. ` +
      `Health score: ${details.before_score} → ${details.after_score}.</p>` +
      `<p>Treatments: ${(details.fixes || []).map(esc).join(", ")}</p>`;
  }
  if (event.event_type === "guidance") {
    return `<p><b>Issue:</b> ${esc(details.problem_title)}</p>
      <p><b>Your question:</b> ${esc(details.question)}</p>
      <p class="history-answer"><b>Guidance:</b> ${esc(details.answer)}</p>`;
  }
  return "";
}

function renderRecord(record) {
  const timeline = record.events.map((event) => `
    <div class="history-event">
      <div class="history-event-heading"><b>${esc(event.event_type)}</b><time>${esc(event.created_at)}</time></div>
      ${eventDetails(event)}
    </div>`).join("");
  const reportLink = record.status === "Treated"
    ? `<a class="btn light" href="recovery.html?id=${record.id}">Open recovery report</a>`
    : `<a class="btn light" href="diagnosis.html?id=${record.id}">Open diagnosis</a>`;
  return `<article class="card">
    <div class="history-title">
      <div><h2>${esc(record.filename)}</h2><p class="muted">Uploaded ${esc(record.created_at)}</p></div>
      <span class="badge ${record.status === "Treated" ? "Mild" : "Moderate"}">${esc(record.status)}</span>
    </div>
    <div class="stats">
      ${record.before_score != null ? `<span class="stat">Initial score: ${record.before_score}</span>` : ""}
      ${record.after_score != null ? `<span class="stat">Latest score: ${record.after_score}</span>` : ""}
      ${record.remaining_count != null ? `<span class="stat">Remaining issues: ${record.remaining_count}</span>` : ""}
    </div>
    <h3 class="history-subtitle">Activity</h3>
    ${timeline || '<p class="muted">No activity details were recorded for this older check-up.</p>'}
    <div class="actions">${reportLink}</div>
  </article>`;
}

async function load() {
  content.innerHTML = LOADING("Loading your check-up history...");
  try {
    const records = await api("/history");
    content.innerHTML = `<h1>Your history</h1>
      <p class="lead">Review previous uploads, treatments, and follow-up guidance.</p>
      ${records.length
        ? records.map(renderRecord).join("")
        : '<div class="card"><h2>No check-ups yet</h2><p>Upload a dataset to begin building your history.</p></div>'}
      <div class="actions"><a class="btn" href="index.html">Check a dataset</a></div>`;
  } catch (err) { showError(content, err.message); }
}

load();
