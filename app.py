from flask import Flask, request, jsonify, send_file, render_template
import pandas as pd
import os
import json
import re
import uuid
import io
import zipfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}

KNOWN_ABBREVIATIONS = {
    "USA", "UK", "UAE", "EU", "US", "UN", "LLC", "INC", "LTD", "CO",
    "PLC", "CEO", "CFO", "CTO", "FBI", "CIA", "NASA", "NATO", "NZ",
    "AU", "CA", "NY", "TX", "FL", "DC",
}

NULL_STRINGS = {"n/a", "na", "none", "null", "nil", "-", "--", "?", "unknown", ""}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def to_snake_case(name):
    name = str(name).strip()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^\w]", "", name)
    name = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return name.lower()


def try_numeric(series):
    cleaned = (
        series.astype(str)
        .str.replace(r"[$,%]", "", regex=True)
        .str.strip()
    )
    converted = pd.to_numeric(cleaned, errors="coerce")
    success_rate = converted.notna().sum() / max(series.notna().sum(), 1)
    if success_rate >= 0.6:
        return converted, True
    return series, False


def smart_title(val):
    if pd.isna(val) or str(val).lower() == "nan":
        return pd.NA
    def fix_token(t):
        return t.upper() if t.upper() in KNOWN_ABBREVIATIONS else t.capitalize()
    return " ".join(fix_token(t) for t in str(val).split())


def clean_dataframe(df, title_case_columns=None):
    actions = []

    def log(action, detail=None, delta=None):
        entry = {"action": action}
        if detail:
            entry["detail"] = detail
        if delta is not None:
            entry["rows_removed"] = int(delta)
        actions.append(entry)

    original_rows = len(df)
    original_cols = list(df.columns)

    # 1. Snake case columns
    new_cols = [to_snake_case(c) for c in df.columns]
    renamed = {old: new for old, new in zip(df.columns, new_cols) if old != new}
    df.columns = new_cols
    if renamed:
        log("Renamed columns to snake_case", detail=str(renamed))

    # 2. Remove empty rows
    before = len(df)
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    df = df.dropna(how="all")
    log("Removed fully empty rows", delta=before - len(df))

    # 3. Strip whitespace
    stripped_count = 0
    for col in df.columns:
        original = df[col].copy()
        df[col] = df[col].astype(str).str.strip().replace("nan", pd.NA)
        stripped_count += (original != df[col]).sum()
    log("Stripped leading/trailing whitespace", detail=f"{stripped_count} cells affected")

    # 4. Collapse internal whitespace
    collapsed_count = 0
    for col in df.columns:
        original = df[col].copy()
        df[col] = df[col].astype(str).str.replace(r"\s+", " ", regex=True).replace("nan", pd.NA)
        collapsed_count += (original != df[col]).sum()
    log("Collapsed internal whitespace", detail=f"{collapsed_count} cells affected")

    # 5. Nullish strings
    nullish_count = 0
    for col in df.columns:
        mask = df[col].astype(str).str.lower().str.strip().isin(NULL_STRINGS)
        nullish_count += mask.sum()
        df.loc[mask, col] = pd.NA
    log("Replaced nullish strings (N/A, none, null…) with empty", detail=f"{nullish_count} cells affected")

    # 5b. Lowercase emails
    email_cols = [col for col in df.columns if "email" in col or "e_mail" in col]
    email_lowered = 0
    for col in email_cols:
        original = df[col].copy()
        df[col] = df[col].astype(str).str.lower().replace("nan", pd.NA)
        email_lowered += (original.fillna("") != df[col].fillna("")).sum()
    if email_cols:
        log("Lowercased email columns", detail=f"columns: {email_cols}, {email_lowered} cells affected")

    # 6. Deduplicate (case-insensitive)
    before = len(df)
    df_norm = df.fillna("").astype(str).apply(lambda col: col.str.lower().str.strip())
    duplicate_mask = df_norm.duplicated()
    df = df[~duplicate_mask]
    log("Removed duplicate rows (case-insensitive)", delta=before - len(df))

    # 7. Numeric coercion
    numeric_converted = []
    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) == 0:
            continue
        digit_ratio = non_null.astype(str).str.contains(r"\d").mean()
        if digit_ratio > 0.7:
            converted, success = try_numeric(df[col])
            if success:
                if converted.dropna().apply(float.is_integer).all():
                    converted = converted.astype("Int64")
                df[col] = converted
                numeric_converted.append(col)
    if numeric_converted:
        log("Coerced columns to numeric (stripped $, %, ,)", detail=str(numeric_converted))

    # 8. Title case
    if title_case_columns is not None:
        if len(title_case_columns) == 0:
            title_case_columns = [
                col for col in df.select_dtypes(include="object").columns
                if any(k in col for k in ("name", "city", "state", "country",
                                          "title", "label", "description"))
            ]
        tc_count = 0
        for col in title_case_columns:
            if col in df.columns:
                original = df[col].copy()
                df[col] = df[col].apply(smart_title)
                tc_count += (original.fillna("") != df[col].fillna("")).sum()
        if tc_count:
            log("Applied title case (abbreviations preserved)",
                detail=f"columns: {title_case_columns}, {tc_count} cells affected")

    cleaned_rows = len(df)
    report = {
        "rows_before": int(original_rows),
        "rows_after": int(cleaned_rows),
        "total_rows_removed": int(original_rows - cleaned_rows),
        "original_columns": original_cols,
        "cleaned_columns": list(df.columns),
        "actions": actions,
    }

    return df, report


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/clean", methods=["POST"])
def clean():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Use CSV or Excel."}), 400

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[1].lower()

    try:
        if ext == "csv":
            df = pd.read_csv(file, dtype=str)
        else:
            df = pd.read_excel(file, dtype=str)
    except Exception as e:
        return jsonify({"error": f"Could not read file: {str(e)}"}), 400

    title_cols = request.form.get("title_cols", "")
    title_case_columns = [c.strip() for c in title_cols.split(",") if c.strip()] if title_cols else []

    try:
        cleaned_df, report = clean_dataframe(df, title_case_columns=title_case_columns)
    except Exception as e:
        return jsonify({"error": f"Cleaning failed: {str(e)}"}), 500

    # Build zip with cleaned file + report
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Cleaned CSV
        csv_buffer = io.StringIO()
        cleaned_df.to_csv(csv_buffer, index=False)
        zf.writestr("cleaned_" + filename.rsplit(".", 1)[0] + ".csv", csv_buffer.getvalue())
        # Report JSON
        zf.writestr("cleaning_report.json", json.dumps(report, indent=4))

    zip_buffer.seek(0)

    report["zip_available"] = True
    session_id = str(uuid.uuid4())

    # Store zip temporarily in memory via a simple global dict
    app.config.setdefault("ZIPS", {})[session_id] = zip_buffer.read()

    report["session_id"] = session_id
    return jsonify(report)


@app.route("/download/<session_id>")
def download(session_id):
    zips = app.config.get("ZIPS", {})
    if session_id not in zips:
        return "File not found or expired", 404
    data = zips[session_id]
    return send_file(
        io.BytesIO(data),
        mimetype="application/zip",
        as_attachment=True,
        download_name="cleaned_data.zip"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
