"""심사지표 계산 모듈. account_id 우선 매칭, 없으면 한글명 폴백.
원문의 12점 룰베이스 + RED/YELLOW 신호를 그대로 구현.
추정하지 않는다 — 구할 수 없는 지표는 None 처리(환각 방지).
단, 차입금은 '계정 없음 = 무차입(0)'으로 간주한다.
"""

# ── 단일 계정 매칭 테이블: account_id 우선, 보조로 한글명(완전일치) ──
ACCOUNT_MAP = {
    "매출액":     {"id": ["ifrs-full_Revenue"], "nm": ["매출액", "영업수익", "수익(매출액)"]},
    "영업이익":   {"id": ["dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"],
                  "nm": ["영업이익", "영업이익(손실)"]},
    "당기순이익": {"id": ["ifrs-full_ProfitLoss"], "nm": ["당기순이익", "당기순이익(손실)"]},
    "자산총계":   {"id": ["ifrs-full_Assets"], "nm": ["자산총계"]},
    "부채총계":   {"id": ["ifrs-full_Liabilities"], "nm": ["부채총계"]},
    "자본총계":   {"id": ["ifrs-full_Equity"], "nm": ["자본총계"]},
    "유동자산":   {"id": ["ifrs-full_CurrentAssets"], "nm": ["유동자산"]},
    "유동부채":   {"id": ["ifrs-full_CurrentLiabilities"], "nm": ["유동부채"]},
    # 이자비용 (함정1): 영업/재무 활동 이자지급 모두 후보 → 없으면 금융비용/금융원가 폴백
    "이자의지급": {"id": ["ifrs-full_InterestPaidClassifiedAsOperatingActivities",
                       "ifrs-full_InterestPaidClassifiedAsFinancingActivities"],
                  "nm": ["이자지급", "이자의 지급", "이자의지급"]},
    "금융비용":   {"id": ["ifrs-full_FinanceCosts"], "nm": ["금융비용", "금융원가"]},
}

# ── 차입금(함정3): id 또는 한글명 부분일치로 모두 합산 ──
BORROWING_ID = [
    "ifrs-full_ShorttermBorrowings",
    "ifrs-full_CurrentPortionOfLongtermBorrowings",
    "ifrs-full_LongtermBorrowings",
    "ifrs-full_NoncurrentPortionOfNoncurrentLoansReceived",
    "ifrs-full_NoncurrentPortionOfNoncurrentBondsIssued",
    "dart_ShortTermBorrowings",
    "dart_LongTermBorrowings",
]
BORROWING_NM_KEYWORDS = ["차입금", "사채", "유동성장기부채"]
# 차입금이 아닌데 키워드에 걸릴 수 있는 계정 제외
BORROWING_NM_EXCLUDE = ["대여금", "수취채권", "매입채무", "증가", "상환", "감소"]


def _to_num(s):
    """문자열 금액 → int. 빈 값/콤마/하이픈 처리. 못 바꾸면 None."""
    if s is None or str(s).strip() in ("", "-"):
        return None
    try:
        return int(str(s).replace(",", ""))
    except ValueError:
        return None


def _find(accounts, key, period="thstrm_amount"):
    """ACCOUNT_MAP 기준 단일 계정 금액 반환. 못 찾으면 None.
    account_id 완전일치 우선, 없으면 한글명 완전일치."""
    spec = ACCOUNT_MAP[key]
    # 1) account_id 우선
    for acc in accounts:
        if acc.get("account_id") in spec["id"]:
            val = _to_num(acc.get(period))
            if val is not None:
                return val
    # 2) 한글명 완전일치 폴백
    for acc in accounts:
        nm = (acc.get("account_nm") or "").strip()
        if nm in spec["nm"]:
            val = _to_num(acc.get(period))
            if val is not None:
                return val
    return None


def _sum_borrowings(accounts, period="thstrm_amount"):
    """차입금 성격 계정을 id 또는 한글명 부분일치로 모두 합산.
    재무상태표(BS) 계정만 대상으로 하며, 계정이 하나도 없으면 0(무차입)."""
    total = 0
    seen = set()  # (account_id, account_nm) 기준 중복 합산 방지
    for acc in accounts:
        if acc.get("sj_div") != "BS":   # 차입금 잔액은 재무상태표에만
            continue
        aid = acc.get("account_id") or ""
        nm = (acc.get("account_nm") or "").strip()
        key = (aid, nm)
        if key in seen:
            continue
        hit_id = aid in BORROWING_ID
        hit_nm = (any(k in nm for k in BORROWING_NM_KEYWORDS)
                  and not any(x in nm for x in BORROWING_NM_EXCLUDE))
        if hit_id or hit_nm:
            val = _to_num(acc.get(period))
            if val is not None:
                total += val
                seen.add(key)
    return total  # 무차입이면 0


def _safe_div(a, b):
    """0 나누기/None 방어. 못 구하면 None."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def _fmt(v, suffix=""):
    """표시용 포맷. None이면 N/A, 아니면 반올림 + 단위."""
    return f"{round(v, 2)}{suffix}" if v is not None else "N/A"


def compute(raw: dict) -> dict:
    """수집 결과(raw)를 받아 심사지표 전체를 계산."""
    # ── 데이터 부재 방어: financials/list 없으면 등급 None 반환 ──
    financials = raw.get("financials")
    if not financials or not financials.get("list"):
        return {
            "company_name": raw.get("company", {}).get("corp_name", "N/A"),
            "year": str(raw.get("year", "N/A")),
            "grade": None,
            "opinion": "데이터 부족",
            "score": None,
            "total_score": None,
            "score_breakdown": {},
            "details": [],
            "risk_signals": [],
            "metrics": {},
            "raw_values": {},
            "signals": [],
            "reason": "DART에 해당 기업/연도의 재무제표가 없습니다.",
        }

    accounts = financials["list"]

    def g(key, period="thstrm_amount"):
        return _find(accounts, key, period)

    # ── 원시 계정값 추출 (3개년) ──
    영업이익 = g("영업이익")
    매출_당기 = g("매출액", "thstrm_amount")
    매출_전기 = g("매출액", "frmtrm_amount")
    당기순이익_당기 = g("당기순이익", "thstrm_amount")
    당기순이익_전기 = g("당기순이익", "frmtrm_amount")
    당기순이익_전전 = g("당기순이익", "bfefrmtrm_amount")
    자산총계 = g("자산총계")
    부채총계 = g("부채총계")
    자본총계 = g("자본총계")
    유동자산 = g("유동자산")
    유동부채 = g("유동부채")

    # ── 이자비용 (함정1): 이자지급 우선, 없거나 0이면 금융비용 폴백 ──
    이자비용 = g("이자의지급")
    이자비용_출처 = "이자지급(현금흐름표)"
    if 이자비용 is None or 이자비용 == 0:
        이자비용 = g("금융비용")
        이자비용_출처 = "금융비용/금융원가(이자비용 근사)"

    # ── 총차입금 (함정3): 부분일치 합산, 무차입이면 0 ──
    총차입금 = _sum_borrowings(accounts)

    # ── 핵심 비율 (is not None으로 0%·음수 보존) ──
    ICR = _safe_div(영업이익, 이자비용)
    부채비율_pct = (_safe_div(부채총계, 자본총계) * 100
                  if 부채총계 is not None and 자본총계 not in (None, 0) else None)
    유동비율_pct = (_safe_div(유동자산, 유동부채) * 100
                  if 유동자산 is not None and 유동부채 not in (None, 0) else None)
    차입금의존도_pct = (_safe_div(총차입금, 자산총계) * 100
                     if 자산총계 not in (None, 0) else None)  # 총차입금 0이면 0% 정상
    매출성장률_pct = (_safe_div(매출_당기 - 매출_전기, abs(매출_전기)) * 100
                   if 매출_당기 is not None and 매출_전기 not in (None, 0) else None)

    # EBITDA (함정2): 감가상각비를 fnlttSinglAcntAll에서 못 구함 → 추정 안 함
    EBITDA = None

    # ── 3개년 수익성 ──
    순이익_3년 = [당기순이익_당기, 당기순이익_전기, 당기순이익_전전]
    적자년수 = sum(1 for v in 순이익_3년 if v is not None and v < 0)
    전부흑자 = all(v is not None and v > 0 for v in 순이익_3년)
    흑자년수 = sum(1 for v in 순이익_3년 if v is not None and v > 0)

    # ── 12점 룰베이스 점수 (원문 표 그대로) ──
    score = 0
    breakdown = {}

    # ICR (가중치 3)
    if ICR is None:        s = 0
    elif ICR >= 3:         s = 3
    elif ICR >= 2:         s = 2
    elif ICR >= 1.5:       s = 1
    elif ICR >= 1:         s = 0
    else:                  s = -3
    breakdown["ICR"] = s; score += s

    # 부채비율 (가중치 2)
    if 부채비율_pct is None:    s = 0
    elif 부채비율_pct <= 100:   s = 2
    elif 부채비율_pct <= 200:   s = 1
    elif 부채비율_pct <= 300:   s = 0
    elif 부채비율_pct <= 500:   s = -1
    else:                       s = -3
    breakdown["부채비율"] = s; score += s

    # 3개년 수익성 (가중치 2)
    if 전부흑자:                                       s = 2
    elif 흑자년수 >= 2:                                s = 1
    elif 당기순이익_당기 is not None and 당기순이익_당기 > 0: s = 0
    elif 적자년수 >= 1:                                s = -2
    else:                                              s = 0
    breakdown["수익성3년"] = s; score += s

    # 매출성장률 (가중치 2)
    if 매출성장률_pct is None:   s = 0
    elif 매출성장률_pct > 10:    s = 2
    elif 매출성장률_pct > 0:     s = 1
    elif 매출성장률_pct > -10:   s = 0
    else:                        s = -1
    breakdown["매출성장률"] = s; score += s

    # 유동비율 (가중치 1)
    if 유동비율_pct is None:     s = 0
    elif 유동비율_pct >= 150:    s = 1
    elif 유동비율_pct >= 100:    s = 0
    else:                        s = -1
    breakdown["유동비율"] = s; score += s

    # 차입금의존도 (가중치 1)
    if 차입금의존도_pct is None:  s = 0
    elif 차입금의존도_pct <= 30:  s = 1
    elif 차입금의존도_pct <= 50:  s = 0
    else:                         s = -1
    breakdown["차입금의존도"] = s; score += s

    # ── 등급 판정 ──
    if   score >= 8:   grade, opinion = "A", "승인 권고"
    elif score >= 5:   grade, opinion = "B", "승인 권고"
    elif score >= 2:   grade, opinion = "C", "조건부 승인 검토"
    elif score >= -1:  grade, opinion = "D", "추가 담보·보증 필요"
    else:              grade, opinion = "E", "여신 거절 권고"

    # ── RED / YELLOW 신호 (is not None으로 0%·음수 보존) ──
    signals = []
    # 영업적자(음수 ICR)는 '1배 미만'보다 심각하므로 별도 표기
    if ICR is not None and ICR < 0:
        signals.append(("RED", "영업적자(이자보상배율 음수)"))
    elif ICR is not None and ICR < 1:
        signals.append(("RED", "이자보상배율 1배 미만"))
    if 부채비율_pct is not None and 부채비율_pct > 500:
        signals.append(("RED", "부채비율 500% 초과"))
    if 적자년수 >= 3:
        signals.append(("RED", "3개년 연속 적자"))
    if 매출성장률_pct is not None and 매출성장률_pct <= -20:
        signals.append(("RED", "매출 20% 이상 급감"))

    if ICR is not None and 1 <= ICR < 1.5:
        signals.append(("YELLOW", "이자보상배율 1.5배 미만"))
    if 부채비율_pct is not None and 300 < 부채비율_pct <= 500:
        signals.append(("YELLOW", "부채비율 300% 초과"))
    if 적자년수 == 2:
        signals.append(("YELLOW", "2개년 연속 적자"))
    if 차입금의존도_pct is not None and 차입금의존도_pct > 50:
        signals.append(("YELLOW", "차입금의존도 50% 초과"))
    if 유동비율_pct is not None and 유동비율_pct < 100:
        signals.append(("YELLOW", "유동비율 100% 미만"))

    # ── 에이전트(financial_agent) 소비용 details ──
    details = [
        {"name": "이자보상배율(ICR)", "value": _fmt(ICR, "배"),
         "score": breakdown.get("ICR"), "weight": 3},
        {"name": "부채비율", "value": _fmt(부채비율_pct, "%"),
         "score": breakdown.get("부채비율"), "weight": 2},
        {"name": "3개년 수익성", "value": f"적자년수 {적자년수}년",
         "score": breakdown.get("수익성3년"), "weight": 2},
        {"name": "매출성장률", "value": _fmt(매출성장률_pct, "%"),
         "score": breakdown.get("매출성장률"), "weight": 2},
        {"name": "유동비율", "value": _fmt(유동비율_pct, "%"),
         "score": breakdown.get("유동비율"), "weight": 1},
        {"name": "차입금의존도", "value": _fmt(차입금의존도_pct, "%"),
         "score": breakdown.get("차입금의존도"), "weight": 1},
    ]
    risk_signals = [sig[1] for sig in signals]

    return {
        "company_name": raw.get("company", {}).get("corp_name", "N/A"),
        "year": str(raw.get("year", "N/A")),
        "grade": grade,
        "opinion": opinion,
        "score": score,
        "total_score": score,
        "score_breakdown": breakdown,
        "details": details,
        "risk_signals": risk_signals,
        "metrics": {
            "ICR": round(ICR, 2) if ICR is not None else None,
            "이자비용_출처": 이자비용_출처,
            "이자비용": 이자비용,
            "부채비율_pct": round(부채비율_pct, 1) if 부채비율_pct is not None else None,
            "유동비율_pct": round(유동비율_pct, 1) if 유동비율_pct is not None else None,
            "차입금의존도_pct": round(차입금의존도_pct, 1) if 차입금의존도_pct is not None else None,
            "매출성장률_pct": round(매출성장률_pct, 1) if 매출성장률_pct is not None else None,
            "EBITDA": EBITDA,  # None = 데이터 부족으로 미산출
            "총차입금": 총차입금,
            "영업이익": 영업이익,
            "매출액": 매출_당기,
            "당기순이익": 당기순이익_당기,
        },
        "raw_values": {
            "적자년수": 적자년수, "전부흑자": 전부흑자, "흑자년수": 흑자년수,
        },
        "signals": signals,
    }


if __name__ == "__main__":
    import json
    from pathlib import Path

    for fname in ["삼성전자_2023.json", "리노공업_2023.json", "광진실업_2024.json"]:
        path = Path("raw") / fname
        if not path.exists():
            print(f"[건너뜀] {fname} 없음")
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        r = compute(raw)
        print(f"\n===== {r['company_name']} ({r['year']}) =====")
        print(f"등급: {r['grade']} | 총점: {r['total_score']} | 의견: {r['opinion']}")
        print(f"이자비용 출처: {r['metrics'].get('이자비용_출처')}")
        print(f"ICR: {r['metrics'].get('ICR')} | "
              f"차입금의존도: {r['metrics'].get('차입금의존도_pct')}% | "
              f"총차입금: {r['metrics'].get('총차입금'):,}")
        print(f"위험 신호: {r['risk_signals'] or '없음'}")
