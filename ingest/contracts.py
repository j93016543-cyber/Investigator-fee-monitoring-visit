"""
IQVIA 계약서 데이터 (하위그룹 A / D 소스)
==========================================

계약서 원본은 한글 임베디드 PDF(MSA/ATP) + Work Order docx(WOv3) 이며, 자동 추출이
어렵거나 표가 복잡하여 사람이 검수한 값을 여기에 구조화해 둔다.
새 Change Order(CO)/Work Order(WO)를 받으면 VERSIONS 와 (필요 시) 항목표를 갱신한다.

핵심 계약서 계층:
  MSA  (CO24-133, eff 2024-07-13)  : 기본계약(단가 없음)
  ATP  (CO24-114, eff 2024-06-25)  : 초기 3개월, $297,156.95
  WO v3 (19-Aug-2024)              : 전체 study 예산 - 항목별 단가 확정본
  CO1  (23-Sep-2025)               : 현재 유효(Budget Tracker 기준)

금액 단위: USD
"""

VENDOR = "IQVIA RDS Inc. (CRO)"
CONTRACT_NUMBER = "LAB97701"
PROTOCOL = "TTK-CS-101"
IP = "BAL0891"

# ---- 계약 버전 이력. is_effective=True = 현재 유효 계약 ------------------------
VERSIONS = [
    {"type": "MSA", "doc_no": "CO24-133", "version": "MSA (Master Service Agreement)",
     "effective_date": "2024-07-13", "governing_law": "Singapore",
     "term": "5년 또는 계약업무 종료 시까지",
     "note": "기본 이용약관. 단가는 하위 WO/ATP에서 책정.", "is_effective": False},
    {"type": "ATP", "doc_no": "CO24-114", "version": "ATP (Authorization to Proceed)",
     "effective_date": "2024-06-25", "governing_law": "Singapore",
     "term": "계약일로부터 3개월, 자동연장 없음", "grand_total": 297156.95,
     "note": "AML study 초기 3개월. 총액 선지급 후 reconciliation.", "is_effective": False},
    {"type": "WO", "doc_no": "LAB97701_WOv3_19Aug24", "version": "Work Order v3",
     "effective_date": "2024-08-19", "governing_law": "Singapore",
     "term": "전체 study (61.15 개월, 2024-06-30 ~ 2029-07-29)", "grand_total": 16032808.97,
     "note": "전체 study 예산 확정본. 항목별 단가/Payment Schedule 포함.", "is_effective": False},
    {"type": "CO", "doc_no": None, "version": "CO1_23Sep2025",
     "effective_date": "2025-09-23", "governing_law": "Singapore",
     "term": "Change Order 1 (현재 유효)",
     "note": "현재 유효 계약(Budget Tracker 기준).", "is_effective": True},
]

# ---- WO v3 지급 envelope (연구비 총액 / invoiceable 총액 근거) ----------------
PAYMENT_ENVELOPES = {
    "professional_specialty_max": 6618167.57,   # invoiceable (전문/특수 fee, 할인 후 Direct)
    "investigator_grants_total": 8321417.00,    # 연구비(Investigator Fees) 총액
    "investigator_advance": 1248213.00,
    "passthrough_excl_investigator": 1093224.41,
    "passthrough_advance": 137619.42,
    "grand_total": 16032808.97,
}

# ---- study 가정치 (Scope of Work) --------------------------------------------
STUDY_ASSUMPTIONS = {
    "timeline_months": 61.15, "countries": ["KOR", "USA"],
    "sites_identified": 63, "sites_selected": 13, "sites_activated": 19,
    "patients_screened": 210, "patients_enrolled": 168, "patients_complete": 152,
    "by_country": [
        {"country": "South Korea", "identified": 35, "selected": 7, "active": 11,
         "screened": 130, "enrolled": 104, "completed": 94},
        {"country": "USA", "identified": 28, "selected": 6, "active": 8,
         "screened": 80, "enrolled": 64, "completed": 58},
    ],
}

# ---- 연구비(Investigator Grant) 단가 - 대상자(환자)당 -------------------------
INVESTIGATOR_RATES = [
    {"region": "North America", "unit": "Patient", "qty": 80,
     "cost_per_unit": 43173.90, "total": 3453912.00},
    {"region": "Asia Pacific", "unit": "Patient", "qty": 130,
     "cost_per_unit": 37442.35, "total": 4867505.00},
]

# ---- WO v3 예산 항목표 (Attachment 2). kind: section/sub/item/subtotal/total --
# (name, unit, qty, unit_cost, total, cost_type, kind)
WO_BUDGET = [
    ("Direct Expenses (Core Services)", None, None, None, None, "Direct", "section"),
    ("Project Start-up/Initiation", None, None, None, None, "Direct", "sub"),
    ("Study Setup and Plan Development", "Study", 1, 10208.82, 10208.82, "Direct", "item"),
    ("Project Training", "Training", 1, 122413.94, 122413.94, "Direct", "item"),
    ("IQVIA Translation Services", "Country", 2, 30599.00, 61198.00, "Direct", "item"),
    ("Sub-total: Project Start-up", None, None, None, 193820.76, "Direct", "subtotal"),
    ("Site Start-up Services", None, None, None, None, "Direct", "sub"),
    ("Site Identified", "Site", 11, 6058.86, 66647.42, "Direct", "item"),
    ("Core Document Package - Informed Consent", "ICF(s)", 4, 2237.57, 8950.27, "Direct", "item"),
    ("Core Document Package", "Core Document Package", 19, 754.01, 14326.11, "Direct", "item"),
    ("Core Document Package (Amendments) w/ ICF change", "Master ICF Amendment", 8, 4106.83, 32854.63, "Direct", "item"),
    ("Core Document Package (Notifications)", "Notification", 132, 189.79, 25052.57, "Direct", "item"),
    ("Site Activation", "Site", 19, 7084.02, 134596.44, "Direct", "item"),
    ("Site Contract", "Site", 19, 2923.93, 55554.68, "Direct", "item"),
    ("Site Contract Amendments", "Total Contract Amendment", 27, 1652.25, 44610.84, "Direct", "item"),
    ("Clinical Trial Submission to Central/Local IRBs and EC(s)", "Site", 11, 3406.89, 37475.78, "Direct", "item"),
    ("Substantial Amendment", "Amendment", 2, 65192.26, 130384.51, "Direct", "item"),
    ("Import/Export License", "License", 1, 6521.89, 6521.89, "Direct", "item"),
    ("RA Amendments", "Amendment", 10, 2647.58, 26475.83, "Direct", "item"),
    ("Initial RA Amendment Project Start Up", "Study", 1, 3689.67, 3689.67, "Direct", "item"),
    ("Ethics Committee Amendment", "Amendment", 54, 2206.47, 119149.40, "Direct", "item"),
    ("ICF Site Info Personalization", "Sites", 19, 224.75, 4270.26, "Direct", "item"),
    ("Preparation and QC of CSR Submissions", "Study", 1, 806.70, 806.70, "Direct", "item"),
    ("Sub-total: Site Start-up", None, None, None, 711367.00, "Direct", "subtotal"),
    ("Clinical Site Monitoring and Site Management", None, None, None, None, "Direct", "sub"),
    ("Onsite Transition Visits (South Korea)", "Transition Visit", 5, 2336.79, 11683.96, "Direct", "item"),
    ("Onsite Transition Visits (USA)", "Transition Visit", 2, 4050.16, 8100.32, "Direct", "item"),
    ("Remote Onsite Transition Visits (USA)", "Transition Visit", 1, 2984.33, 2984.33, "Direct", "item"),
    ("Document Review for South Korea Transition", "Site", 5, 353.95, 1769.75, "Direct", "item"),
    ("Document Review for USA Transition", "Site", 3, 632.18, 1896.55, "Direct", "item"),
    ("Site Qualification Visit (SQV)", "Qual Visit", 6, 2325.61, 13953.67, "Direct", "item"),
    ("Site Qualification Visit by Phone", "Qual Call", 7, 438.11, 3066.77, "Direct", "item"),
    ("Site Initiation Visit (SIV)", "SIV Visit", 11, 2619.94, 28819.38, "Direct", "item"),
    ("Interim Site Monitoring Visit (IMV) - One-Day", "IMV Visit", 365, 3052.53, 1114172.51, "Direct", "item"),
    ("Interim Site Monitoring Visit (IMV) - Two-Day", "IMV Visit", 81, 4092.57, 331497.83, "Direct", "item"),
    ("Remote IMV - One-Day", "Remote IMV Visit", 92, 3215.90, 295862.80, "Direct", "item"),
    ("Remote IMV - Two-Day", "Remote IMV Visit", 15, 5030.91, 75463.65, "Direct", "item"),
    ("Essential Document / TMF Maintenance", "Enroll-to-FU Month", 51, 9468.77, 482907.32, "Direct", "item"),
    ("Site Closeout Visit (COV)", "Closeout Visits", 19, 3742.13, 71100.40, "Direct", "item"),
    ("Site Management", "Site Month", 898, 676.95, 607896.88, "Direct", "item"),
    ("Electronic Investigator Site File Software (eISF)", "Site", 19, 2712.45, 51536.53, "Direct", "item"),
    ("CTMS Transfer", "Study", 1, 150000.00, 150000.00, "Direct", "item"),
    ("Data Integration Services", "Study", 1, 18326.38, 18326.38, "Direct", "item"),
    ("Sub-total: Clinical Monitoring & Site Mgmt", None, None, None, 3271039.02, "Direct", "subtotal"),
    ("Project Management and Support", None, None, None, None, "Direct", "sub"),
    ("Project Management (Pre-Study)", "Pre-study Month", 5, 73424.31, 367121.56, "Direct", "item"),
    ("Project Management (Ongoing)", "Enroll/Treatment Month", 27, 53560.49, 1446133.21, "Direct", "item"),
    ("Project Management (Closeout)", "Closeout Month", 5, 15953.26, 79766.31, "Direct", "item"),
    ("Project Management (Long Term Follow-up)", "LTFU/DBL Month", 25, 50463.88, 1261597.02, "Direct", "item"),
    ("DLRT Charter Creation and Review", "Charter", 2, 743.66, 1487.32, "Direct", "item"),
    ("IQVIA DrugDev", "Study", 1, 188748.20, 188748.20, "Direct", "item"),
    ("Vendor Management Office", "Study", 1, 213486.00, 213486.00, "Direct", "item"),
    ("Sub-total: Project Management", None, None, None, 3558339.60, "Direct", "subtotal"),
    ("Meetings", None, None, None, None, "Direct", "sub"),
    ("Meetings - Kick-off Meeting", "Meeting", 1, 13595.13, 13595.13, "Direct", "item"),
    ("Customer Teleconferences", "Meeting", 142, 758.87, 107758.93, "Direct", "item"),
    ("Meetings - Internal Team Meetings", "Meeting*CRA", 1054, 100.73, 106172.93, "Direct", "item"),
    ("DLRM", "Meeting", 17, 1580.93, 26875.73, "Direct", "item"),
    ("Transition/Wrap-up Meetings (KR+USA, 6 lines)", "Meeting", 24, None, 21813.27, "Direct", "item"),
    ("LRSU to CRA handover meeting", "Site", 11, 144.12, 1585.28, "Direct", "item"),
    ("Sub-total: Meetings", None, None, None, 274801.27, "Direct", "subtotal"),
    ("End of Study Activities", None, None, None, None, "Direct", "sub"),
    ("Submission of End of Trial Notifications", "Site", 19, 161.25, 3063.78, "Direct", "item"),
    ("Sub-total: End of Study", None, None, None, 3063.78, "Direct", "subtotal"),
    ("Sub-total Direct Costs (Core CRO Services)", None, None, None, 8012431.43, "Direct", "subtotal"),
    ("Discount (Bottomline)", None, None, None, -741196.04, "Direct", "item"),
    ("One Time Discount for Work Order only", None, None, None, -653067.82, "Direct", "item"),
    ("Sub-total Discounted Direct Costs (Professional/Specialty)", None, None, None, 6618167.57, "Direct", "total"),
    ("Pass-Through Costs (Core Services)", None, None, None, None, "PTC", "section"),
    ("Office Supplies", "Notebook", 19, 1689.21, 32095.00, "PTC", "item"),
    ("Monitoring Travel", "Visit", 465, 585.00, 272025.00, "PTC", "item"),
    ("Regulatory/IRB/EC fees", "Estimated Total", 19, 14516.42, 275811.92, "PTC", "item"),
    ("Document Indexing, QC and File Review", "Document", 7975, 0.08, 598.13, "PTC", "item"),
    ("Printing", "Site", 19, 11.26, 214.00, "PTC", "item"),
    ("Teleconferences", "Teleconference", 264, 21.00, 5544.00, "PTC", "item"),
    ("Miscellaneous Administrative Overhead", "active sites x months", 898, 33.00, 29634.00, "PTC", "item"),
    ("Informed Consent Form", "ICF", 40, 1523.25, 60930.00, "PTC", "item"),
    ("DocuSign", "Study", 1, 35.36, 35.36, "PTC", "item"),
    ("Clario", "Study", 1, 416337.00, 416337.00, "PTC", "item"),
    ("Investigator Grants and Vendor", None, None, None, None, "PTC", "section"),
    ("Investigator Payments (North America)", "Patient", 80, 43173.90, 3453912.00, "PTC", "item"),
    ("Investigator Payments (Asia Pacific)", "Patient", 130, 37442.35, 4867505.00, "PTC", "item"),
    ("Sub-total Pass-through Costs", None, None, None, 9414641.41, "PTC", "total"),
    ("Project Grand Total", None, None, None, 16032808.97, "Total", "total"),
]

# ---- WO v3 지급 스케줄 (Attachment 4). ---------------------------------------
PAYMENT_SCHEDULE = [
    ("Jun-2024", "Pre-Payment Due Upon ATP Execution", 4.09, 270676.37),
    ("Aug-2024", "Pre-Payment Due Upon WO Execution", 10.91, 722048.76),
    ("Oct-2024", "Sign off transition checklist", 10.00, 661816.76),
    ("Dec-2024", "First SIV for additional solid tumor site", 9.00, 595635.08),
    ("Feb-2025", "First IRB submission of AML site", 9.00, 595635.08),
    ("Apr-2025", "First IRB approval of AML site", 7.00, 463271.73),
    ("Jun-2025", "30% of Monitoring Visits & Reports Completed", 7.00, 463271.73),
    ("Aug-2025", "90% of Site Initiation Visits & Reports Completed", 7.00, 463271.73),
    ("Oct-2025", "40% of Monitoring Visits & Reports Completed", 7.00, 463271.73),
    ("Dec-2025", "45% of Monitoring Visits & Reports Completed", 6.00, 397090.05),
    ("Mar-2026", "50% of Monitoring Visits & Reports Completed", 6.00, 397090.05),
    ("May-2026", "60% of Monitoring Visits & Reports Completed", 5.00, 330908.38),
    ("Jul-2026", "65% of Monitoring Visits & Reports Completed", 5.00, 330908.38),
    ("Oct-2026", "70% of Monitoring Visits & Reports Completed", 4.00, 264726.70),
    ("Jan-2027", "80% of Monitoring Visits & Reports Completed", 4.00, 264726.70),
    ("Jun-2027", "85% of Monitoring Visits & Reports Completed", 3.00, 198545.03),
    ("Nov-2027", "90% of Monitoring Visits & Reports Completed", 3.00, 198545.03),
    ("Jun-2028", "95% of Monitoring Visits & Reports Completed", 3.00, 198545.03),
    ("Mar-2029", "Completion of In-treatment follow-up of last patient", 3.00, 198545.03),
    ("May-2029", "100% Site close out", 2.00, 132363.35),
    ("Aug-2029", "Credit of residual Pre-Payment", -15.00, -992725.13),
]

# ---- WO v3 계약 모니터링 visit 횟수 (Attachment 1 Scope) - D/F 대조용 --------
CONTRACTED_VISITS = [
    {"type": "Site Selection Visits (Total)", "count": 13,
     "detail": {"Teleconference": 7, "Onsite": 6}},
    {"type": "Site Initiation Visits (SIV)", "count": 11, "unit_cost": 2619.94},
    {"type": "Interim Monitoring Visits (IMV, Total)", "count": 553,
     "detail": {"1-Day Onsite": 365, "2-Day Onsite": 81, "1-Day Remote": 92, "2-Day Remote": 15}},
    {"type": "Close Out Visits (COV)", "count": 19, "unit_cost": 3742.13},
    {"type": "Total Site Monitoring Visits", "count": 596},
]

# 모니터링 visit 단가 (E 금액 검증 & D 표시용)
MONITORING_UNIT_COSTS = {
    "SIV": 2619.94, "SQV": 2325.61, "SQV_phone": 438.11,
    "IMV_1day": 3052.53, "IMV_2day": 4092.57,
    "IMV_remote_1day": 3215.90, "IMV_remote_2day": 5030.91,
    "COV": 3742.13, "Monitoring_Travel_per_visit": 585.00,
    "Regulatory_IRB_EC_per_site": 14516.42,
}


def build():
    versions = list(VERSIONS)
    effective = next((v for v in versions if v.get("is_effective")), versions[-1])
    budget = [
        {"item": r[0], "unit": r[1], "qty": r[2], "unit_cost": r[3],
         "total": r[4], "cost_type": r[5], "kind": r[6]}
        for r in WO_BUDGET
    ]
    return {
        "vendor": VENDOR, "contract_number": CONTRACT_NUMBER,
        "protocol": PROTOCOL, "ip": IP,
        "effective_version": effective["version"],
        "effective_date": effective["effective_date"],
        "versions": versions,
        "payment_envelopes": PAYMENT_ENVELOPES,
        "study_assumptions": STUDY_ASSUMPTIONS,
        "investigator_rates": INVESTIGATOR_RATES,
        "wo_budget": budget,
        "payment_schedule": [
            {"month": m, "milestone": ms, "pct": p, "amount": a}
            for (m, ms, p, a) in PAYMENT_SCHEDULE
        ],
        "contracted_visits": CONTRACTED_VISITS,
        "monitoring_unit_costs": MONITORING_UNIT_COSTS,
        # 하위 호환: 기존 atp_items 키 유지
        "atp_items": budget,
    }
