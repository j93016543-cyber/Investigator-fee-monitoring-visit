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


def _cta_from_files(version, files):
    dates = []
    for f in files:
        dates += parse_dates(f.name)
    eff = max(dates).isoformat() if dates else None
    items, meta = {}, {}
    for f in files:
        if f.suffix.lower() in XLS_EXTS and not f.name.startswith("~"):
            it, mt = extract_items(f)
            items.update(it)
            if mt and not meta:
                meta = mt
    return {
        "version": version,
        "effective_date": eff,
        "protocol_version": meta.get("protocol_version"),
        "institution": meta.get("institution"),
        "pi": meta.get("pi"),
        "items": [{"item": k, "amount": v} for k, v in items.items()],
        "n_files": len([f for f in files if f.is_file()]),
    }


def parse_site_folder(site_dir):
    """'Site <번호>' 폴더 → ctas 리스트.

    - 버전 하위폴더(Initial / Amd1 / AMD#2 ...)가 있으면 폴더별 1개 CTA
    - 하위폴더가 없고 파일이 site 폴더 바로 아래 있으면(초기 CTA만) → 'Initial' 1개
    """
    ctas = []
    subdirs = sorted([d for d in site_dir.iterdir() if d.is_dir()])
    if subdirs:
        # 버전 폴더별 1개 CTA. site 루트의 낱개 문서(NL/노트 등)는 무시.
        for ver_dir in subdirs:
            ver = re.sub(r"^\d+(?:[.\)]\s*|\s+)", "", ver_dir.name).strip()  # "1. "/"01 "/"4.X"/"1) " 제거
            ctas.append(_cta_from_files(ver, list(ver_dir.rglob("*"))))
    else:
        # 하위폴더 없음 = 초기 CTA만 → site 루트 파일을 하나의 CTA로
        root_files = [f for f in site_dir.iterdir() if f.is_file()]
        if root_files:
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
