const drop = document.getElementById("drop");
const input = document.getElementById("fileInput");
const startBtn = document.getElementById("startBtn");
const status = document.getElementById("status");
let chosenFile = null;

function choose(file) {
  if (!file) return;
  if (!/\.(csv|xlsx|xls)$/i.test(file.name)) { showError(status, "Please choose a .csv, .xlsx or .xls file."); return; }
  chosenFile = file;
  document.getElementById("fileName").textContent = "Selected: " + file.name;
  startBtn.disabled = false;
  status.innerHTML = "";
}
drop.addEventListener("click", () => input.click());
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); } });
input.addEventListener("change", () => choose(input.files[0]));
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); choose(e.dataTransfer.files[0]); });

startBtn.addEventListener("click", async () => {
  startBtn.disabled = true;
  status.innerHTML = LOADING("The doctor is examining your data...");
  const form = new FormData();
  form.append("file", chosenFile);
  try {
    const result = await api("/upload", { method: "POST", body: form });
    location.href = "diagnosis.html?id=" + result.patient_id;
  } catch (err) {
    showError(status, err.message);
    startBtn.disabled = false;
  }
});
