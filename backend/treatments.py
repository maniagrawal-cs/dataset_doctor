"""Applies approved fixes with pandas, and writes the matching Python code for each fix."""
import warnings
import pandas as pd

# Fixes run in this order so each step builds on the previous one.
ORDER = ["trim_whitespace", "standardize_case", "to_numeric", "to_datetime",
         "drop_duplicates", "fill_missing", "cap_outliers"]
NUMBER_CLEANUP = r"[,$€£%\s]"


def apply_fixes(df, fixes):
    """Apply the chosen fixes. Returns the cleaned DataFrame and a list of what was done."""
    df = df.copy()
    done = []
    for fix in sorted(fixes, key=lambda f: ORDER.index(f["type"])):
        t, c = fix["type"], fix.get("column")
        if t == "trim_whitespace":
            df[c] = df[c].str.strip()
        elif t == "standardize_case":
            text = df[c].str.strip()
            key = text.str.lower()
            common = text.groupby(key).agg(lambda x: x.value_counts().index[0])
            df[c] = key.map(common)
        elif t == "to_numeric":
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(NUMBER_CLEANUP, "", regex=True), errors="coerce")
        elif t == "to_datetime":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df[c] = pd.to_datetime(df[c], errors="coerce")
        elif t == "drop_duplicates":
            df = df.drop_duplicates().reset_index(drop=True)
        elif t == "fill_missing":
            if pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c]):
                df[c] = df[c].fillna(df[c].median())
            else:
                mode = df[c].mode()
                df[c] = df[c].fillna(mode.iloc[0] if len(mode) else "Unknown")
        elif t == "cap_outliers":
            q1, q3 = df[c].quantile(0.25), df[c].quantile(0.75)
            iqr = q3 - q1
            df[c] = df[c].clip(q1 - 1.5 * iqr, q3 + 1.5 * iqr)
        done.append(fix["title"])
    return df, done


def code_for(fix):
    """The same fix, written as readable, commented Python code."""
    t, c = fix["type"], fix.get("column")
    if t == "trim_whitespace":
        return (f"# Remove spaces at the start and end of the text in {c!r}\n"
                f"df[{c!r}] = df[{c!r}].str.strip()\n")
    if t == "standardize_case":
        return (f"# Make spelling consistent in {c!r}: values that differ only by upper/lower case\n"
                f"# are replaced by their most common spelling.\n"
                f"text = df[{c!r}].str.strip()\n"
                f"key = text.str.lower()  # the lower-case version is used to find matching values\n"
                f"most_common = text.groupby(key).agg(lambda x: x.value_counts().index[0])\n"
                f"df[{c!r}] = key.map(most_common)\n")
    if t == "to_numeric":
        return (f"# Turn {c!r} into real numbers: remove symbols like $ , % and spaces first.\n"
                f"# errors='coerce' means anything that is still not a number becomes empty (NaN).\n"
                f"df[{c!r}] = pd.to_numeric(\n"
                f"    df[{c!r}].astype(str).str.replace(r\"[,$€£%\\s]\", \"\", regex=True),\n"
                f"    errors=\"coerce\")\n")
    if t == "to_datetime":
        return (f"# Turn the text in {c!r} into real dates. Unreadable dates become empty (NaT).\n"
                f"df[{c!r}] = pd.to_datetime(df[{c!r}], errors=\"coerce\")\n")
    if t == "drop_duplicates":
        return ("# Remove rows that are exact copies of an earlier row (the first copy is kept)\n"
                "df = df.drop_duplicates().reset_index(drop=True)\n")
    if t == "fill_missing":
        return (f"# Fill empty cells in {c!r}: median for numbers/dates, most common value for text\n"
                f"if pd.api.types.is_numeric_dtype(df[{c!r}]) or pd.api.types.is_datetime64_any_dtype(df[{c!r}]):\n"
                f"    df[{c!r}] = df[{c!r}].fillna(df[{c!r}].median())\n"
                f"else:\n"
                f"    mode = df[{c!r}].mode()  # the most common value(s)\n"
                f"    df[{c!r}] = df[{c!r}].fillna(mode.iloc[0] if len(mode) else \"Unknown\")\n")
    if t == "cap_outliers":
        return (f"# Limit extreme values in {c!r} to the normal range (the 'IQR rule')\n"
                f"q1, q3 = df[{c!r}].quantile(0.25), df[{c!r}].quantile(0.75)\n"
                f"iqr = q3 - q1\n"
                f"df[{c!r}] = df[{c!r}].clip(q1 - 1.5 * iqr, q3 + 1.5 * iqr)\n")
    return ""
