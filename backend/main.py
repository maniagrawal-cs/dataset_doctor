"""Dataset Doctor: the FastAPI app. Run with:  uvicorn backend.main:app --reload"""
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).parent / ".env")  # loads GEMINI_API_KEY

# Support both launch styles:
#   cd backend && uvicorn main:app --reload
#   project root && uvicorn backend.main:app --reload
try:
    from . import code_generator, database, examiner, gemini_service, treatments
except ImportError:
    import code_generator
    import database
    import examiner
    import gemini_service
    import treatments

BASE = Path(__file__).parent.parent
UPLOADS, OUTPUTS = BASE / "uploads", BASE / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)
database.init_db()

app = FastAPI(title="Dataset Doctor")


def get_patient(patient_id):
    patient = database.get_patient(patient_id)
    if not patient:
        raise HTTPException(404, "We could not find that patient. Please upload your file again.")
    return patient


def previously_applied_fixes(patient):
    fixes = patient.get("applied_fixes") or []
    if fixes:
        return fixes
    diagnosis = patient.get("diagnosis") or {}
    applied_titles = set(patient.get("applied") or [])
    fixes = [fix for fix in diagnosis.get("fixes", []) if fix["title"] in applied_titles]
    return sorted(fixes, key=lambda fix: treatments.ORDER.index(fix["type"]))


MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    original_name = Path(file.filename or "dataset").name
    ext = Path(original_name).suffix.lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(400, "Please upload a .csv, .xlsx or .xls file.")
    saved = UPLOADS / f"{uuid.uuid4().hex}{ext}"
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File is too large. Please upload a file smaller than 25 MB.")
        if not content:
            raise HTTPException(400, "The uploaded file is empty.")
        saved.write_bytes(content)
    finally:
        await file.close()
    try:
        df = examiner.load_df(saved)
    except Exception:
        saved.unlink(missing_ok=True)
        raise HTTPException(400, "We could not read that file. Is it a valid CSV or Excel file?")
    if df.empty:
        saved.unlink(missing_ok=True)
        raise HTTPException(400, "That file has no data rows.")
    patient_id = database.create_patient(original_name, str(saved))
    database.add_history(patient_id, "uploaded", {"rows": len(df), "columns": len(df.columns)})
    return {"patient_id": patient_id, "rows": len(df), "columns": len(df.columns)}


@app.get("/api/diagnose/{patient_id}")
def diagnose(patient_id: int):
    patient = get_patient(patient_id)
    if patient["diagnosis"]:  # already done, reuse it
        return patient["diagnosis"]
    df = examiner.load_df(patient["original_path"])
    diagnosis = examiner.examine(df)
    samples = {c: [str(v)[:30] for v in df[c].dropna().unique()[:3]] for c in df.columns[:40]}
    diagnosis = gemini_service.add_explanations(diagnosis, samples)
    database.update_patient(patient_id, diagnosis=diagnosis)
    database.add_history(patient_id, "diagnosed", {
        "score": diagnosis["score"], "problem_count": diagnosis["problem_count"]})
    return diagnosis


@app.get("/api/treatment-plan/{patient_id}")
def treatment_plan(patient_id: int):
    patient = get_patient(patient_id)
    if patient["cleaned_path"]:
        current = examiner.load_df(patient["cleaned_path"])
        diagnosis = examiner.examine(current)
    else:
        diagnosis = diagnose(patient_id)
    applied_fixes = previously_applied_fixes(patient)
    return {
        "fixes": diagnosis["fixes"],
        "score": diagnosis["score"],
        "applied_fix_ids": [fix["id"] for fix in applied_fixes],
    }


class TreatRequest(BaseModel):
    fix_ids: list[str]


def selected_fixes(diagnosis, fix_ids):
    chosen = [fix for fix in diagnosis["fixes"] if fix["id"] in fix_ids]
    if not chosen:
        raise HTTPException(400, "Please select at least one treatment.")
    return chosen


@app.post("/api/preview/{patient_id}")
def preview_treatment(patient_id: int, body: TreatRequest):
    patient = get_patient(patient_id)
    if patient["cleaned_path"]:
        original = examiner.load_df(patient["cleaned_path"])
        diagnosis = examiner.examine(original)
    else:
        diagnosis = diagnose(patient_id)
        original = examiner.load_df(patient["original_path"])
    chosen = selected_fixes(diagnosis, body.fix_ids)
    cleaned, _ = treatments.apply_fixes(original, chosen)
    return {
        "before": examiner.brief(diagnosis),
        "after": examiner.brief(examiner.examine(cleaned)),
        "before_preview": examiner.preview(original, n=5),
        "after_preview": examiner.preview(cleaned, n=5),
    }


@app.post("/api/treat/{patient_id}")
def treat(patient_id: int, body: TreatRequest):
    patient = get_patient(patient_id)
    if patient["cleaned_path"]:
        original = examiner.load_df(patient["cleaned_path"])
        diagnosis = examiner.examine(original)
    else:
        diagnosis = diagnose(patient_id)
        original = examiner.load_df(patient["original_path"])
    chosen = selected_fixes(diagnosis, body.fix_ids)
    ordered_chosen = sorted(chosen, key=lambda fix: treatments.ORDER.index(fix["type"]))
    cleaned, done = treatments.apply_fixes(original, ordered_chosen)

    out_path = OUTPUTS / f"cleaned_{patient_id}_{code_generator.output_name(patient['filename'])}"
    if out_path.suffix == ".csv":
        cleaned.to_csv(out_path, index=False)
    else:
        cleaned.to_excel(out_path, index=False)

    before = examiner.brief(diagnosis)
    after = examiner.examine(cleaned)
    after["preview"] = examiner.preview(cleaned)
    applied_fixes = previously_applied_fixes(patient)
    applied_fixes.extend(ordered_chosen)
    applied_fix_ids = {fix["id"] for fix in applied_fixes}
    applied_titles = list(patient["applied"] or [])
    for title in done:
        if title not in applied_titles:
            applied_titles.append(title)
    code = code_generator.build_code(patient["filename"], applied_fixes)
    database.update_patient(
        patient_id, cleaned_path=str(out_path), applied=applied_titles,
        applied_fix_ids=sorted(applied_fix_ids), applied_fixes=applied_fixes,
        after=after, code=code)
    database.add_history(patient_id, "treated", {
        "fixes": done,
        "before_score": before["score"],
        "after_score": after["score"],
        "before_problem_count": before["problem_count"],
        "after_problem_count": after["problem_count"],
    })
    return {"ok": True}


@app.get("/api/recovery/{patient_id}")
def recovery(patient_id: int):
    patient = get_patient(patient_id)
    if not patient["after"]:
        raise HTTPException(400, "This patient has not been treated yet.")
    after = patient["after"]
    if "problems" not in after:
        cleaned = examiner.load_df(patient["cleaned_path"])
        after = examiner.examine(cleaned)
        after["preview"] = examiner.preview(cleaned)
        database.update_patient(patient_id, after=after)
    return {"filename": patient["filename"], "before": examiner.brief(patient["diagnosis"]),
            "after": after, "applied": patient["applied"]}


class GuidanceRequest(BaseModel):
    problem_id: str
    question: str = ""


@app.post("/api/guidance/{patient_id}")
def guidance(patient_id: int, body: GuidanceRequest):
    patient = get_patient(patient_id)
    if not patient["cleaned_path"]:
        raise HTTPException(400, "Apply a treatment before requesting follow-up guidance.")
    question = body.question.strip()
    if len(question) > 1000:
        raise HTTPException(400, "Please keep your question under 1,000 characters.")
    cleaned = examiner.load_df(patient["cleaned_path"])
    diagnosis = examiner.examine(cleaned)
    problem = next((p for p in diagnosis["problems"] if p["id"] == body.problem_id), None)
    if not problem:
        raise HTTPException(404, "That issue is no longer present in the cleaned dataset.")
    question = question or "Please explain why this issue remains and suggest safe next steps."
    answer, ai_used = gemini_service.explain_problem(problem, question)
    database.add_history(patient_id, "guidance", {
        "problem_title": problem["title"], "question": question, "answer": answer})
    return {"problem_title": problem["title"], "answer": answer, "ai_used": ai_used}


@app.get("/api/history")
def history():
    results = []
    for patient in database.get_history():
        diagnosis = patient["diagnosis"] or {}
        after = patient["after"] or {}
        results.append({
            "id": patient["id"],
            "filename": patient["filename"],
            "created_at": patient["created_at"],
            "status": "Treated" if after else "Diagnosed" if diagnosis else "Uploaded",
            "before_score": diagnosis.get("score"),
            "after_score": after.get("score"),
            "remaining_count": after.get("problem_count"),
            "applied": patient["applied"] or [],
            "events": patient["events"],
        })
    return results


@app.get("/api/code/{patient_id}")
def get_code(patient_id: int):
    patient = get_patient(patient_id)
    if not patient["code"]:
        raise HTTPException(400, "This patient has not been treated yet.")
    return {"code": patient["code"]}


@app.get("/api/download/{patient_id}")
def download(patient_id: int):
    patient = get_patient(patient_id)
    if not patient["cleaned_path"]:
        raise HTTPException(400, "This patient has not been treated yet.")
    return FileResponse(patient["cleaned_path"], filename=code_generator.output_name(patient["filename"]))


@app.get("/api/download-code/{patient_id}")
def download_code(patient_id: int):
    patient = get_patient(patient_id)
    if not patient["code"]:
        raise HTTPException(400, "This patient has not been treated yet.")
    return Response(patient["code"], media_type="text/x-python",
                    headers={"Content-Disposition": 'attachment; filename="clean_dataset.py"'})


# Serve the website. This must come LAST so it does not hide the /api routes.
app.mount("/", StaticFiles(directory=BASE / "frontend", html=True), name="frontend")
