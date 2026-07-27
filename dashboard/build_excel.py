#!/usr/bin/env python3
"""
data/store.json + data/site_cta.json  ->  exports/TTK-CS-101_tracker.xlsx
대시보드(A~F)를 엑셀 워크북으로 출력 (음영 포함).
사용법: python3 dashboard/build_excel.py
"""
import json
import re
import datetime
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
store = json.loads((ROOT / "data" / "store.json").read_text(encoding="utf-8"))
sct_path = ROOT / "data" / "site_cta.json"
scts = json.loads(sct_path.read_text(encoding="utf-8")).get("sites", {}) if sct_path.exists() else {}
C = store["contract"]

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="0D7680")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
SEC_FILL = PatternFill("solid", fgColor="D9E4E6")
SUB_FILL = PatternFill("solid", fgColor="EDF2F3")
TOT_FILL = PatternFill("solid", fgColor="CFDBDE")
EFF_FILL = PatternFill("solid", fgColor="E2F0F1")
SHADE = {"good": PatternFill("solid", fgColor="D8EEE4"),
         "warn": PatternFill("solid", fgColor="FBECCB"),
         "crit": PatternFill("solid", fgColor="F7DDD7")}
THIN = Side(style="thin", color="D0D8DA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BASE = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)


def real_date(x):
    return x if (x and not str(x).startswith("2000-01-01")) else ""


def parse_visit(v):
    if not v:
        return ("", 99999)
    if re.search(r"screen", v, re.I):
        return ("Screening", 0)
    m = re.search(r"C(\d+).*?D\s*([0-9]+(?:_[0-9A-Za-z]+)?)", v, re.I)
    if m:
        cyc = int(m.group(1)); dn = int(re.match(r"\d+", m.group(2)).group())
        return (f"C{cyc}D{m.group(2)}", cyc * 1000 + dn)
    return (v[:14], 98000)


def cta_list(site):
    return (scts.get(str(site), {}) or {}).get("ctas", [])


def cta_at(site, date):
    arr = sorted([c for c in cta_list(site) if c.get("effective_date")], key=lambda c: c["effective_date"])
    if not arr:
        return None
    if not date:
        return arr[-1]
    out = None
    for c in arr:
        if c["effective_date"] <= date:
            out = c
    return out or arr[0]


def site_name(s):
    return (store.get("sites", {}).get(str(s)) or {}).get("name", "")


def numfmt(cell, kind):
    cell.number_format = {"usd": '#,##0.00', "usd0": '#,##0', "int": '#,##0'}.get(kind, 'General')


def sheet(wsname, headers, rows, widths=None, numcols=None, freeze="A2"):
    ws = wb.create_sheet(wsname)
    ws.sheet_view.showGridLines = False
    numcols = numcols or {}
    for j, h in enumerate(headers, 1):
        c = ws.cell(1, j, h); c.fill = HDR_FILL; c.font = HDR_FONT; c.border = BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, row in enumerate(rows, 2):
        rcls = row.get("_cls"); shade = row.get("_shade", {})
        for j, h in enumerate(headers, 1):
            cell = ws.cell(i, j, row.get(h))
            cell.font = BOLD if rcls in ("sec", "total") else BASE
            cell.border = BORDER
            cell.alignment = Alignment(horizontal="right" if j in numcols else "left", vertical="center")
            if j in numcols:
                numfmt(cell, numcols[j])
            fill = {"sec": SEC_FILL, "sub": SUB_FILL, "total": TOT_FILL, "eff": EFF_FILL}.get(rcls)
            if fill:
                cell.fill = fill
            if shade.get(h):
                cell.fill = SHADE[shade[h]]
    ws.freeze_panes = freeze
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w
    return ws


wb = openpyxl.Workbook()
fees = store.get("investigator_fees", [])
invs = store.get("pass_through_invoices", [])
env = C.get("payment_envelopes", {})

# ===== 0. 요약 =====
ws = wb.active; ws.title = "0. 요약"; ws.sheet_view.showGridLines = False
feeU = sum(x["amount"] for x in fees if x.get("currency") == "USD" and isinstance(x.get("amount"), (int, float)))
feeK = sum(x["amount"] for x in fees if x.get("currency") == "KRW" and isinstance(x.get("amount"), (int, float)))
ws["A1"] = "TTK-CS-101 · 연구비 & 모니터링 누적 트래커"
ws["A1"].font = Font(name=FONT, size=16, bold=True, color="0D7680")
ws["A2"] = f"Protocol {C.get('protocol','TTK-CS-101')} · CRO {C.get('vendor','')} · 계약번호 {C.get('contract_number','')}"
ws["A2"].font = Font(name=FONT, size=10, color="6D8388")
ws["A3"] = f"유효 계약: {C.get('effective_version')} (eff. {C.get('effective_date')})"
ws["A3"].font = Font(name=FONT, size=10, italic=True)
kpis = [
    ("연구비(Investigator Grants) 계약 총액", env.get("investigator_grants_total"), "usd0", "WO v3"),
    ("연구비 실지급 누계 (USD)", round(feeU, 2), "usd", "visit_activity! Visit Amount(K) 합"),
    ("연구비 실지급 누계 (KRW)", round(feeK), "int", "visit_activity! Visit Amount(K) 합"),
    ("Invoiceable(Professional) 최대", env.get("professional_specialty_max"), "usd0", "WO v3"),
    ("현재 IQVIA 계약 예산(최신 CO)", (C.get("cnf_versions") or [{}])[-1].get("grand_total"), "usd0", "IQVIA CNF 최신"),
    ("연구비 실지급 건수", len(fees), "int", "visit_activity rows"),
]
ws.cell(5, 1, "항목").font = HDR_FONT; ws.cell(5, 1).fill = HDR_FILL
ws.cell(5, 2, "값").font = HDR_FONT; ws.cell(5, 2).fill = HDR_FILL
ws.cell(5, 3, "출처").font = HDR_FONT; ws.cell(5, 3).fill = HDR_FILL
for k, (lab, val, kind, src) in enumerate(kpis):
    rr = 6 + k
    ws.cell(rr, 1, lab).font = BASE
    c = ws.cell(rr, 2, val); c.font = BOLD; numfmt(c, kind)
    ws.cell(rr, 3, src).font = Font(name=FONT, size=9, color="6D8388")
    for cc in range(1, 4):
        ws.cell(rr, cc).border = BORDER
r0 = 6 + len(kpis) + 2
ws.cell(r0, 1, "분기별 지급 연구비 (IQVIA, USD)").font = Font(name=FONT, size=12, bold=True)
r0 += 1
for j, h in enumerate(["연도-분기", "Planned", "Actual"], 1):
    c = ws.cell(r0, j, h); c.fill = HDR_FILL; c.font = HDR_FONT; c.border = BORDER
q = sorted([x for x in store.get("quarterly", []) if x["vendor"] == "IQVIA" and (x["planned"] or x["actual"])],
           key=lambda x: (x["year"], x["quarter"]))
for k, x in enumerate(q):
    rr = r0 + 1 + k
    ws.cell(rr, 1, f"{x['year']} Q{x['quarter']}").font = BASE
    for jj, key in [(2, "planned"), (3, "actual")]:
        cc = ws.cell(rr, jj, round(x[key], 2)); cc.font = BASE; cc.number_format = '#,##0'
    for cc in range(1, 4):
        ws.cell(rr, cc).border = BORDER
ws.column_dimensions["A"].width = 42; ws.column_dimensions["B"].width = 20; ws.column_dimensions["C"].width = 34
ws.freeze_panes = "A5"

sites_cta = sorted([s for s in scts if scts[s].get("ctas")], key=str)

# ===== A. CTA 변경이력 =====
rowsA = []
for s in sites_cta:
    rowsA.append({"CTA Version": f"Site {s} — {site_name(s) or scts[s].get('name','')}",
                  "_cls": "sec"})
    cs = sorted(scts[s]["ctas"], key=lambda c: c.get("effective_date") or "")
    eff = cta_at(s, None); prev = None
    for c in cs:
        n = len(c.get("items", []))
        delta = "" if prev is None else (f"+{n-prev}" if n - prev >= 0 else str(n - prev))
        rowsA.append({"CTA Version": c["version"], "Effective Date": c.get("effective_date") or "—",
                      "Protocol Ver.": c.get("protocol_version") or "—", "항목수": n or "—", "Δ항목": delta,
                      "_cls": "eff" if (eff and c["version"] == eff["version"]) else None})
        prev = n
sheet("A. CTA 변경이력", ["CTA Version", "Effective Date", "Protocol Ver.", "항목수", "Δ항목"],
      rowsA, widths=[44, 16, 28, 10, 10], numcols={4: "int"})

# ===== A2. CTA 항목별 비용 =====
rowsAI = []
for s in sites_cta:
    for c in sorted(scts[s]["ctas"], key=lambda c: c.get("effective_date") or ""):
        for it in c.get("items", []):
            rowsAI.append({"Site#": s, "CTA Version": c["version"], "Effective": c.get("effective_date") or "—",
                           "항목(Trial Procedure)": it.get("item"), "Selected Cost": it.get("amount")})
sheet("A2. CTA 항목별비용", ["Site#", "CTA Version", "Effective", "항목(Trial Procedure)", "Selected Cost"],
      rowsAI, widths=[8, 28, 12, 62, 16], numcols={5: "usd"})

# ===== B. 지급원장 =====
rowsB = []
for x in fees:
    lab, _ = parse_visit(x.get("visit")); vd = real_date(x.get("visit_date"))
    c = cta_at(x.get("site"), vd or x.get("payment_date"))
    neg = isinstance(x.get("amount"), (int, float)) and x["amount"] < 0
    rowsB.append({"Country": x.get("country"), "site name": site_name(x.get("site")), "site #": x.get("site"),
                  "구분": "Investigator fee", "subject #": x.get("patient"), "Visit #": lab, "Visit date": vd,
                  "description": x.get("visit"), "Amount": x.get("amount"), "Cur": x.get("currency"),
                  "effective CTA": c["version"] if c else "—", "CTA eff date": c["effective_date"] if c else "—",
                  "Payment #": x.get("payment_no"), "Paid date": x.get("payment_date"),
                  "_shade": {"Amount": "warn" if neg else ("good" if x.get("payment_date") else None)}})
for x in invs:
    c = cta_at(x.get("site"), x.get("payment_date"))
    rowsB.append({"Country": x.get("country"), "site name": site_name(x.get("site")), "site #": x.get("site"),
                  "구분": "Invoice", "subject #": "", "Visit #": "", "Visit date": "",
                  "description": x.get("description"), "Amount": x.get("amount"), "Cur": x.get("currency"),
                  "effective CTA": c["version"] if c else "—", "CTA eff date": c["effective_date"] if c else "—",
                  "Payment #": x.get("payment_no"), "Paid date": x.get("payment_date"),
                  "_shade": {"Amount": "good" if x.get("payment_date") else None}})
sheet("B. 지급원장",
      ["Country", "site name", "site #", "구분", "subject #", "Visit #", "Visit date", "description",
       "Amount", "Cur", "effective CTA", "CTA eff date", "Payment #", "Paid date"], rowsB,
      widths=[12, 34, 7, 15, 12, 10, 12, 34, 14, 6, 24, 12, 12, 12], numcols={9: "usd"})

# ===== C. 대상자·방문 (계약금액 대조) =====
idx = {}
for x in fees:
    s, pt = x.get("site"), x.get("patient")
    if not s or not pt:
        continue
    lab, order = parse_visit(x.get("visit"))
    o = idx.setdefault((s, pt, lab), {"site": s, "pt": pt, "label": lab, "region": x.get("country"),
                                      "cur": x.get("currency"), "u": 0.0, "k": 0.0, "dates": [], "vdate": "", "order": order})
    if x.get("currency") == "KRW":
        o["k"] += x.get("amount") or 0
    else:
        o["u"] += x.get("amount") or 0
    if x.get("payment_date"):
        o["dates"].append(x["payment_date"])
    if not o["vdate"]:
        o["vdate"] = real_date(x.get("visit_date"))
rowsC = []
for o in sorted(idx.values(), key=lambda o: (str(o["site"]), str(o["pt"]), o["order"])):
    vd = o["vdate"] or (sorted(o["dates"])[0] if o["dates"] else "")
    c = cta_at(o["site"], vd)
    cur = o["cur"] or "USD"
    actual = o["k"] if cur == "KRW" else o["u"]
    costs = c.get("visit_costs", {}).get(o["label"]) if c else None
    match = None
    if costs and actual:
        aa = abs(actual); mn = costs[0]
        if any(abs(aa - xx) <= max(1, xx * 0.02) for xx in costs):
            match = "good"
        elif aa < mn * 0.98:
            match = "crit"
        else:
            match = "warn"
    paid = sorted([x for x in o["dates"] if x])
    rowsC.append({"Site#": o["site"], "기관": site_name(o["site"]), "대상자": o["pt"], "Region": o["region"],
                  "Visit #": o["label"], "Visit date": vd,
                  "effective CTA": c["version"] if c else "—", "CTA eff date": c["effective_date"] if c else "—",
                  "실지급 연구비": round(actual, 2) if actual else 0, "Cur": cur,
                  "CTA 계약금액": (f"{costs[0]:,.0f} ~ {costs[-1]:,.0f}" if costs and costs[0] != costs[-1]
                                 else (f"{costs[0]:,.0f}" if costs else "—")),
                  "대조": {"good": "일치", "warn": "초과", "crit": "미달"}.get(match, "—"),
                  "Paid date": paid[-1] if paid else "—",
                  "_shade": {"실지급 연구비": match, "대조": match}})
sheet("C. 대상자·방문",
      ["Site#", "기관", "대상자", "Region", "Visit #", "Visit date", "effective CTA", "CTA eff date",
       "실지급 연구비", "Cur", "CTA 계약금액", "대조", "Paid date"], rowsC,
      widths=[7, 30, 12, 14, 9, 12, 24, 12, 16, 6, 18, 8, 12], numcols={9: "usd"})

# ===== D. IQVIA 계약 =====
rowsD = []
rowsD.append({"항목": "■ 계약 버전 이력", "_cls": "sec"})
for v in C.get("versions", []):
    rowsD.append({"항목": v["version"], "Unit/유형": v.get("type"), "Effective": v.get("effective_date"),
                  "금액/총액": v.get("grand_total"), "비고": v.get("note"),
                  "_cls": "eff" if v.get("is_effective") else None})
rowsD.append({"항목": "■ IQVIA CO/CNF 변경이력 (Revised Grand Total)", "_cls": "sec"})
prev = None
for v in C.get("cnf_versions", []):
    g = v.get("grand_total")
    delta = "" if (prev is None or g is None) else (g - prev)
    rowsD.append({"항목": v["version"], "Effective": v.get("effective_date"), "금액/총액": g,
                  "비고": (f"Δ {delta:+,.0f}" if isinstance(delta, (int, float)) else "")})
    if g is not None:
        prev = g
rowsD.append({"항목": "■ 모니터링 Visit 단가 (WO v3)", "_cls": "sec"})
uc = C.get("monitoring_unit_costs", {})
uc_labels = [("Site Initiation Visit (SIV)", "SIV"), ("Site Qualification Visit (SQV)", "SQV"),
             ("SQV by Phone", "SQV_phone"), ("IMV One-Day", "IMV_1day"), ("IMV Two-Day", "IMV_2day"),
             ("Remote IMV One-Day", "IMV_remote_1day"), ("Remote IMV Two-Day", "IMV_remote_2day"),
             ("Close-Out Visit (COV)", "COV"), ("Monitoring Travel (per visit)", "Monitoring_Travel_per_visit"),
             ("Regulatory/IRB/EC (per site)", "Regulatory_IRB_EC_per_site")]
for lab, key in uc_labels:
    rowsD.append({"항목": lab, "금액/총액": uc.get(key)})
sheet("D. IQVIA 계약", ["항목", "Unit/유형", "Effective", "금액/총액", "비고"], rowsD,
      widths=[46, 14, 14, 16, 40], numcols={4: "usd"})

# ===== D2. IQVIA 지급 스케줄 =====
rowsPS = [{"예정월": x["month"], "Milestone": x["milestone"], "%": x["pct"], "Net Amount(USD)": x["amount"],
           "_cls": "total" if x["milestone"] == "Total" else None} for x in C.get("payment_schedule", [])]
sheet("D2. IQVIA 지급스케줄", ["예정월", "Milestone", "%", "Net Amount(USD)"], rowsPS,
      widths=[10, 52, 8, 18], numcols={3: "int", 4: "usd0"})

# ===== E. CRA 경비 =====
cvis = store.get("cra_visits", [])
cidx = {}
for v in cvis:
    cidx.setdefault(re.sub(r"[\s,]", "", str(v.get("cra", "")).lower()), []).append(v.get("visit_start"))


def fmatch(x):
    arr = cidx.get(re.sub(r"[\s,]", "", str(x.get("cra", "")).lower()))
    if not arr:
        return "warn"
    dt = x.get("visit_date") or x.get("trans_date")
    for vs in arr:
        try:
            if dt and vs and abs((datetime.date.fromisoformat(vs) - datetime.date.fromisoformat(dt)).days) <= 10:
                return "good"
        except Exception:
            pass
    return "warn"


rowsE = []
for x in store.get("cra_expenses", []):
    amt = x.get("net_amount") if x.get("net_amount") is not None else x.get("amount")
    m = fmatch(x)
    trav = x.get("group") == "교통비" and isinstance(amt, (int, float)) and amt > uc.get("Monitoring_Travel_per_visit", 1e9)
    rowsE.append({"CRA": x.get("cra"), "Site#": x.get("site"), "카테고리": x.get("group"), "Reason": x.get("reason"),
                  "Description": x.get("description"), "Trans Date": x.get("trans_date"), "Visit Date": x.get("visit_date"),
                  "금액(USD)": amt, "F일치": "일치" if m == "good" else "미확인",
                  "_shade": {"금액(USD)": "warn" if trav else None, "F일치": m}})
sheet("E. CRA경비", ["CRA", "Site#", "카테고리", "Reason", "Description", "Trans Date", "Visit Date", "금액(USD)", "F일치"],
      rowsE, widths=[16, 7, 12, 10, 34, 12, 12, 14, 10], numcols={8: "usd"})

# ===== F. CRA visit =====
rowsF = []
for v in sorted(cvis, key=lambda v: (str(v.get("cra")), str(v.get("site")), str(v.get("visit_start")))):
    rowsF.append({"CRA": v.get("cra"), "Site#": v.get("site"), "기관(Account)": v.get("account"), "PI": v.get("pi"),
                  "Visit Type": v.get("visit_type"), "Status": v.get("status"), "Visit Start": v.get("visit_start"),
                  "Visit End": v.get("visit_end"), "DOS": v.get("dos"), "Report": v.get("report_status")})
sheet("F. CRA visit", ["CRA", "Site#", "기관(Account)", "PI", "Visit Type", "Status", "Visit Start", "Visit End", "DOS", "Report"],
      rowsF, widths=[16, 7, 34, 20, 22, 16, 12, 12, 6, 12], numcols={9: "int"})

# ===== 모니터링 잔여 =====
mv = store.get("monitoring_visits", {})
snaps = mv.get("snapshots", [])
Mheaders = ["카테고리", "Activity", "계약"] + snaps + ["잔여"]
rowsM = []
for r in mv.get("rows", []):
    row = {"카테고리": ("" if r.get("activity") else r.get("group")) or "", "Activity": r.get("activity") or r.get("group") or "",
           "계약": r.get("contracted"), "잔여": r.get("balance")}
    for i, a in enumerate(r.get("actuals", [])):
        if i < len(snaps):
            row[snaps[i]] = a.get("total")
    bal = r.get("balance")
    row["_shade"] = {"잔여": ("crit" if (isinstance(bal, (int, float)) and bal < 0) else
                             ("warn" if bal == 0 else ("good" if isinstance(bal, (int, float)) else None)))}
    agg = str(r.get("group") or "").startswith(("Interim MV Sub-Total", "Total"))
    if agg:
        row["_cls"] = "total"
    rowsM.append(row)
numM = {3: "int"}
for i in range(len(snaps)):
    numM[4 + i] = "int"
numM[4 + len(snaps)] = "int"
sheet("모니터링 잔여", Mheaders, rowsM, widths=[16, 40, 8] + [11] * len(snaps) + [8], numcols=numM)

(ROOT / "exports").mkdir(exist_ok=True)
out = ROOT / "exports" / "TTK-CS-101_tracker.xlsx"
wb.save(out)
print("saved:", out, "sheets:", wb.sheetnames)
