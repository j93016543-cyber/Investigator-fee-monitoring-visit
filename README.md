# TTK-CS-101 연구비 · 모니터링 누적 트래커

IQVIA(CRO)로부터 매번 받는 엑셀/계약서 파일을 넣고 프로그램을 실행하면, 데이터를
표준 스키마로 추출해 **누적**하고 웹 대시보드로 시각화합니다.

- **연구비**: 분기별 지급 trend + 하위그룹 A(계약서·항목별 단가) / B(지급·invoice 기록, 계약 대조 음영) / C(대상자·방문 tracker)
- **모니터링**: SIV/IMV/COV 계약 대비 실적 trend + 하위그룹 D(계약·항목별 비용) / E(CRA 경비) / F(visit tracker, 계약 대비 잔여 음영)

## 빠른 사용법

```bash
# 1) 새로 받은 IQVIA 파일을 data/source/ 에 넣는다 (기존 파일 교체 또는 신규 추가)
# 2) 데이터 누적
python3 ingest/ingest.py
# 3) 대시보드 빌드 (자체 완결형 HTML)
python3 dashboard/build.py
# 4) dashboard/index.html 을 브라우저로 열기
```

## 폴더 구조

```
data/source/          IQVIA 원본 파일 (누적 입력)
data/store.json       추출·누적된 표준 데이터 (자동 생성)
ingest/ingest.py      누적 수집 프로그램 (엑셀 파싱 + upsert)
ingest/contracts.py   계약서 데이터 (MSA/ATP/WO v3/CO1 버전 + 항목별 단가) — 사람이 검수
dashboard/build.py    store.json → index.html 빌드
dashboard/_template.html, app.js   대시보드 UI (CSS/렌더러)
dashboard/index.html  최종 대시보드 (Artifact)
```

## 지원 파일 & 매핑

| 원본 파일 | 성격 | 반영 위치 |
|---|---|---|
| `IQVIA_MSA.pdf` / `IQVIA_ATP.pdf` / `IQVIA_WOv3.docx` | 계약서 | A · D (버전·항목별 단가) → `contracts.py` |
| `project_budget_tracker.xlsx` | 예산/지급 원장 | 분기별 trend · A · B · D |
| `visit_balance.xlsx` | 모니터링 visit 계약/실적 | 모니터링 trend · F |
| `subject_visit_tracker.xlsx` | EDC 대상자 방문 | C |

## 누적(merge) 규칙

- **지급/invoice**: `invoice_no + cost_type` 로 upsert (중복 자동 제거)
- **분기별 planned/actual**: `vendor+year+quarter` 로 최신값 갱신
- **모니터링 visit 스냅샷**: 스냅샷 날짜별로 누적 (새 파일 = 새 스냅샷 컬럼)
- **대상자 방문**: `(subject, visit_folder, date)` 로 upsert
- **계약서**: `contracts.py` 의 `VERSIONS` / 항목표에 새 CO/WO 를 추가

## 음영(shading) 검증 규칙

- **B (지급 기록)**: 각 지급 금액이 유효 계약(WO v3)의 Payment Schedule·항목 단가와
  일치하면 <span>🟩 계약 일치</span>, 계약서에서 찾지 못하면 <span>🟨 확인 필요</span>.
- **F (모니터링 visit)**: 잔여가 음수면 🟥 계약 초과, 0이면 🟨 소진, 양수면 🟩 잔여.

## 현재 유효 계약 (Effective)

`CO1_23Sep2025` (Budget Tracker 기준). 계약서 계층: MSA(2024-07-13) → ATP(2024-06-25) →
**WO v3(2024-08-19, 항목별 단가 확정)** → CO1(2025-09-23, 현재 유효).

## 아직 데이터가 필요한 부분 (파일 주시면 자동 반영)

| 항목 | 필요 파일 | 현재 상태 |
|---|---|---|
| B: 방문별 **연구비 금액**·visit#·지급일별 음영 | `visit activity.xlsx`, `Invoice.xlsx` | 대상자·방문·방문일까지 반영, 금액 대기 |
| E: **CRA 경비 상세**(이름·모니터링일·식비/교통비/IRB/숙박비/Per Diem·금액) | `CRA 모니터링 ER.xlsx` | 계약 단가(대조 기준)만 표시 |
| F: **CRA별·Site별 DOS** 상세 | `CRA Site Visit Report.xlsx` | 계약 대비 visit 집계만 표시 |
