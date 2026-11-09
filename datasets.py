"""
datasets.py — Flexible user-uploaded review datasets (CSV / Excel / JSON).
-------------------------------------------------------------------------
A dataset may have any number of columns and any column naming convention.
The app preserves all columns, then inspects headers AND sample values to infer
useful review fields (text, item, rating, date and author). The user can always
change those suggestions on the mapping screen.
"""
import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

import pandas as pd

from database import get_conn, fetch_df

MAX_ROWS = 5000           # speed + DB-size safety cap per file
PROFILE_SAMPLE = 300      # values inspected for automatic column detection

# (header phrase, confidence points). Header names are normalised so these all
# work: reviewText, REVIEW_TEXT, review-text, review.text, etc.
ROLE_ALIASES = {
    "text": [
        ("review text", 145), ("review body", 145), ("review content", 145),
        ("customer review", 140), ("review comment", 135), ("review", 125),
        ("feedback", 120), ("comment", 120), ("testimonial", 115),
        ("opinion", 110), ("feedback text", 135), ("comment text", 135),
        ("review description", 125), ("message", 95), ("content", 90),
        ("body", 85), ("text", 80), ("description", 50), ("summary", 42),
        ("headline", 35),
    ],
    "item": [
        ("product title", 145), ("product name", 145), ("item name", 145),
        ("product id", 125), ("product", 115), ("item", 115),
        ("product code", 110), ("asin", 108), ("sku", 105), ("model", 95),
        ("brand", 80), ("category", 75), ("product type", 75),
        ("title", 70), ("name", 28),
    ],
    "rating": [
        ("overall rating", 145), ("review rating", 145), ("star rating", 145),
        ("rating", 135), ("stars", 130), ("star", 125), ("overall", 120),
        ("score", 110), ("grade", 90), ("rank", 55),
    ],
    "date": [
        ("review date", 145), ("review time", 140), ("date", 125),
        ("timestamp", 125), ("created at", 120), ("created", 105),
        ("published", 105), ("posted", 100), ("unix review time", 135),
        ("time", 70), ("day", 55),
    ],
    "author": [
        ("reviewer name", 145), ("reviewer id", 135), ("reviewer", 125),
        ("author", 125), ("customer name", 115), ("customer", 100),
        ("username", 105), ("user name", 100), ("user", 75), ("member", 75),
        ("profile name", 90),
    ],
}


# ---------- resilient file parsing ----------

def _set_large_csv_field_limit():
    """Allow Python's CSV parser to read unusually long review text cells."""
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:  # a few systems only accept smaller C long values
            limit //= 10


def _read_file_bytes(file):
    try:
        file.seek(0)
        return file.read()
    except Exception:
        return file.getvalue()


def _guess_delimiter(raw: bytes) -> str:
    """Detect comma, semicolon, tab or pipe CSV without relying on file name."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            sample = raw[:100_000].decode(encoding, errors="replace")
            # The header is the most dependable source: a malformed data row
            # can make csv.Sniffer fail even though the delimiter is obvious.
            header = next((line for line in sample.splitlines() if line.strip()), "")
            counts = {delimiter: header.count(delimiter) for delimiter in (",", ";", "\t", "|")}
            best, occurrences = max(counts.items(), key=lambda pair: pair[1])
            if occurrences:
                return best
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            return dialect.delimiter
        except csv.Error:
            continue
    return ","


def _read_csv_forgiving(file):
    """Read standard CSV fast; recover gracefully from messy marketplace files."""
    raw = _read_file_bytes(file)
    if not raw:
        raise ValueError("The CSV file is empty.")
    separator = _guess_delimiter(raw)

    # Fast path: normal CSV / Excel exports.
    fast_errors = []
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding, sep=separator,
                               nrows=MAX_ROWS + 1), None
        except Exception as exc:
            fast_errors.append(exc)

    # Compatibility path: Python engine supports enormous text fields and lets
    # us discard only individual malformed rows instead of rejecting the file.
    _set_large_csv_field_limit()
    skipped = []

    def skip_bad_line(line):
        skipped.append(line)
        return None

    for encoding in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(
                io.BytesIO(raw), encoding=encoding, encoding_errors="replace",
                sep=separator, engine="python", on_bad_lines=skip_bad_line,
                nrows=MAX_ROWS + 1,
            )
            note = (f"Used a compatibility reader; skipped {len(skipped)} malformed row(s)."
                    if skipped else "Used a compatibility reader for this CSV format.")
            return df, note
        except Exception:
            skipped.clear()

    # Final recovery for incorrectly escaped quote marks.
    try:
        df = pd.read_csv(
            io.BytesIO(raw), encoding="latin-1", encoding_errors="replace",
            sep=separator, engine="python", quoting=csv.QUOTE_NONE,
            on_bad_lines=skip_bad_line, nrows=MAX_ROWS + 1,
        )
        return df, ("Used a recovery reader for malformed quotes; "
                    f"skipped {len(skipped)} unusable row(s). Please check the preview.")
    except Exception as exc:
        detail = str(fast_errors[-1]) if fast_errors else str(exc)
        raise ValueError(
            "Could not read this CSV even with the compatibility reader. "
            "Open it in Excel/Google Sheets and save it as CSV UTF-8 or .xlsx. "
            f"Reader detail: {detail}"
        ) from exc


def _read_json_forgiving(file):
    """Accept ordinary JSON arrays/wrappers as well as JSON Lines / JSONL."""
    raw = _read_file_bytes(file)
    if not raw:
        raise ValueError("The JSON file is empty.")
    try:
        stripped = raw.lstrip()
        if stripped.startswith((b"[", b"{")):
            payload = json.loads(raw.decode("utf-8-sig"))
            if isinstance(payload, dict):
                # Common wrappers such as {"reviews": [...]} are accepted.
                list_value = next((v for v in payload.values() if isinstance(v, list)), None)
                payload = list_value if list_value is not None else [payload]
            df = pd.json_normalize(payload, sep="_").head(MAX_ROWS + 1)
        else:
            df = pd.read_json(io.BytesIO(raw), lines=True, nrows=MAX_ROWS + 1)
            # Flatten nested JSONL fields, e.g. {"review": {"text": "..."}}.
            if any(isinstance(v, (dict, list)) for v in df.head(10).to_numpy().flatten()):
                df = pd.json_normalize(df.to_dict("records"), sep="_")
    except Exception as exc:
        raise ValueError("Invalid JSON review file. Use a JSON array or JSON Lines (.jsonl).") from exc
    return df, "Loaded JSON review data."


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove empty rows/columns and make blank/duplicate headers usable."""
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").copy()
    seen = {}
    cleaned = []
    for i, original in enumerate(df.columns):
        base = str(original).strip() or f"Column {i + 1}"
        seen[base] = seen.get(base, 0) + 1
        cleaned.append(base if seen[base] == 1 else f"{base} ({seen[base]})")
    df.columns = cleaned
    return df


def read_upload(file):
    """Read CSV, Excel or JSON into a dataframe; keep every original column.

    Returns ``(dataframe, was_truncated)``. Parser feedback is placed in
    ``dataframe.attrs['parse_note']`` for the upload screen to display.
    """
    name = (getattr(file, "name", "") or "").lower()
    parse_note = None
    if name.endswith(".csv"):
        df, parse_note = _read_csv_forgiving(file)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file, nrows=MAX_ROWS + 1)
    elif name.endswith((".json", ".jsonl", ".ndjson")):
        df, parse_note = _read_json_forgiving(file)
    else:
        raise ValueError(f"Unsupported file type: {getattr(file, 'name', 'file')} "
                         "(use CSV, Excel or JSON)")

    df = _clean_columns(df)
    truncated = len(df) > MAX_ROWS
    if truncated:
        df = df.head(MAX_ROWS).copy()
    if parse_note:
        df.attrs["parse_note"] = parse_note
    return df, truncated


# ---------- automatic schema inference ----------

def _normalise_header(column) -> str:
    """Convert ReviewText / review_text / review.text to 'review text'."""
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(column))
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _header_score(column, role: str) -> float:
    header = _normalise_header(column)
    wrapped = f" {header} "
    best = 0.0
    for phrase, points in ROLE_ALIASES[role]:
        if header == phrase:
            best = max(best, float(points))
        elif f" {phrase} " in wrapped:
            # Full phrase inside a longer name, e.g. "verified review text".
            best = max(best, float(points - 18))
    return best


def _sample_values(series: pd.Series, limit: int = PROFILE_SAMPLE) -> list:
    values = []
    for value in series.dropna().head(limit * 3):
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none", "null", "nat"}:
            values.append(value)
            if len(values) >= limit:
                break
    return values


def _rating_value(value):
    """Read 4, 4.0, '4 out of 5 stars' and similar rating representations."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    raw = str(value).strip()
    if not raw:
        return None
    try:
        number = float(raw)
    except ValueError:
        match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:/|out\s+of|star)", raw, flags=re.I)
        if not match:
            return None
        number = float(match.group(1))
    # Avoid treating IDs, years and prices as ratings.
    return number if 0 <= number <= 10 else None


def rating_series(series: pd.Series) -> pd.Series:
    """Convert flexible star strings/numbers to numeric values for filters/charts."""
    return series.map(_rating_value)


def _parse_date_value(value):
    """Return a valid timestamp for conventional dates or Unix timestamps."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    raw = str(value).strip()
    if not raw:
        return None

    # Amazon datasets commonly store unixReviewTime in seconds or milliseconds.
    if re.fullmatch(r"\d+(?:\.0+)?", raw):
        number = float(raw)
        unit = "s" if 946684800 <= number <= 4_102_444_800 else (
            "ms" if 946684800000 <= number <= 4_102_444_800000 else None)
        if unit:
            try:
                return pd.to_datetime(number, unit=unit, utc=True).tz_convert(None)
            except (ValueError, OverflowError):
                return None
    try:
        try:
            stamp = pd.to_datetime(raw, format="mixed", errors="coerce")
        except (TypeError, ValueError):  # supports older pandas too
            stamp = pd.to_datetime(raw, errors="coerce")
        if pd.isna(stamp):
            return None
        stamp = pd.Timestamp(stamp)
        if stamp.tzinfo is not None:
            stamp = stamp.tz_convert(None)
        # Prevent ordinary numeric IDs being misread as dates near 1970.
        return stamp if 1990 <= stamp.year <= 2100 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _text_score(column, values: list) -> float:
    header = _header_score(column, "text")
    if not values:
        return header
    strings = [str(v).strip() for v in values]
    lengths = [len(s) for s in strings]
    average_length = sum(lengths) / len(lengths)
    alpha_fraction = sum(bool(re.search(r"[A-Za-z]", s)) for s in strings) / len(strings)
    phrase_fraction = sum(len(re.findall(r"[A-Za-z]+", s)) >= 3 for s in strings) / len(strings)
    score = header + min(38, average_length / 5) + alpha_fraction * 14 + phrase_fraction * 26
    name = _normalise_header(column)
    if any(token in name.split() for token in ("id", "url", "image", "price", "rating", "date", "time", "vote", "helpful")):
        score -= 65
    return score


def _item_score(column, values: list) -> float:
    header = _header_score(column, "item")
    if not values:
        return header
    strings = [str(v).strip() for v in values]
    count = len(strings)
    unique_ratio = len(set(strings)) / max(1, count)
    meaningful = sum(bool(re.search(r"[A-Za-z0-9]", s)) for s in strings) / count
    # Repeated values are useful grouping fields; column name remains the main
    # signal because a dataset may contain only one product.
    grouping = 24 if 0.01 <= unique_ratio <= 0.88 else (10 if unique_ratio < 1 else 0)
    score = header + grouping + meaningful * 8
    name = _normalise_header(column)
    if any(token in name.split() for token in ("review", "comment", "feedback", "author", "reviewer", "customer", "user")):
        score -= 85
    return score


def _rating_score(column, values: list) -> float:
    header = _header_score(column, "rating")
    parsed = [v for v in (_rating_value(value) for value in values) if v is not None]
    if not values:
        return header
    valid_ratio = len(parsed) / len(values)
    star_ratio = (sum(0 <= v <= 5 for v in parsed) / len(parsed)) if parsed else 0
    return header + valid_ratio * 35 + star_ratio * 40


def _date_score(column, values: list) -> float:
    header = _header_score(column, "date")
    if not values:
        return header
    parsed_ratio = sum(_parse_date_value(v) is not None for v in values) / len(values)
    return header + parsed_ratio * 55


def _author_score(column, values: list) -> float:
    header = _header_score(column, "author")
    if not values:
        return header
    strings = [str(v).strip() for v in values]
    # Names/IDs can both identify the reviewer, so do not demand prose here.
    nonempty = sum(bool(s) for s in strings) / len(strings)
    return header + nonempty * 8


def _best(scores: dict, excluded=(), threshold: float = 0):
    allowed = [(column, score) for column, score in scores.items() if column not in excluded]
    if not allowed:
        return None, 0.0
    column, score = max(allowed, key=lambda pair: pair[1])
    return (column, score) if score >= threshold else (None, score)


def _confidence(score: float) -> str:
    if score >= 130:
        return "High"
    if score >= 80:
        return "Likely"
    return "Check"


def infer_review_schema(df: pd.DataFrame):
    """Infer useful fields from all columns, regardless of their names.

    Returns ``(mapping, report)`` where mapping has text/item/rating/date/author
    keys and report is a small UI-ready list explaining the suggestions.
    """
    columns = list(df.columns)
    samples = {column: _sample_values(df[column]) for column in columns}
    text_scores = {c: _text_score(c, samples[c]) for c in columns}
    text, text_value = _best(text_scores)

    item_scores = {c: _item_score(c, samples[c]) for c in columns}
    item, item_value = _best(item_scores, excluded=(text,), threshold=58)

    rating_scores = {c: _rating_score(c, samples[c]) for c in columns}
    rating, rating_value = _best(rating_scores, excluded=(text, item), threshold=50)

    date_scores = {c: _date_score(c, samples[c]) for c in columns}
    date, date_value = _best(date_scores, excluded=(text, item, rating), threshold=50)

    author_scores = {c: _author_score(c, samples[c]) for c in columns}
    author, author_value = _best(author_scores, excluded=(text, item, rating, date), threshold=58)

    mapping = {"text": text, "item": item, "rating": rating, "date": date, "author": author}
    score_by_role = {"text": text_value, "item": item_value, "rating": rating_value,
                     "date": date_value, "author": author_value}
    labels = {"text": "Review text", "item": "Item / product", "rating": "Rating",
              "date": "Date", "author": "Author"}
    report = []
    for role in ("text", "item", "rating", "date", "author"):
        column = mapping[role]
        if column:
            report.append({"Field": labels[role], "Suggested column": column,
                           "Confidence": _confidence(score_by_role[role]),
                           "How it was found": "header name + sample values"})
        else:
            report.append({"Field": labels[role], "Suggested column": "—",
                           "Confidence": "Not needed", "How it was found": "no confident match"})
    return mapping, report


def auto_map_columns(df: pd.DataFrame) -> dict:
    """Backwards-compatible shorthand for the flexible schema inference."""
    return infer_review_schema(df)[0]


# ---------- analysis helpers ----------

def _display_date(value) -> str:
    stamp = _parse_date_value(value)
    return stamp.strftime("%Y-%m-%d") if stamp is not None else str(value).strip()


def reviews_from_df(df: pd.DataFrame, mapping: dict, limit: int = 2000) -> list:
    """Convert mapped rows to the review structure required by nlp_engine."""
    text_col = mapping.get("text")
    rating_col = mapping.get("rating")
    date_col = mapping.get("date")
    author_col = mapping.get("author")
    out = []
    for index, (_, row) in enumerate(df.iterrows()):
        if len(out) >= limit:
            break
        text = str(row[text_col]).strip() if text_col in df.columns else ""
        if not text or text.lower() in {"nan", "none", "null"}:
            continue
        rating = _rating_value(row[rating_col]) if rating_col in df.columns else None
        date = _display_date(row[date_col]) if date_col in df.columns else ""
        if date.lower() in {"nan", "none", "null", "nat"}:
            date = ""
        author = str(row[author_col]).strip() if author_col in df.columns else ""
        if not author or author.lower() in {"nan", "none", "null"}:
            author = f"Review #{index + 1}"
        out.append({"author": author, "rating": rating, "text": text, "date": date})
    return out


def search_items(items: list, query: str) -> list:
    """Prefix-first search over detected item/group values."""
    query = (query or "").strip().lower()
    items = [str(item) for item in items]
    if not query:
        return sorted(set(items))
    starts = sorted({item for item in items if item.lower().startswith(query)})
    contains = sorted({item for item in items if query in item.lower() and item not in starts})
    return starts + contains


# ---------- persistence (per user, in SQLite) ----------

def _unique_name(user_id: int, name: str) -> str:
    base = name.rsplit(".", 1)[0][:60] or "dataset"
    existing = {dataset["name"] for dataset in list_datasets(user_id)}
    if base not in existing:
        return base
    number = 2
    while f"{base} ({number})" in existing:
        number += 1
    return f"{base} ({number})"


def save_dataset(user_id: int, filename: str, df: pd.DataFrame) -> str:
    """Store all imported columns for one user and return the unique dataset name."""
    name = _unique_name(user_id, filename)
    conn = get_conn()
    conn.execute(
        """INSERT INTO datasets (user_id, name, csv_text, columns, row_count, created_at)
           VALUES (?,?,?,?,?, datetime('now','localtime'))""",
        (user_id, name, df.to_csv(index=False), ", ".join(df.columns), len(df)),
    )
    conn.commit()
    conn.close()
    return name


def list_datasets(user_id: int) -> list:
    df = fetch_df(
        "SELECT id, name, columns, row_count, created_at FROM datasets WHERE user_id=? ORDER BY id DESC",
        (user_id,))
    return df.to_dict("records") if not df.empty else []


def load_dataset(dataset_id: int, user_id: int):
    """Return (name, dataframe) only if the dataset belongs to this user."""
    df = fetch_df("SELECT name, csv_text FROM datasets WHERE id=? AND user_id=?",
                  (dataset_id, user_id))
    if df.empty:
        return None, None
    return df["name"][0], pd.read_csv(io.StringIO(df["csv_text"][0]))


def delete_dataset(dataset_id: int, user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM datasets WHERE id=? AND user_id=?", (dataset_id, user_id))
    conn.commit()
    conn.close()


def load_sample():
    """Built-in demo dataset so users can explore the workflow instantly."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data.csv")
    return "Sample Reviews (demo)", pd.read_csv(path)
