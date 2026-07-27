#!/usr/bin/env python3
"""
연구비 & 모니터링 누적 트래커 - 데이터 수집(ingest) 프로그램
=============================================================

IQVIA 로부터 매번 받는 엑셀/PDF 파일을 data/source/ 에 넣고 이 스크립트를 실행하면,
파일 안의 데이터를 표준 스키마로 추출해 data/store.json 에 **누적(upsert)** 한다.
그 뒤 dashboard/build.py 를 실행하면 대시보드(dashboard/index.html)가 갱신된다.

누적(merge) 규칙
  - 지급/invoice 기록      : invoice_no + cost_type 로 upsert (중복 자동 제거)
  - 분기별 planned/actual  : vendor+year+quarter 로 upsert (최신 파일 값으로 갱신)
  - 모니터링 visit 스냅샷  : snapshot 날짜별로 누적 (새 파일 = 새 스냅샷 컬럼)
  - 대상자 방문           : (subject, visit_folder) 로 upsert
계약서(D/A)는 ingest/contracts.py 에서 관리(사람이 검수한 값).

사용법:  python3 ingest/ingest.py
"""
import json
import os
import sys
import datetime
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "source"
STORE = ROOT / "data" / "store.json"

sys.path.insert(0, str(ROOT / "ingest"))
import contracts  # noqa: E402


# ----------------------------------------------------------------------------- helpers
def d(v):
    """날짜/시간 값을 ISO 문자열로."""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%Y-%m-%d")
    return v


def s(v):
    return v.strip() if isinstance(v, str) else v


def num(v):
    if isinstance(v, (int, float)):
        return v
    return None


BUDGET_VENDOR_ROWS = {  # '0. Budget Summary' section 2 (분기별)
    17: "IQVIA", 18: "Syneos", 19: "Sharp", 20: "Fisher", 21: "Marken",
    22: "SBQ", 23: "Aptamer", 24: "Invivo", 25: "Labconnect", 26: "AIMS",
}
STATUS_VENDOR_COLS = {  # '0. Budget Summary' section 1 (Contracted/Paid/Remaining)
    2: "IQVIA", 3: "Syneos", 4: "Sharp", 5: "Fisher", 6: "Marken",
    7: "SBQ", 8: "Aptamer", 9: "Invivo", 10: "Labconnect", 11: "AIMS",
}


# ----------------------------------------------------------------------------- parsers
def parse_budget_tracker(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {"contract_meta": {}, "vendor_status": [], "quarterly": [],
           "direct_payments": [], "ptc_invoices": []}

    # --- 계약 메타 (IQVIA 시트) ---
    if "1. IQVIA " in wb.sheetnames:
        w = wb["1. IQVIA "]
        out["contract_meta"] = {
            "contract_number": s(w["C2"].value),
            "version": s(w["E2"].value),
            "budget_usd": num(w["B8"].value),
            "paid_usd": num(w["B9"].value),
            "remaining_usd": num(w["B10"].value),
        }

    # --- Overall status + 분기별 (Budget Summary) ---
    if "0. Budget Summary" in wb.sheetnames:
        w = wb["0. Budget Summary"]
        for col, vendor in STATUS_VENDOR_COLS.items():
            row = {"vendor": vendor,
                   "contracted": num(w.cell(8, col).value),
                   "paid": num(w.cell(9, col).value),
                   "remaining": num(w.cell(10, col).value),
                   "pct_remaining": num(w.cell(11, col).value)}
            if any(row[k] is not None for k in ("contracted", "paid")):
                out["vendor_status"].append(row)

        for r, vendor in BUDGET_VENDOR_ROWS.items():
            currency = s(w.cell(r, 2).value) or ""
            for year in range(2023, 2028):
                start = 3 + (year - 2023) * 11
                for q in range(1, 5):
                    planned = num(w.cell(r, start + 2 * (q - 1)).value)
                    actual = num(w.cell(r, start + 2 * (q - 1) + 1).value)
                    if not planned and not actual:
                        continue
                    out["quarterly"].append({
                        "vendor": vendor, "currency": currency,
                        "year": year, "quarter": q,
                        "planned": planned or 0, "actual": actual or 0,
                    })

    # --- Direct 지급 기록 (B/C 소스) ---
    if "1-1. Direct" in wb.sheetnames:
        w = wb["1-1. Direct"]
        for r in range(36, w.max_row + 1):
            milestone = s(w.cell(r, 1).value)
            if not milestone:
                continue
            rec = {
                "cost_type": "Direct",
                "category": "Direct (Core CRO Services)",
                "milestone": milestone,
                "budget_usd": num(w.cell(r, 2).value),
                "invoiced_usd": num(w.cell(r, 3).value),
                "invoice_no": s(w.cell(r, 4).value),
                "invoiced_date": d(w.cell(r, 5).value),
                "paid_year": num(w.cell(r, 6).value),
                "paid_month": num(w.cell(r, 7).value),
                "paid_date": d(w.cell(r, 8).value),
                "total_krw": num(w.cell(r, 9).value),
                "paid_yn": s(w.cell(r, 10).value),
                "approval_no": s(w.cell(r, 11).value),  # 지출결의 # (내부기안결재번호)
            }
            out["direct_payments"].append(rec)

    # --- PTC invoice 기록 (연구비=Investigator Payments 포함) ---
    if "1-2. PTC" in wb.sheetnames:
        w = wb["1-2. PTC"]
        # 카테고리 헤더 (row 40, cols C..O)
        cat_cols = {}
        for c in range(3, 16):
            h = s(w.cell(40, c).value)
            if h:
                cat_cols[c] = h
        for r in range(41, w.max_row + 1):
            inv = s(w.cell(r, 1).value)
            amt = num(w.cell(r, 16).value)  # Invoiced Amount ($) col P
            if not inv and not amt:
                continue
            # 카테고리별 금액 분해
            breakdown = {}
            for c, name in cat_cols.items():
                v = num(w.cell(r, c).value)
                if v:
                    breakdown[name] = v
            out["ptc_invoices"].append({
                "cost_type": "PTC",
                "category": "Pass-through",
                "invoice_no": inv,
                "invoiced_usd": amt,
                "invoiced_date": d(w.cell(r, 17).value),
                "paid_year": num(w.cell(r, 18).value),
                "breakdown": breakdown,
            })
    wb.close()
    return out


def parse_visit_balance(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {"monitoring_visits": {}, "billing_milestones": [], "expense_forecast": []}

    if "Sheet1" in wb.sheetnames:
        w = wb["Sheet1"]
        # 스냅샷 라벨 (row1): Contracted, Actual (29Oct25), ... , Balance
        snap_cols = []  # (start_col, label)
        for c in range(1, w.max_column + 1):
            v = s(w.cell(1, c).value)
            if v and "Actual" in v:
                snap_cols.append((c, v.replace("Actual", "").strip(" ()")))
        rows = []
        group = None
        for r in range(3, w.max_row + 1):
            a = s(w.cell(r, 1).value)
            b = s(w.cell(r, 2).value)
            if a and (a[0].isupper() or a[0].isdigit()) and not b and a not in ("Total",):
                pass
            if a:
                group = a
            activity = b
            contracted = num(w.cell(r, 3).value)
            if activity is None and contracted is None:
                continue
            actuals = []
            for (c, label) in snap_cols:
                total = num(w.cell(r, c).value)
                kr = num(w.cell(r, c + 1).value)
                us = num(w.cell(r, c + 2).value)
                actuals.append({"snapshot": label, "total": total, "kr": kr, "us": us})
            rows.append({
                "group": group, "activity": activity,
                "contracted": contracted,
                "contracted_kr": num(w.cell(r, 4).value),
                "contracted_us": num(w.cell(r, 5).value),
                "actuals": actuals,
                "balance": num(w.cell(r, 18).value),
            })
        out["monitoring_visits"] = {
            "snapshots": [lbl for (_, lbl) in snap_cols],
            "rows": rows,
        }

    if "Sheet2" in wb.sheetnames:
        w = wb["Sheet2"]
        for r in range(2, w.max_row + 1):
            desc = s(w.cell(r, 4).value)
            amt = num(w.cell(r, 5).value)
            if not desc and not amt:
                continue
            out["billing_milestones"].append({
                "activity": s(w.cell(r, 1).value),
                "source_type": s(w.cell(r, 2).value),
                "category": s(w.cell(r, 3).value),
                "description": desc,
                "amount": amt,
                "budget_qty": num(w.cell(r, 6).value),
                "expected_month": s(w.cell(r, 8).value),
            })

    if "Sheet3" in wb.sheetnames:
        w = wb["Sheet3"]
        # row4 Actual/Forecast, row5 dates, rows 6-8 categories
        headers = [(c, d(w.cell(5, c).value), s(w.cell(4, c).value))
                   for c in range(3, w.max_column + 1) if w.cell(5, c).value]
        for r in range(6, 9):
            label = s(w.cell(r, 2).value)
            if not label:
                continue
            series = []
            for (c, date, kind) in headers:
                v = num(w.cell(r, c).value)
                if v is not None:
                    series.append({"date": date, "kind": kind, "value": v})
            out["expense_forecast"].append({"category": label, "series": series})
    wb.close()
    return out


def parse_subject_visits(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    records = []
    # 긴(long) 포맷 EDC 시트: 헤더에 SVDAT / SiteNumber / Subject 포함
    for name in wb.sheetnames:
        w = wb[name]
        header = {s(w.cell(1, c).value): c for c in range(1, min(w.max_column, 40) + 1)
                  if w.cell(1, c).value}
        if "SVDAT" not in header or "Subject" not in header:
            continue
        for r in range(2, w.max_row + 1):
            subj = s(w.cell(r, header["Subject"]).value)
            if not subj:
                continue
            records.append({
                "study": s(w.cell(r, header.get("studyid", 2)).value),
                "subject": subj,
                "site": s(w.cell(r, header.get("Site", 4)).value),
                "site_no": s(w.cell(r, header.get("SiteNumber", 5)).value),
                "visit_folder": s(w.cell(r, header.get("FolderName", header.get("InstanceName", 7))).value),
                "instance": s(w.cell(r, header.get("InstanceName", 7)).value),
                "visit_date": d(w.cell(r, header["SVDAT"]).value),
                "visit_done": s(w.cell(r, header.get("SVYN", 14)).value),
            })
    wb.close()
    return records


# ----------------------------------------------------------------------------- merge
def upsert(target, new, keyfn):
    idx = {keyfn(x): i for i, x in enumerate(target)}
    for rec in new:
        k = keyfn(rec)
        if k in idx:
            target[idx[k]] = rec
        else:
            idx[k] = len(target)
            target.append(rec)


def load_store():
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {"meta": {}, "contract": {}, "vendor_status": [], "quarterly": [],
            "payments": [], "monitoring_visits": {}, "billing_milestones": [],
            "expense_forecast": [], "subject_visits": [], "sources": []}


def norm_inv(x):
    return (x or "").strip()


def main():
    store = load_store()
    store["contract"] = contracts.build()

    files = sorted(SRC.glob("*"))
    processed = []
    for f in files:
        name = f.name.lower()
        try:
            if name.endswith((".xlsx", ".xlsm")):
                wb = openpyxl.load_workbook(f, read_only=True)
                sheets = set(wb.sheetnames)
                wb.close()
                if "0. Budget Summary" in sheets or any("IQVIA" in x for x in sheets):
                    b = parse_budget_tracker(f)
                    store["contract"]["tracker_meta"] = b["contract_meta"]
                    upsert(store["vendor_status"], b["vendor_status"], lambda x: x["vendor"])
                    upsert(store["quarterly"], b["quarterly"],
                           lambda x: (x["vendor"], x["year"], x["quarter"]))
                    upsert(store["payments"], b["direct_payments"],
                           lambda x: ("Direct", norm_inv(x.get("invoice_no")), x.get("milestone")))
                    upsert(store["payments"], b["ptc_invoices"],
                           lambda x: ("PTC", norm_inv(x.get("invoice_no"))))
                    processed.append((f.name, "budget_tracker"))
                elif any(x == "Sheet1" for x in sheets) and "Sheet2" in sheets:
                    v = parse_visit_balance(f)
                    store["monitoring_visits"] = v["monitoring_visits"]
                    store["billing_milestones"] = v["billing_milestones"]
                    store["expense_forecast"] = v["expense_forecast"]
                    processed.append((f.name, "visit_balance"))
                else:
                    recs = parse_subject_visits(f)
                    if recs:
                        upsert(store["subject_visits"], recs,
                               lambda x: (x["subject"], x["visit_folder"], x["visit_date"]))
                        processed.append((f.name, "subject_visits"))
                    else:
                        processed.append((f.name, "skipped(unknown xlsx)"))
            elif name.endswith(".pdf"):
                processed.append((f.name, "contract_pdf(→contracts.py)"))
        except Exception as e:  # noqa
            processed.append((f.name, f"ERROR: {e}"))

    store["sources"] = [f.name for f in files]
    store["meta"] = {
        "protocol": "TTK-CS-101",
        "sponsor_cro": "IQVIA (CRO)",
        "generated_note": "ingest.py 로 생성. 새 파일은 data/source/ 에 추가 후 재실행.",
    }
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    # 요약
    print("=== 처리한 파일 ===")
    for n, k in processed:
        print(f"  - {n}: {k}")
    print("\n=== store.json 요약 ===")
    print(f"  계약 버전        : {len(store['contract'].get('versions', []))}개, "
          f"유효={store['contract'].get('effective_version')}")
    print(f"  ATP 항목         : {len(store['contract'].get('atp_items', []))}")
    print(f"  vendor status    : {len(store['vendor_status'])}")
    print(f"  분기별 레코드    : {len(store['quarterly'])}")
    print(f"  지급/invoice     : {len(store['payments'])}")
    mv = store["monitoring_visits"]
    print(f"  모니터링 visit   : {len(mv.get('rows', []))} rows, "
          f"snapshots={mv.get('snapshots')}")
    print(f"  billing 마일스톤 : {len(store['billing_milestones'])}")
    print(f"  expense forecast : {len(store['expense_forecast'])}")
    print(f"  대상자 방문      : {len(store['subject_visits'])}")
    print(f"\n저장: {STORE}")


if __name__ == "__main__":
    main()
