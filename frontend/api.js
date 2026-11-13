// Small helpers shared by every page.
async function api(path, options) {
  const res = await fetch("/api" + path, options);
  let data = null;
  try { data = await res.json(); } catch (e) { /* not JSON */ }
  if (!res.ok) throw new Error((data && data.detail) || "Something went wrong. Please try again.");
  return data;
}
function getPatientId() { return new URLSearchParams(location.search).get("id"); }
function esc(text) {
  const d = document.createElement("div");
  d.textContent = text == null ? "" : String(text);
  return d.innerHTML.replace(/"/g, "&quot;");
}
function showError(box, message) {
  box.innerHTML = `<p class="error">${esc(message)}</p>`;
}
const LOADING = (text) => `<div class="loading"><div class="spinner"></div>${esc(text)}</div>`;
