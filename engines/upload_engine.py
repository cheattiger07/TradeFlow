import os
import uuid
import logging
import chardet
import pandas as pd
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

ENCODINGS_TO_TRY = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
DELIMITERS_TO_TRY = [",", ";", "\t", "|"]


# ─── 1. Filename Validation ────────────────────────────────────────────────────

def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check extension is in allowed set."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed_extensions


def safe_filename(original: str) -> str:
    """
    Secure filename with UUID prefix to prevent collisions.
    Falls back to a pure UUID name if secure_filename returns empty
    (e.g. non-ASCII filenames from Indian brokers).
    """
    secured = secure_filename(original)
    if not secured:
        ext = original.rsplit(".", 1)[-1].lower() if "." in original else "csv"
        secured = f"upload.{ext}"
    unique_name = f"{uuid.uuid4().hex}_{secured}"
    return unique_name


# ─── 2. Save File ──────────────────────────────────────────────────────────────

def save_file(file, upload_folder: str) -> str:
    """Save uploaded file with a unique name. Returns saved path."""
    filename = safe_filename(file.filename)
    path = os.path.join(upload_folder, filename)
    file.save(path)

    # Guard: reject zero-byte files
    if os.path.getsize(path) == 0:
        os.remove(path)
        raise ValueError("Uploaded file is empty.")

    logger.info(f"Saved upload: {path}")
    return path


# ─── 3. Encoding Detection ────────────────────────────────────────────────────

def detect_encoding(path: str) -> str:
    """
    Use chardet to sniff encoding.
    Falls back through known encodings if chardet is uncertain.
    """
    with open(path, "rb") as f:
        raw = f.read(50_000)   # read first 50KB — enough for sniffing
    result = chardet.detect(raw)
    detected = result.get("encoding")
    confidence = result.get("confidence", 0)

    if detected and confidence > 0.7:
        logger.info(f"Detected encoding: {detected} (confidence {confidence:.0%})")
        return detected

    logger.warning(f"chardet uncertain ({confidence:.0%}), defaulting to utf-8-sig")
    return "utf-8-sig"


# ─── 4. CSV Loader with Delimiter + Encoding Auto-Detect ──────────────────────

def _load_csv(path: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Try multiple encodings × delimiters until a valid DataFrame is produced.
    A valid result must have >1 column (single-column = wrong delimiter).
    """
    encoding = detect_encoding(path)
    encodings = [encoding] + [e for e in ENCODINGS_TO_TRY if e != encoding]

    for enc in encodings:
        for delim in DELIMITERS_TO_TRY:
            try:
                df = pd.read_csv(
                    path,
                    delimiter=delim,
                    encoding=enc,
                    skip_blank_lines=True,
                    on_bad_lines="warn",    # skip malformed rows, don't crash
                )
                if df.shape[1] > 1:        # valid parse = multiple columns
                    logger.info(f"CSV loaded: encoding={enc}, delimiter='{delim}', "
                                f"rows={len(df)}, cols={df.shape[1]}")
                    return df, None
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"CSV parse attempt failed (enc={enc}, delim={delim}): {e}")
                continue

    return None, "Could not parse CSV. Check that the file is a valid tradebook export."


# ─── 5. XLSX Loader ───────────────────────────────────────────────────────────

def _load_xlsx(path: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Load first non-empty sheet from an XLSX file.
    Handles merged header rows by skipping leading empty rows.
    """
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        for sheet in xl.sheet_names:
            df = xl.parse(sheet, skip_blank_lines=True)
            if not df.empty and df.shape[1] > 1:
                logger.info(f"XLSX loaded: sheet='{sheet}', rows={len(df)}, cols={df.shape[1]}")
                return df, None

        return None, "XLSX file has no usable sheets with data."
    except Exception as e:
        logger.exception("XLSX load failed")
        return None, "Could not read XLSX file. Ensure it is a valid Excel export."


# ─── 6. Unified Loader (public API) ───────────────────────────────────────────

def load_file(path: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Unified entry point. Dispatches to CSV or XLSX loader by extension.
    Returns (df, None) on success or (None, error_message) on failure.
    """
    ext = path.rsplit(".", 1)[-1].lower()

    if ext == "csv":
        df, error = _load_csv(path)
    elif ext in ("xlsx", "xls"):
        df, error = _load_xlsx(path)
    else:
        return None, f"Unsupported file type: .{ext}"

    if error:
        if os.path.exists(path):
            os.remove(path)
        return None, error

    # Strip whitespace from all column names
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

    # Drop fully empty rows and columns
    df.dropna(how="all", inplace=True)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]
    if len(df) > 100000:
        return None, "File too large: max 100,000 rows allowed."
    return df, None