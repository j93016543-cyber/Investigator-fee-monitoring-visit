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
| `project_budget_tracker.xlsx` | 예산/지급 원장 | 분기별 trend · A · D |
| `visit_activity.xlsx` | 대상자 방문별 **연구비** 지급 | B · C |
| `Invoice.xlsx` (PASS THROUGH) | site invoiceable 상세 | B |
| `visit_balance.xlsx` | 모니터링 visit 계약/실적 | 모니터링 trend · 계약대비 잔여 |
| `subject_visit_tracker.xlsx` | EDC 대상자 방문 | (참고) |
| `CRA_monitoring_ER.xlsx` | CRA 경비정산 | **E** (식비·교통·IRB·숙박·Per Diem) |
| `CRA_Site_Visit_Report.xlsx` | CRA 모니터링 실적 | **F** (CRA별·site별 방문·DOS) |

## 누적(merge) 규칙

- **CRO 지급/invoice**: `invoice_no + cost_type` 로 upsert
- **연구비(방문별)**: `(payment_no, patient, visit, amount)` 로 upsert
- **invoiceable**: `(invoice_no, description, amount, payment_no)` 로 upsert
- **CRA visit(F)**: `(cra, site, visit_type, visit_start)` 로 upsert
- **CRA 경비(E)**: `(doc_id, seq)` 로 upsert
- **분기별 planned/actual**: `vendor+year+quarter` 로 최신값 갱신
- **모니터링 visit 스냅샷**: 스냅샷 날짜별로 누적 (새 파일 = 새 스냅샷 컬럼)
- **계약서**: `contracts.py` 의 `VERSIONS` / 항목표에 새 CO/WO 를 추가

## 하위그룹 A~F (대시보드)

**연구비 탭**
- **A**: 기관별(Site) CTA·지급 요약 — Total Investigator fee, 분기별(paid date 기준), 적용 CTA
- **B**: 지급 원장 (Country·site·subject·Visit#·Visit date·description·Amount·effective CTA version·CTA effective date)
- **C**: 기관·대상자·방문 매트릭스 (열=Visit#, 행=Visit date/effective CTA/Investigator fee/Invoiceable/Paid date, 지급일 음영)
- (참고) IQVIA WO 계약 — CRO 마스터 계약 버전 + 연구비 단가

**모니터링 탭** — 계약 대비 visit 잔여 / D: 모니터링 계약·단가 / E: CRA 경비 / F: CRA Site Visit Report

### CTA (기관 임상시험계약) 입력
site별 CTA는 IQVIA WO(CRO 계약)와 별개입니다. `data/site_cta.json` 의 각 site `ctas` 배열에
`{"version":"CTA v1.0","effective_date":"2024-01-15","items":[{"item":"C1D1","amount":1900}]}`
형식으로 추가하면 A/B/C 의 "effective CTA version / date" 가 방문·지급일 시점 기준으로 자동 채워집니다.

## 음영(shading) 검증 규칙

- **B (원장)**: 🟩 지급완료(payment date 존재) / 🟨 조정·취소(음수). 연구비 계약 대조는 C의 대상자 단가 기준.
- **C (지급 tracker)**: 🟩 지급일 존재. 각 방문에 지급일 시점의 **유효 계약 버전**(effective date 기준)을 표시.
- **E (CRA 경비)**: F 일치(해당 CRA·일자가 F 방문 ±10일 내) 🟩/🟨, 교통비가 계약 Monitoring Travel 단가($585/visit) 초과 시 🟨.
- **계약대비 잔여**: 잔여 음수 🟥 초과 · 0 🟨 소진 · 양수 🟩 잔여.

## 현재 유효 계약 (Effective)

`CO1_23Sep2025` (Budget Tracker 기준). 계약서 계층: MSA(2024-07-13) → ATP(2024-06-25) →
**WO v3(2024-08-19, 항목별 단가 확정)** → CO1(2025-09-23, 현재 유효).

## 현재 반영 현황

A~F 전부 실데이터로 채워져 있습니다 (연구비 방문별 지급, invoiceable, CRA 경비, CRA visit 실적 포함).
매월 새 파일을 같은 이름으로 `data/source/`에 넣고 `ingest.py` → `build.py` 재실행하면 누적 갱신됩니다.

### 참고 (선택적 개선 여지)
- CRA 경비의 식비/숙박/Per Diem **1일 상한 rate**가 계약서에 명시돼 있으면 알려주세요 —
  현재는 교통비만 계약 Monitoring Travel 단가($585/visit)로 대조합니다.
- 통화: 연구비/ invoiceable은 USD·KRW 혼재 → 통화별로 분리 집계합니다.
