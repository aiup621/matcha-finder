from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Sequence, Tuple


def normalize_email(value: str | None) -> str:
    """Return a normalised representation of ``value`` suitable for deduping."""

    if not value:
        return ""

    text = str(value).strip()
    text = re.sub(r"^\s*mailto:\s*", "", text, flags=re.IGNORECASE)

    try:  # Normalise full-width variants to ASCII where possible.
        import unicodedata

        text = unicodedata.normalize("NFKC", text)
    except Exception:  # pragma: no cover - defensive, should not happen.
        pass

    text = re.sub(r"\s+", "", text)
    text = text.rstrip(".")
    return text.lower()


def collect_emails_map(
    service,
    spreadsheet_id: str,
    title: str,
    email_col_letter: str,
    header_rows: int,
) -> Dict[str, List[int]]:
    """Return a mapping of normalised emails to 1-based row numbers."""

    range_a1 = f"'{title}'!{email_col_letter}{header_rows + 1}:{email_col_letter}"
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=range_a1,
            valueRenderOption="FORMATTED_VALUE",
            majorDimension="COLUMNS",
        )
        .execute()
    )

    values = response.get("values", [])
    if not values:
        return {}

    column = values[0]
    emails_map: Dict[str, List[int]] = {}

    for offset, raw_value in enumerate(column):
        row_number = header_rows + 1 + offset
        normalised = normalize_email(raw_value)
        if normalised in {"", "-", "n/a", "na", "なし", "無し", "none"}:
            continue
        emails_map.setdefault(normalised, []).append(row_number)

    return emails_map


def get_sheet_id(service, spreadsheet_id: str, title: str) -> int:
    """Return the numeric sheet ID for ``title``."""

    response = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            fields="sheets(properties(sheetId,title))",
        )
        .execute()
    )
    for sheet in response.get("sheets", []):
        properties = sheet.get("properties", {})
        if properties.get("title") == title:
            sheet_id = properties.get("sheetId")
            if sheet_id is not None:
                return sheet_id
    raise ValueError(f"Worksheet {title!r} not found in spreadsheet {spreadsheet_id!r}")


def _get_rgb_color(cell: dict | None) -> dict | None:
    if not cell:
        return None
    fmt = cell.get("effectiveFormat") or {}
    style = fmt.get("backgroundColorStyle") or {}
    rgb_color = style.get("rgbColor")
    if rgb_color:
        return rgb_color
    return fmt.get("backgroundColor")


def _is_colored(cell: dict | None) -> bool:
    color = _get_rgb_color(cell)
    if not color:
        return False
    red = float(color.get("red", 1.0) or 1.0)
    green = float(color.get("green", 1.0) or 1.0)
    blue = float(color.get("blue", 1.0) or 1.0)
    return (red + green + blue) < 2.9


def find_rows_highlighted_as_duplicates(
    service,
    spreadsheet_id: str,
    title: str,
    email_col_letter: str = "E",
    header_rows: int = 1,
) -> List[int]:
    """Return row indices with non-white background colour in ``email_col_letter``."""

    range_a1 = f"'{title}'!{email_col_letter}{header_rows + 1}:{email_col_letter}"
    response = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_a1],
            includeGridData=True,
            fields=(
                "sheets("
                "properties.sheetId,properties.title,"
                "data.rowData.values.effectiveFormat.backgroundColor,"
                "data.rowData.values.effectiveFormat.backgroundColorStyle,"
                "data.rowData.values.effectiveValue.stringValue,"
                "data.rowData.values.userEnteredValue"
                ")"
            ),
        )
        .execute()
    )

    rows: List[int] = []
    sheets = response.get("sheets", [])
    if not sheets:
        return rows

    data = sheets[0].get("data", [])
    if not data:
        return rows

    row_data = data[0].get("rowData", [])
    for offset, row in enumerate(row_data):
        values = row.get("values", []) if isinstance(row, dict) else []
        cell = values[0] if values else None
        if _is_colored(cell):
            rows.append(header_rows + offset)
    return rows


def find_rows_by_programmatic_duplicates(
    service,
    spreadsheet_id: str,
    title: str,
    email_col_letter: str = "E",
    header_rows: int = 1,
) -> List[int]:
    """Return row indices where ``email_col_letter`` contains duplicated values."""

    range_a1 = f"'{title}'!{email_col_letter}:{email_col_letter}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_a1)
        .execute()
    )

    values = result.get("values", [])
    duplicates: List[int] = []
    seen: set[str] = set()

    for idx, row in enumerate(values):
        if idx < header_rows:
            continue
        cell_value = row[0] if row else ""
        if cell_value is None:
            cell_value = ""
        if not isinstance(cell_value, str):
            cell_value = str(cell_value)
        normalised = cell_value.strip().lower()
        if normalised in {"", "なし", "無し", "none", "n/a", "na", "-"}:
            continue
        if normalised not in seen:
            seen.add(normalised)
            continue
        duplicates.append(idx)
    return duplicates


def _compress_consecutive_indices(indices: Sequence[int]) -> List[Tuple[int, int]]:
    if not indices:
        return []
    sorted_indices = sorted(set(indices), reverse=True)
    ranges: List[Tuple[int, int]] = []
    run_start = prev = sorted_indices[0]
    for index in sorted_indices[1:]:
        if index == prev - 1:
            prev = index
            continue
        ranges.append((prev, run_start + 1))
        run_start = prev = index
    ranges.append((prev, run_start + 1))
    return ranges


def delete_rows(
    service,
    spreadsheet_id: str,
    sheet_id: int,
    row_indices: Iterable[int],
) -> None:
    """Delete ``row_indices`` on ``sheet_id`` in descending batches."""

    indices = list(row_indices)
    if not indices:
        return
    ranges = _compress_consecutive_indices(indices)
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start,
                    "endIndex": end,
                }
            }
        }
        for start, end in ranges
    ]
    (
        service.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests})
        .execute()
    )


def cleanup_duplicates_written_only(
    service,
    spreadsheet_id: str,
    title: str,
    email_col_letter: str,
    header_rows: int,
    written_rows: Sequence[int],
    *,
    dry_run: bool = False,
) -> int:
    """Delete duplicates among ``written_rows`` based on normalised email values."""

    if not written_rows:
        return 0

    emails_map = collect_emails_map(
        service,
        spreadsheet_id,
        title,
        email_col_letter,
        header_rows,
    )

    written_set = {int(row) for row in written_rows}
    to_delete: List[int] = []

    for rows in emails_map.values():
        if len(rows) <= 1:
            continue
        sorted_rows = sorted(rows)
        for candidate in sorted_rows[1:]:
            if candidate in written_set:
                to_delete.append(candidate)

    if not to_delete:
        logging.info("[CLEANUP] No written-only duplicates to delete.")
        return 0

    to_delete_desc = sorted(set(to_delete), reverse=True)

    if dry_run:
        logging.info(
            "[DRY_RUN] Would delete %s rows (written-only): %s",
            len(to_delete_desc),
            to_delete_desc,
        )
        return len(to_delete_desc)

    sheet_id = get_sheet_id(service, spreadsheet_id, title)
    zero_based_rows = [row - 1 for row in to_delete_desc]
    delete_rows(service, spreadsheet_id, sheet_id, zero_based_rows)
    logging.info(
        "[CLEANUP] Deleted %s rows (written-only): %s",
        len(to_delete_desc),
        to_delete_desc,
    )
    return len(to_delete_desc)

