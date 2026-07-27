"""
CTA(기관별 임상시험계약) 폴더 파서 - 하위그룹 A 소스
=====================================================

data/source/cta/Site <번호>/<버전 폴더>/... 구조를 스캔해서 site 별 CTA 버전
(version, effective_date, protocol_version, institution, PI, 항목별 비용)을 추출한다.

- version        : 버전 폴더명 (Initial / Amd1_PA V7.0 / CTA AMD#2_PA8 ...)
- effective_date : 폴더 내 파일명에서 파싱한 가장 늦은 날짜(= 서명/FE 일자)
- items          : budget 엑셀의 (항목, Selected Cost) 목록

새 site 는 data/source/cta/ 에 'Site <번호>' 폴더째 넣으면 자동 인식된다.
"""
import re
import shutil
import datetime
import tempfile
import subprocess
from pathlib import Path

import openpyxl

XLS_EXTS = (".xlsx", ".xlsm", ".xls")


def open_workbook(path):
    """budget 엑셀 열기. .xls(실제로는 xlsx인 파일 포함) 도 처리.
    1) .xlsx/.xlsm → 그대로
    2) .xls → 복사 후 .xlsx 로 시도(확장자만 다른 경우 대부분 성공)
    3) 실패 시 libreoffice 로 xlsx 변환
    """
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        return openpyxl.load_workbook(path, data_only=True)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    shutil.copy(path, tmp.name)
    try:
        return openpyxl.load_workbook(tmp.name, data_only=True)
    except Exception:
        pass
    # libreoffice 변환 (진짜 레거시 .xls)
    outdir = tempfile.mkdtemp()
    try:
        subprocess.run(["libreoffice", "--headless", "--convert-to", "xlsx",
                        "--outdir", outdir, str(path)],
                       capture_output=True, timeout=120)
        conv = list(Path(outdir).glob("*.xlsx"))
        if conv:
            return openpyxl.load_workbook(conv[0], data_only=True)
    except Exception:
        pass
    raise ValueError(f"cannot open {path.name}")

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_RE = re.compile(r"(\d{1,2})(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(\d{4}|\d{2})", re.I)


def parse_dates(text):
    out = []
    for d, mon, y in DATE_RE.findall(text):
        yr = int(y);  yr += 2000 if yr < 100 else 0
        try:
            out.append(datetime.date(yr, MONTHS[mon.lower()], int(d)))
        except ValueError:
            pass
    return out


def _meta(ws):
    """budget 시트 상단 메타(Protocol Version / Institution / PI)."""
    m = {}
    for r in range(1, 14):
        for c in range(1, 4):
            v = ws.cell(r, c).value
            if not isinstance(v, str):
                continue
            key = v.strip().rstrip(":")
            nxt = ws.cell(r, c + 1).value
            if key == "Protocol Version" and nxt:
                m["protocol_version"] = str(nxt).strip()
            elif key == "Institution" and nxt:
                m["institution"] = str(nxt).strip()
            elif key == "Principal Investigator" and nxt:
                m["pi"] = str(nxt).strip()
    return m


def extract_items(path):
    """budget 엑셀에서 (항목, Selected Cost) 추출. 두 레이아웃 지원."""
    items = {}
    meta = {}
    try:
        wb = open_workbook(path)
    except Exception:
        return items, meta
    for ws in wb.worksheets:
        if not meta:
            meta = _meta(ws)
        # 레이아웃 1: 헤더에 'Selected Cost' + 'Trial Procedures'
        hdr_row = cost_col = name_col = None
        for r in range(1, min(ws.max_row, 20) + 1):
            for c in range(1, min(ws.max_column, 34) + 1):
                v = ws.cell(r, c).value
                if isinstance(v, str):
                    if "Selected Cost" in v:
                        hdr_row, cost_col = r, c
                    elif "Trial Procedures" in v:
                        name_col = c
            if hdr_row and name_col:
                break
        if hdr_row and cost_col and name_col:
            for r in range(hdr_row + 1, ws.max_row + 1):
                nm = ws.cell(r, name_col).value
                cost = ws.cell(r, cost_col).value
                if isinstance(nm, str) and nm.strip() and isinstance(cost, (int, float)):
                    items.setdefault(nm.strip(), round(float(cost), 2))
        # 레이아웃 2: 'Overhead Percent' 있는 요약시트 → col A 항목 + col B 숫자
        elif any("Overhead Percent" in str(ws.cell(r, 1).value or "")
                 for r in range(1, min(ws.max_row, 12) + 1)):
            for r in range(13, ws.max_row + 1):
                a = ws.cell(r, 1).value
                b = ws.cell(r, 2).value
                if isinstance(a, str) and a.strip() and isinstance(b, (int, float)):
                    items.setdefault(a.strip(), round(float(b), 2))
    wb.close()
    return items, meta


MONTHS_FULL = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"])}


def pdf_meta(path):
    """CTA amendment PDF에서 명시적 effective date / protocol version 추출.
    - 'payable from <Month D, YYYY>' 또는 'is effective as of <Month D, YYYY>' (개정 자체의 발효일)
    - 'Protocol Version X[.Y]'
    원계약 발효일('effective as of ...' 앞에 is 없음)은 잡지 않도록 패턴 제한.
    """
    try:
        from pdfminer.high_level import extract_text
        t = extract_text(str(path), page_numbers=[0, 1, 2, 3])
    except Exception:
        return None, None
    eff = None
    m = (re.search(r"payable from ([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", t)
         or re.search(r"\bis effective as of ([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", t))
    if m and m.group(1).lower() in MONTHS_FULL:
        try:
            eff = datetime.date(int(m.group(3)), MONTHS_FULL[m.group(1).lower()], int(m.group(2))).isoformat()
        except ValueError:
            pass
    pv = re.search(r"Protocol Version (\d+(?:\.\d+)?)", t)
    return eff, (f"Version {pv.group(1)}" if pv else None)


def _cta_from_files(version, files):
    dates = []
    for f in files:
        dates += parse_dates(f.name)
    eff = max(dates).isoformat() if dates else None
    items, meta = {}, {}
    vcosts = {}
    for f in files:
        if f.suffix.lower() in XLS_EXTS and not f.name.startswith("~"):
            it, mt = extract_items(f)
            items.update(it)
            if mt and not meta:
                meta = mt
            for lab, amts in compute_visit_costs(f).items():
                vcosts.setdefault(lab, set()).update(amts)
    # PDF-only 버전(budget xlsx 없음): PDF의 'effective and payable from' / 'is effective as of'
    # 발효일과 Protocol Version 을 사용. (xlsx 폴더는 FE 파일명 날짜 유지 — 순서 안정)
    pdfs = [f for f in files if f.suffix.lower() == ".pdf"
            and any(k in f.name.lower() for k in ("cta", "amendment", "agreement", "clinical_trial"))]
    for f in pdfs:
        peff, ppv = pdf_meta(f)
        if ppv and not meta.get("protocol_version"):
            meta["protocol_version"] = ppv
        if peff and not items:   # 예산 xlsx 없는 PDF-only 버전만 날짜 override
            eff = peff
        if peff:
            break
    return {
        "version": version,
        "effective_date": eff,
        "protocol_version": meta.get("protocol_version"),
        "institution": meta.get("institution"),
        "pi": meta.get("pi"),
        "items": [{"item": k, "amount": v} for k, v in items.items()],
        # 방문별 계약금액(참고): 레지멘/시트별 값이 여럿이면 리스트
        "visit_costs": {k: sorted(v) for k, v in vcosts.items()},
        "n_files": len([f for f in files if f.is_file()]),
    }


def _isnum(v):
    return isinstance(v, (int, float))


def _norm_visit(h):
    h = str(h).replace("\n", " ")
    if "creen" in h.lower():
        return "Screening"
    m = re.search(r"C(\d+).*?Day\s*(\d+)", h)
    if m:
        return f"C{m.group(1)}D{m.group(2)}"
    return None


def compute_visit_costs(path):
    """budget 엑셀의 상세 매트릭스(절차×방문)에서 방문별 계약금액 계산.
    반환: {visit_label: set(금액)}  — 절차표의 'Total' 행 전까지만 합산.
    """
    out = {}
    try:
        wb = open_workbook(path)
    except Exception:
        return out
    for ws in wb.worksheets:
        # 헤더행: 'Trial Procedures' + 'Selected Cost'
        hr = costcol = None
        for r in range(1, min(ws.max_row, 25) + 1):
            has_proc = has_cost = False
            for c in range(1, min(ws.max_column, 10) + 1):
                v = str(ws.cell(r, c).value or "")
                if "Trial Procedures" in v:
                    has_proc = True
                if "Selected Cost" in v:
                    has_cost = True
                    costcol = c
            if has_proc and has_cost:
                hr = r
                break
        if not hr or not costcol:
            continue
        # 첫 방문 컬럼
        firstvisit = None
        for c in range(costcol + 1, ws.max_column + 1):
            if _norm_visit(ws.cell(hr, c).value):
                firstvisit = c
                break
        if not firstvisit:
            continue
        for c in range(firstvisit, ws.max_column + 1):
            lab = _norm_visit(ws.cell(hr, c).value)
            if not lab:
                continue
            tot = 0.0
            for r in range(hr + 1, ws.max_row + 1):
                b = str(ws.cell(r, 2).value or "")
                if "Total" in b or "Sub-total" in b:
                    break
                cost = ws.cell(r, costcol).value
                q = ws.cell(r, c).value
                if _isnum(cost) and _isnum(q):
                    tot += cost * q
            if tot > 0:
                out.setdefault(lab, set()).add(round(tot, 2))
    wb.close()
    return out


def parse_site_folder(site_dir):
    """'Site <번호>' 폴더 → ctas 리스트.

    - 버전 하위폴더(Initial / Amd1 / AMD#2 ...)가 있으면 폴더별 1개 CTA
    - 하위폴더가 없고 파일이 site 폴더 바로 아래 있으면(초기 CTA만) → 'Initial' 1개
    """
    ctas = []
    subdirs = sorted([d for d in site_dir.iterdir() if d.is_dir()])
    for ver_dir in subdirs:
        ver = re.sub(r"^\d+(?:[.\)]\s*|\s+)", "", ver_dir.name).strip()  # "1. "/"01 "/"4.X"/"1) " 제거
        ctas.append(_cta_from_files(ver, list(ver_dir.rglob("*"))))
    # site 루트 파일: 실제 CTA/agreement/budget 문서가 있으면 Initial 로 인정.
    # (NL/노트 등 잡문서만 있으면 무시)
    root_files = [f for f in site_dir.iterdir() if f.is_file()]
    is_cta_doc = lambda f: re.search(r"cta|agreement|budget|regimen|clinical_trial", f.name, re.I)
    if root_files and any(is_cta_doc(f) for f in root_files):
        if not any((c.get("version") or "").lower().startswith("initial") for c in ctas):
            ctas.append(_cta_from_files("Initial", root_files))
    ctas.sort(key=lambda c: c["effective_date"] or "")
    return ctas


def parse_cta_root(cta_root):
    """data/source/cta/ 전체 스캔 → {site#: {name, ctas}}."""
    out = {}
    if not cta_root.exists():
        return out
    for site_dir in sorted(cta_root.iterdir()):
        if not site_dir.is_dir():
            continue
        m = re.search(r"(\d{3,4})", site_dir.name)
        if not m:
            continue
        site = m.group(1)
        ctas = parse_site_folder(site_dir)
        name = None
        for c in ctas:
            if c.get("institution"):
                name = c["institution"]
                break
        out[site] = {"name": name, "ctas": ctas, "source_folder": site_dir.name}
    return out
