"""Talks to the Google Gemini API. If anything goes wrong we return None and the app keeps working."""
import json
import os
import requests


def ask_gemini(prompt, as_json=False):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if as_json:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    try:
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=90)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as error:  # network, quota, bad key ...
        print("Gemini is not available right now:", error)
        return None


def add_explanations(diagnosis, sample_values):
    """Ask Gemini for a friendly summary and a plain-language explanation of each problem."""
    if not diagnosis["problems"]:
        return diagnosis
    facts = {
        "rows": diagnosis["rows"], "columns": diagnosis["columns"], "health_score": diagnosis["score"],
        "sample_values": sample_values,
        "problems": [{"id": p["id"], "title": p["title"], "count": p["count"], "severity": p["severity"]}
                     for p in diagnosis["problems"]],
    }
    prompt = (
        "You are a friendly, calm data doctor explaining a dataset check-up to a complete beginner. "
        "Use very simple language and no jargon. Below are measurements made by software (they are correct, "
        "do not change any numbers).\n"
        f"{json.dumps(facts, default=str)[:12000]}\n\n"
        'Reply ONLY with JSON in this exact shape: {"summary": "2-3 warm sentences about the overall health", '
        '"problems": {"<problem id>": {"what": "one or two sentences: what is wrong", '
        '"why": "one or two sentences: why it is a problem"}}}. Include every problem id.')
    text = ask_gemini(prompt, as_json=True)
    if not text:
        return diagnosis
    try:
        data = json.loads(text)
        diagnosis["summary"] = data.get("summary") or diagnosis["summary"]
        for p in diagnosis["problems"]:
            info = data.get("problems", {}).get(p["id"])
            if info:
                p["what"] = info.get("what") or p["what"]
                p["why"] = info.get("why") or p["why"]
        diagnosis["ai_used"] = True
    except Exception as error:
        print("Could not read Gemini's answer:", error)
    return diagnosis


def explain_problem(problem, question):
    """Provide follow-up guidance using issue metadata, without sending row values."""
    fix = problem.get("fix")
    fallback = (
        f"This issue is still present: {problem['what']} {problem['why']} "
        + (f"A possible next step is: {fix['description']} "
           "Preview the change and confirm it is appropriate before applying it."
           if fix else
           "There is no automatic fix for this issue because an automatic change may be unsafe. "
           "Review the source data or define the rule you want the data to follow.")
    )
    facts = {
        "issue": {
            "title": problem["title"],
            "severity": problem["severity"],
            "count": problem["count"],
            "what": problem["what"],
            "why": problem["why"],
            "suggested_fix": fix["description"] if fix else None,
        },
        "user_question": question,
    }
    prompt = (
        "You are Dataset Doctor, helping a beginner understand a remaining data-quality issue. "
        "Use only the supplied issue facts; do not invent data values or claim the issue is fixed. "
        "Explain the likely meaning and give cautious, practical next steps. If a safe automatic "
        "fix is not offered, say why and suggest a manual review. Keep the answer under 150 words.\n"
        f"{json.dumps(facts, default=str)[:5000]}\n\n"
        "Reply with plain text only.")
    text = ask_gemini(prompt)
    if text and text.strip():
        return text.strip(), True
    return fallback, False
