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
                "paid_month": num(w.cell(r, 19).value),      # S
                "paid_date": d(w.cell(r, 20).value),          # T
                "paid_krw": num(w.cell(r, 21).value),         # U Paid Amount(₩)
                "paid_yn": s(w.cell(r, 22).value),            # V
                "approval_no": s(w.cell(r, 23).value),        # W 지출결의 #
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


# CRA ER 경비 카테고리 매핑 (reason code -> 사용자 카테고리)
EXPENSE_CATEGORY = {
    "MEALX": "식비", "HOTEL": "숙박비", "DAILA": "Per Diem",
    "TAXIX": "교통비", "BUS": "교통비", "TOLLX": "교통비", "PARKI": "교통비",
    "MILEA": "교통비", "CAREN": "교통비",
    "APFEE": "IRB/승인비", "LABFE": "기타", "COURI": "기타",
    "SUPPL": "기타", "OTPRI": "기타",
}


def _hdr(ws, ncols=45):
    return {s(ws.cell(1, c).value): c for c in range(1, ncols + 1) if ws.cell(1, c).value}


def parse_visit_activity(path):
    """연구비(대상자 방문별 지급) - B/C 소스."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    h = _hdr(ws, 20)
    recs = []
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        g = lambda k, dc: s(ws.cell(r, h.get(k, dc)).value)
        recs.append({
            "kind": "연구비", "site": g("Site #", 4), "country": g("Country ", 5),
            "payee": g("Payee", 3), "investigator": g("Investigator", 6),
            "patient": g("Patient", 7), "visit": g("Visit", 8),
            "visit_date": d(ws.cell(r, h.get("Visit Date", 9)).value),
            "invoice_no": g("Site Invoice #", 10),
            "amount": num(ws.cell(r, h.get("Visit Amount", 11)).value),
            "currency": g("Currency", 12), "payment_no": g("Payment #", 13),
            "payment_date": d(ws.cell(r, h.get("Payment Date", 14)).value),
            "adhoc": g("Ad hoc", 15),
        })
    wb.close()
    return recs


def parse_invoice(path):
    """Pass-through invoiceable (site invoice 상세) - B 소스."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    h = _hdr(ws, 15)
    recs = []
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value is None:
            continue
        g = lambda k, dc: s(ws.cell(r, h.get(k, dc)).value)
        recs.append({
            "kind": "invoiceable", "site": g("Site #", 4), "country": g("Country ", 5),
            "payee": g("Payee", 3), "investigator": g("Investigator", 6),
            "description": g("Description", 7),
            "amount": num(ws.cell(r, h.get("Amount", 8)).value),
            "currency": g("Currency", 9), "invoice_no": g("Site Invoice #", 10),
            "payment_no": g("Payment #", 11), "transition": g("Transition", 12),
            "payment_date": d(ws.cell(r, h.get("Payment Date", 13)).value),
        })
    wb.close()
    return recs


def parse_cra_visits(path):
    """CRA Site Visit Report - F 소스 (CRA/site/방문일/DOS/횟수)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    h = _hdr(ws, 40)
    recs = []
    for r in range(2, ws.max_row + 1):
        mon = s(ws.cell(r, h.get("Monitor", 1)).value)
        if not mon or "%Compliance" in str(mon):
            continue
        g = lambda k, dc: s(ws.cell(r, h.get(k, dc)).value)
        recs.append({
            "cra": mon, "site": g("Site #", 19), "pi": g("PI Name", 17),
            "account": g("Account", 18), "country": g("Protocol Country", 6),
            "city": g("City", 8), "visit_type": g("Visit Type", 20),
            "status": g("Visit Status", 21),
            "visit_start": d(ws.cell(r, h.get("Visit Start", 24)).value),
            "visit_end": d(ws.cell(r, h.get("Visit End", 25)).value),
            "dos": num(ws.cell(r, h.get("Days On Site", 26)).value),
            "report_status": g("Report Status", 29),
        })
    wb.close()
    return recs


def parse_pending_fees(path):
    """BWS 연구비/invoice ER 배치(INVFE) - 지급예정(paid date=TBD) 연구비.

    CRA ER 과 시트 구조가 같으나 Reason=INVFE(카테고리 91511) 이면 연구비 배치.
    Payment Date 컬럼이 없으므로 미지급(TBD)로 취급.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    h = _hdr(ws, 33)
    recs = []
    for r in range(3, ws.max_row + 1):
        seq = ws.cell(r, h.get("Seq #", 1)).value
        reason = s(ws.cell(r, h.get("Reason", 3)).value)
        if seq is None and reason is None:
            continue
        if reason != "INVFE":
            continue
        g = lambda k, dc: s(ws.cell(r, h.get(k, dc)).value)
        recs.append({
            "site": g("Investigator Site", 25), "patient": g("Patient ID", 22),
            "visit": g("Description", 8),
            "visit_date": d(ws.cell(r, h.get("Visit Date", 23)).value),
            "trans_date": d(ws.cell(r, h.get("Trans Date", 9)).value),
            "amount": num(ws.cell(r, h.get("Net Amount", 32)).value),
            "currency": "KRW",  # BWS 연구비 = 원(KRW)
            "country": g("Country", 10), "doc_id": g("Expenses Doc ID", 24),
            "seq": seq, "payment_date": None, "status": "TBD",
        })
    wb.close()
    return recs


def parse_cra_expenses(path):
    """CRA ER 경비 - E 소스 (CRA/site/카테고리/금액/일자)."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    h = _hdr(ws, 33)
    recs = []
    for r in range(3, ws.max_row + 1):
        seq = ws.cell(r, h.get("Seq #", 1)).value
        reason = s(ws.cell(r, h.get("Reason", 3)).value)
        if seq is None and reason is None:
            continue
        g = lambda k, dc: s(ws.cell(r, h.get(k, dc)).value)
        recs.append({
            "seq": seq, "code": s(ws.cell(r, h.get("Category", 2)).value),
            "reason": reason, "group": EXPENSE_CATEGORY.get(reason, "기타"),
            "cra": g("Incurring Person", 11), "empl_id": g("Empl ID", 12),
            "description": g("Description", 8), "country": g("Country", 10),
            "trans_date": d(ws.cell(r, h.get("Trans Date", 9)).value),
            "visit_date": d(ws.cell(r, h.get("Visit Date", 23)).value),
            "amount": num(ws.cell(r, h.get("Amount", 15)).value),
            "net_amount": num(ws.cell(r, h.get("Net Amount", 32)).value),
            "patient_id": g("Patient ID", 22), "site": g("Investigator Site", 25),
            "doc_id": g("Expenses Doc ID", 24),
        })
    wb.close()
    return recs


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
    base = {"meta": {}, "contract": {}, "vendor_status": [], "quarterly": [],
            "payments": [], "monitoring_visits": {}, "billing_milestones": [],
            "expense_forecast": [], "subject_visits": [],
            "investigator_fees": [], "pass_through_invoices": [],
            "cra_visits": [], "cra_expenses": [], "pending_fees": [], "sources": []}
    if STORE.exists():
        loaded = json.loads(STORE.read_text(encoding="utf-8"))
        base.update(loaded)  # 기존 데이터 유지 + 신규 키 기본값 보장
    return base


def norm_inv(x):
    return str(x).strip() if x is not None else ""


def main():
    store = load_store()
    store["contract"] = contracts.build()
    # IQVIA(CRO) CO/CNF 변경이력 (하위그룹 D)
    try:
        import iqvia as iqvia_mod  # noqa: E402
        iv = iqvia_mod.parse_iqvia_root(SRC / "iqvia")
        if iv:
            store["contract"]["cnf_versions"] = iv
    except Exception as e:  # noqa
        print("IQVIA CNF 파싱 경고:", e)

    files = sorted(SRC.glob("*"))
    processed = []
    for f in files:
        name = f.name.lower()
        try:
            if name.endswith((".xlsx", ".xlsm")):
                wb = openpyxl.load_workbook(f, read_only=True)
                sheets = set(wb.sheetnames)
                # 활성 시트 헤더로 파일 유형 판별
                aws = wb.active
                hdr = {aws.cell(1, c).value for c in range(1, min(aws.max_column, 45) + 1)}
                wb.close()
                if "0. Budget Summary" in sheets or any("IQVIA" in str(x) for x in sheets):
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
                elif "PATIENT ACTIVITY" in sheets or "Visit Amount" in hdr:
                    recs = parse_visit_activity(f)
                    upsert(store["investigator_fees"], recs,
                           lambda x: (norm_inv(x.get("payment_no")), x.get("patient"),
                                      x.get("visit"), x.get("amount")))
                    processed.append((f.name, f"visit_activity ({len(recs)} 연구비)"))
                elif "PASS THROUGH" in sheets or ("Description" in hdr and "Site Invoice #" in hdr):
                    recs = parse_invoice(f)
                    upsert(store["pass_through_invoices"], recs,
                           lambda x: (norm_inv(x.get("invoice_no")), x.get("description"),
                                      x.get("amount"), norm_inv(x.get("payment_no"))))
                    processed.append((f.name, f"invoice ({len(recs)} invoiceable)"))
                elif "Monitor" in hdr and "Days On Site" in hdr:
                    recs = parse_cra_visits(f)
                    upsert(store["cra_visits"], recs,
                           lambda x: (x.get("cra"), x.get("site"), x.get("visit_type"),
                                      x.get("visit_start")))
                    processed.append((f.name, f"cra_visits ({len(recs)} F)"))
                elif "Incurring Person" in hdr or "Investigator Site" in hdr:
                    # INVFE(연구비 배치) vs CRA 경비 구분: Reason 컬럼 확인
                    wb2 = openpyxl.load_workbook(f, read_only=True, data_only=True)
                    ws2 = wb2.active
                    rcol = next((c for c in range(1, 10) if ws2.cell(1, c).value == "Reason"), 3)
                    reasons = {ws2.cell(r, rcol).value for r in range(3, min(ws2.max_row, 40) + 1)}
                    wb2.close()
                    if "INVFE" in reasons:
                        recs = parse_pending_fees(f)
                        upsert(store["pending_fees"], recs,
                               lambda x: (norm_inv(x.get("doc_id")), x.get("seq"),
                                          x.get("patient"), x.get("visit"), x.get("amount")))
                        processed.append((f.name, f"pending_fees ({len(recs)} 지급예정)"))
                    else:
                        recs = parse_cra_expenses(f)
                        upsert(store["cra_expenses"], recs,
                               lambda x: (norm_inv(x.get("doc_id")), x.get("seq")))
                        processed.append((f.name, f"cra_expenses ({len(recs)} E)"))
                elif "Sheet1" in sheets and "Sheet2" in sheets:
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
                        processed.append((f.name, f"subject_visits ({len(recs)})"))
                    else:
                        processed.append((f.name, "skipped(unknown xlsx)"))
            elif name.endswith(".pdf"):
                processed.append((f.name, "contract_pdf(→contracts.py)"))
            elif name.endswith(".docx"):
                processed.append((f.name, "contract_docx(→contracts.py)"))
        except Exception as e:  # noqa
            processed.append((f.name, f"ERROR: {e}"))

    store["sources"] = [f.name for f in files]

    # 사이트 레지스트리 (site# -> name/country)
    sites = {}
    for x in store["investigator_fees"] + store["pass_through_invoices"]:
        if x.get("site"):
            sites.setdefault(str(x["site"]), {"name": x.get("payee"), "country": x.get("country")})
    for v in store["cra_visits"]:
        if v.get("site"):
            sites.setdefault(str(v["site"]), {"name": v.get("account"), "country": v.get("country")})
    store["sites"] = sites

    # CTA(기관 임상시험계약) 레지스트리
    #  - data/source/cta/Site <번호>/ 폴더가 있으면 자동 파싱(폴더 우선)
    #  - 폴더가 없는 site 는 site_cta.json 의 수기 입력값 유지
    import cta as cta_mod  # noqa: E402
    cta_path = ROOT / "data" / "site_cta.json"
    existing = json.loads(cta_path.read_text(encoding="utf-8")) if cta_path.exists() else {}
    reg = existing.get("sites", {}) if isinstance(existing, dict) else {}
    # 폴더 자동 파싱
    parsed = cta_mod.parse_cta_root(SRC / "cta")
    cta_source = {}
    for s in sorted(set(sites) | set(reg) | set(parsed)):
        if s in parsed:
            entry = parsed[s]
            # 기관명은 실제 지급/CRA 데이터 우선(계약 템플릿 Institution 오기재 방지)
            entry["cta_institution"] = entry.get("name")
            entry["name"] = (sites.get(s) or {}).get("name") or entry.get("name") or (reg.get(s) or {}).get("name")
            cta_source[s] = entry
        else:
            cta_source[s] = reg.get(s) or {"name": (sites.get(s) or {}).get("name"), "ctas": []}
    out = {"_comment": "CTA(기관 임상시험계약). data/source/cta/Site <번호>/ 폴더는 자동 파싱(폴더 우선). "
                       "폴더가 없는 site 는 여기 ctas 배열에 {version, effective_date, items:[{item,amount}]} 수기 입력.",
           "sites": cta_source}
    cta_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    store["site_cta"] = out
    store["cta_counts"] = {s: len(v.get("ctas", [])) for s, v in cta_source.items() if v.get("ctas")}

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
    print(f"  연구비(방문별)   : {len(store['investigator_fees'])}")
    print(f"  invoiceable      : {len(store['pass_through_invoices'])}")
    print(f"  CRA visit(F)     : {len(store['cra_visits'])}")
    print(f"  CRA 경비(E)      : {len(store['cra_expenses'])}")
    print(f"\n저장: {STORE}")


if __name__ == "__main__":
    main()
