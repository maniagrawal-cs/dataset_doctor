"""Builds the final Python cleaning script. A template is always made first; Gemini only polishes the comments."""
from pathlib import Path
try:
    from . import treatments
    from .gemini_service import ask_gemini
except ImportError:
    import treatments
    from gemini_service import ask_gemini


def output_name(filename):
    path = Path(filename)
    ext = ".csv" if path.suffix.lower() == ".csv" else ".xlsx"
    return f"cleaned_{path.stem}{ext}"


def build_template(filename, fixes):
    reader = (f"pd.read_csv({filename!r})" if filename.lower().endswith(".csv")
              else f"pd.read_excel({filename!r})")
    out = output_name(filename)
    writer = f"df.to_csv({out!r}, index=False)" if out.endswith(".csv") else f"df.to_excel({out!r}, index=False)"
    parts = [
        f'"""\nCleaning script made by Dataset Doctor.\nOriginal file: {filename}\n\n'
        f'How to use: pip install pandas openpyxl\n            python clean_dataset.py\n'
        f'(Keep this script in the same folder as your data file.)\n"""\n',
        "import pandas as pd\n",
        f"# Step 0: Load the data\ndf = {reader}\nprint(\"Rows before cleaning:\", len(df))\n",
    ]
    for number, fix in enumerate(fixes, 1):
        parts.append(f"# Step {number}: {fix['title']}\n{treatments.code_for(fix)}")
    parts.append(f"# Final step: Save the cleaned data\n{writer}\nprint(\"Rows after cleaning:\", len(df))\nprint(\"Saved as {out}\")\n")
    return "\n".join(parts)


def build_code(filename, fixes):
    template = build_template(filename, fixes)
    prompt = (
        "Below is a working pandas script. Rewrite it with clearer, beginner-friendly comments that explain "
        "WHAT each step does and WHY. The code must behave exactly the same: same steps, same order, same "
        "file names. Do not add or remove steps. Reply with only the Python code, no markdown fences.\n\n" + template)
    polished = ask_gemini(prompt)
    if polished:
        polished = polished.strip()
        if polished.startswith("```"):
            polished = polished.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if "import pandas" in polished and "read_" in polished and "to_" in polished:
            return polished + "\n"
    return template
