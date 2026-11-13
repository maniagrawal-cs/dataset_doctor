"""The Examiner: uses pandas to measure what is wrong with a dataset."""
import warnings
import pandas as pd

NUMBER_CLEANUP = r"[,$€£%\s]"  # characters removed when turning text into numbers


def load_df(path):
    """Read a CSV or Excel file into a pandas DataFrame."""
    path = str(path)
    if path.lower().endswith(".csv"):
        try:
            df = pd.read_csv(path)
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="latin-1")
    else:
        df = pd.read_excel(path)
    df.columns = [str(c) for c in df.columns]
    return df


def _severity(pct):
    return "Mild" if pct < 5 else "Moderate" if pct < 20 else "Serious"


def _is_text(series):
    return not (pd.api.types.is_numeric_dtype(series)
                or pd.api.types.is_datetime64_any_dtype(series)
                or pd.api.types.is_bool_dtype(series))


def examine(df):
    """Return a diagnosis dictionary: health score, problems and suggested fixes."""
    rows, cols = df.shape
    missing_cells = int(df.isna().sum().sum())
    duplicates = int(df.duplicated().sum())
    problems = []

    def add(ptype, col, title, count, pct, what, why, fix=None):
        fix_id = ptype if col is None else f"{ptype}:{col}"
        problem = {"id": fix_id, "type": ptype, "column": col, "title": title,
                   "severity": _severity(pct), "count": int(count),
                   "what": what, "why": why, "fix_id": None}
        if fix:
            problem["fix_id"] = fix_id
            problem["fix"] = {"id": fix_id, "type": ptype, "column": col, **fix}
        problems.append(problem)

    # 1. Duplicate rows
    if duplicates:
        add("drop_duplicates", None, f"{duplicates} duplicate rows", duplicates, duplicates / rows * 100,
            f"{duplicates} rows are exact copies of other rows.",
            "Duplicates count the same thing twice, which inflates totals and averages.",
            {"title": f"Remove {duplicates} duplicate rows",
             "description": "Keep the first copy of each row and delete the rest.",
             "why": "Every record should be counted once.", "default": True})

    # 2. Missing values
    for col in df.columns:
        n = int(df[col].isna().sum())
        if n:
            pct = n / rows * 100
            fix = None
            if pct <= 50:
                numeric = pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_datetime64_any_dtype(df[col])
                how = "the median (middle value)" if numeric else "the most common value"
                fix = {"title": f"Fill missing values in '{col}'",
                       "description": f"Replace empty cells with {how}.",
                       "why": "Gaps break calculations; a typical value keeps the row usable.",
                       "default": True}
            add("fill_missing", col, f"Missing values in '{col}'", n, pct,
                f"{n} of {rows} cells ({pct:.1f}%) in '{col}' are empty."
                + ("" if fix else " That is too many to guess safely, so no automatic fix is offered."),
                "Empty cells can make averages wrong and can cause errors in later analysis.", fix)

    # 3. Text columns
    for col in df.columns:
        if not _is_text(df[col]):
            continue
        s = df[col].dropna().astype(str)
        if s.empty:
            continue
        stripped = s.str.strip()
        spaces = int((s != stripped).sum())
        if spaces:
            add("trim_whitespace", col, f"Extra spaces in '{col}'", spaces, spaces / rows * 100,
                f"{spaces} values in '{col}' start or end with invisible spaces.",
                "'Paris' and 'Paris ' look the same to you, but a computer treats them as different values.",
                {"title": f"Trim extra spaces in '{col}'", "description": "Remove spaces at the start and end of each value.",
                 "why": "Makes matching and grouping reliable.", "default": True})
        probe = stripped.head(1000)
        numbers = pd.to_numeric(probe.str.replace(NUMBER_CLEANUP, "", regex=True), errors="coerce")
        if numbers.notna().mean() >= 0.8:
            bad = int(numbers.isna().sum())
            add("to_numeric", col, f"Numbers stored as text in '{col}'", len(s), len(s) / rows * 100,
                f"'{col}' looks like numbers, but it is stored as text (for example with $ or commas).",
                "Text cannot be added, averaged or sorted properly as numbers.",
                {"title": f"Convert '{col}' to numbers",
                 "description": "Remove symbols like $ , % and turn the column into numbers."
                                + (" Values that are not numbers become empty." if bad else ""),
                 "why": "Lets you calculate with the column.", "default": True})
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            dates = pd.to_datetime(probe, errors="coerce")
        if dates.notna().mean() >= 0.8 and probe.str.len().mean() >= 6:
            add("to_datetime", col, f"Dates stored as text in '{col}'", len(s), len(s) / rows * 100,
                f"'{col}' contains dates, but the computer sees them as plain text.",
                "Plain text dates cannot be sorted by time or used to calculate durations.",
                {"title": f"Convert '{col}' to real dates", "description": "Turn the text into proper date values. Unreadable dates become empty.",
                 "why": "Enables sorting and date maths.", "default": True})
            continue
        key = stripped.str.lower()
        if stripped.nunique() <= 200 and key.nunique() < stripped.nunique():
            canon = stripped.groupby(key).agg(lambda x: x.value_counts().index[0])
            changed = int((stripped != key.map(canon)).sum())
            add("standardize_case", col, f"Inconsistent spelling in '{col}'", changed, changed / rows * 100,
                f"The same value is written in different ways in '{col}' (for example 'NYC', 'nyc').",
                "Groups and counts get split into several categories that are really one.",
                {"title": f"Make spelling consistent in '{col}'",
                 "description": "Use the most common spelling for values that differ only by upper/lower case.",
                 "why": "One thing should have one name.", "default": True})

    # 4. Outliers in number columns
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]) and not pd.api.types.is_bool_dtype(df[col]):
            x = df[col].dropna()
            if len(x) < 10 or x.is_unique or col.lower().replace('_', '').endswith('id'):  # skip tiny and ID-like columns
                continue
            q1, q3 = x.quantile(0.25), x.quantile(0.75)
            iqr = q3 - q1
            if iqr <= 0:
                continue
            n = int(((x < q1 - 1.5 * iqr) | (x > q3 + 1.5 * iqr)).sum())
            if n:
                add("cap_outliers", col, f"Extreme values in '{col}'", n, n / len(x) * 100,
                    f"{n} values in '{col}' are far outside the normal range.",
                    "A few extreme values can distort averages. They may also be real, so check before changing them.",
                    {"title": f"Limit extreme values in '{col}' (optional)",
                     "description": "Pull extreme values back to the edge of the normal range. Skip this if they are real.",
                     "why": "Reduces distortion, but it changes real numbers.", "default": False})

    # Health score: start at 100 and subtract penalties
    penalty = min(30, missing_cells / max(rows * cols, 1) * 100 * 1.5)
    penalty += min(20, duplicates / max(rows, 1) * 100)
    penalty += min(30, 4 * sum(p["type"] in ("trim_whitespace", "to_numeric", "to_datetime", "standardize_case") for p in problems))
    penalty += min(10, 2 * sum(p["type"] == "cap_outliers" for p in problems))
    score = max(0, round(100 - penalty))
    label = "Healthy" if score >= 80 else "Needs attention" if score >= 60 else "Critical condition"

    return {
        "score": score, "label": label, "rows": int(rows), "cols": int(cols),
        "missing_cells": missing_cells, "duplicates": duplicates,
        "problem_count": len(problems), "problems": problems,
        "fixes": [p["fix"] for p in problems if p["fix_id"]],
        "summary": (f"Your dataset has {rows} rows and {cols} columns. "
                    + (f"We found {len(problems)} issue(s) worth looking at." if problems
                       else "We found no problems. Great shape!")),
        "columns": [{"name": c, "dtype": str(df[c].dtype), "missing": int(df[c].isna().sum())} for c in df.columns],
        "ai_used": False,
    }


def brief(d):
    """A short version of a diagnosis, used for before/after comparison."""
    keys = ("score", "label", "rows", "cols", "missing_cells", "duplicates", "problem_count")
    return {k: d[k] for k in keys}


def preview(df, n=10):
    """First n rows as plain text so they can be sent as JSON."""
    head = df.head(n).astype(object).where(df.head(n).notna(), "").astype(str)
    return {"columns": list(head.columns), "rows": head.values.tolist()}
