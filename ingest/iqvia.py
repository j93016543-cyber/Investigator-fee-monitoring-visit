"""
IQVIA(CRO) 계약 변경이력 파서 - 하위그룹 D 소스
================================================

data/source/iqvia/<CNF 폴더>/ 를 스캔해서 IQVIA CO/CNF(Change Notification Form)
버전별 effective date + Budget Grid(항목별 Revised 단가/총액)를 추출한다.

- version        : CNF 폴더명 (CNF initial / CNF1 / CNF 2 / CNF 3)
- effective_date : 폴더 내 파일명 최신 날짜(FE 일자)
- budget         : Budget Grid 요약(Project Grand Total 까지) 항목별 Revised 총액

새 CO/CNF 를 받으면 data/source/iqvia/ 에 폴더째 넣으면 자동 인식된다.
"""
import re
from pathlib import Path

import cta as cta_mod  # open_workbook, parse_dates 재사용


def parse_grid(path):
    """CNF Budget Grid(첫 시트)에서 항목별 Revised 예산 추출 (Grand Total 까지)."""
    try:
        wb = cta_mod.open_workbook(path)
    except Exception:
        return []
    ws = wb.worksheets[0]
    # 헤더행: col B 'Project Costs'
    hr = None
    for r in range(1, 8):
        if "Project Costs" in str(ws.cell(r, 2).value or ""):
            hr = r
            break
    if not hr:
        wb.close()
        return []
    rows = []
    for r in range(hr + 1, ws.max_row + 1):
        b = ws.cell(r, 2).value
        if not isinstance(b, str) or not b.strip():
            continue
        name = b.strip()
        unit = ws.cell(r, 3).value
        qty = ws.cell(r, 4).value
        uc = ws.cell(r, 5).value
        tot = ws.cell(r, 6).value
        if "Grand Total" in name:
            kind = "total"
        elif "Sub-total" in name:
            kind = "subtotal"
        elif unit is None and tot is None and uc is None:
            kind = "section"
        else:
            kind = "item"
        rows.append({
            "item": name,
            "unit": unit if isinstance(unit, str) else None,
            "qty": qty if isinstance(qty, (int, float)) else None,
            "unit_cost": round(uc, 2) if isinstance(uc, (int, float)) else None,
            "total": round(tot, 2) if isinstance(tot, (int, float)) else None,
            "kind": kind,
        })
        if "Grand Total" in name:
            break
    wb.close()
    return rows


def parse_iqvia_root(root):
    """data/source/iqvia/ 스캔 → CNF 버전 리스트."""
    if not root.exists():
        return []
    # 실제 CNF 폴더들이 root 바로 아래 또는 한 단계 안에 있을 수 있음
    base = root
    subs = [d for d in root.iterdir() if d.is_dir()]
    if len(subs) == 1 and not any("CNF" in d.name for d in subs):
        base = subs[0]
    versions = []
    for vdir in sorted([d for d in base.iterdir() if d.is_dir()]):
        files = list(vdir.rglob("*"))
        dates = []
        for f in files:
            dates += cta_mod.parse_dates(f.name)
        eff = max(dates).isoformat() if dates else None
        budget = []
        grand = None
        for f in files:
            if f.suffix.lower() in (".xlsx", ".xlsm", ".xls") and not f.name.startswith("~"):
                budget = parse_grid(f)
                if budget:
                    gt = next((x for x in budget if x["kind"] == "total"), None)
                    grand = gt["total"] if gt else None
                    break
        versions.append({
            "version": vdir.name.strip(),
            "effective_date": eff,
            "grand_total": grand,
            "budget": budget,
            "n_files": len([f for f in files if f.is_file()]),
        })
    versions.sort(key=lambda v: v["effective_date"] or "")
    return versions
