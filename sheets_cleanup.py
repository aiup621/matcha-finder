from typing import List, Dict, Tuple

EMAIL_COL_A1 = "E"
STATUS_COL_A1 = "G"
ERROR_TEXT = "エラー"


def normalize_email(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip()
    if s.lower().startswith("mailto:"):
        s = s[7:]
    return s.strip().lower()


def _batch_get_values(service, spreadsheet_id: str, title: str, ranges_a1: List[str]) -> Dict[str, List[List[str]]]:
    res = service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=[f"'{title}'!{rng}" for rng in ranges_a1],
        majorDimension="ROWS"
    ).execute()
    out = {}
    for vr in res.get("valueRanges", []):
        # "'Sheet'!E2:E" の形 → 右側の純レンジ文字列に寄せる
        full = vr.get("range", "")
        rng = full.split("!", 1)[1] if "!" in full else full
        out[rng] = vr.get("values", [])
    return out


def _get_sheet_id_by_title(service, spreadsheet_id: str, title: str) -> int:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for s in meta.get("sheets", []):
        if s.get("properties", {}).get("title") == title:
            return s.get("properties", {}).get("sheetId")
    raise RuntimeError(f"Sheet not found: {title}")


def _batch_delete_rows(service, spreadsheet_id: str, sheet_id: int, rows_1based: List[int]) -> int:
    if not rows_1based:
        return 0
    # Google Sheets APIは0-based/終了行exclusive
    reqs = []
    for r in sorted(rows_1based, reverse=True):
        reqs.append({
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": r - 1,
                    "endIndex": r
                }
            }
        })
    body = {"requests": reqs}
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()
    return len(rows_1based)


def cleanup_written_only(service, spreadsheet_id: str, title: str, written_rows: List[int]) -> None:
    if not written_rows:
        print("[CLEANUP] No written rows; skip.")
        return

    data = _batch_get_values(
        service, spreadsheet_id, title,
        [f"{EMAIL_COL_A1}2:{EMAIL_COL_A1}", f"{STATUS_COL_A1}2:{STATUS_COL_A1}"]
    )
    e_rng = f"{EMAIL_COL_A1}2:{EMAIL_COL_A1}"
    g_rng = f"{STATUS_COL_A1}2:{STATUS_COL_A1}"
    e_vals = data.get(e_rng, [])
    g_vals = data.get(g_rng, [])
    max_len = max(len(e_vals), len(g_vals))

    written_set = set(written_rows)

    # E列：先勝ち（先に現れた行を残し、同じメールの後発は削除候補）
    seen = set()
    dup_to_delete = set()
    for i in range(max_len):
        rownum = i + 2  # シート上の行番号（ヘッダが1行の想定）
        email_raw = (e_vals[i][0] if i < len(e_vals) and e_vals[i] else "")
        email = normalize_email(email_raw)
        if not email:
            continue
        if email in seen:
            if rownum in written_set:
                dup_to_delete.add(rownum)
        else:
            seen.add(email)

    # G列：「エラー」
    err_to_delete = set()
    for i in range(len(g_vals)):
        rownum = i + 2
        cell = (g_vals[i][0] if g_vals[i] else "")
        if rownum in written_set and str(cell).strip() == ERROR_TEXT:
            err_to_delete.add(rownum)

    targets = sorted(dup_to_delete | err_to_delete)
    if not targets:
        print("[CLEANUP] No rows to delete (written-only duplicates + G='エラー').")
        return

    sheet_id = _get_sheet_id_by_title(service, spreadsheet_id, title)
    deleted = _batch_delete_rows(service, spreadsheet_id, sheet_id, targets)
    print(f"[CLEANUP] Deleted {deleted} rows (written-only): {targets}")


def _compress_consecutive_indices(indices: List[int]) -> List[Tuple[int, int]]:
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
