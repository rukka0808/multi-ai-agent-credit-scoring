# orchestrator.py
"""
결정론적 오케스트레이터.
에이전트 호출 순서와 실패 게이트를 코드로 고정한다.
LLM은 라우팅에 관여하지 않는다(신뢰도/비용 보호).
"""
import config
from tools import wiki_utils, financial_metrics, dart_collector
from agents import financial_agent, risk_agent, macro_agent, pm_agent


def run_pipeline(company_name: str, year: int, sector: str = "", macro: dict | None = None) -> dict:
    """
    전체 여신 심사 파이프라인을 실행한다.
    반환: {'success': bool, 'report_path': Path|None, 'reason': str}
    """
    macro = macro or {}
    wiki_utils.reset_wiki()
    wiki_utils.log_event(f"[orchestrator] 파이프라인 시작: {company_name} ({year})")

    # === 1. 데이터 수집 (결정론적) ===
    try:
        raw = dart_collector.collect(company_name, year)
    except Exception as e:
        wiki_utils.log_event(f"[orchestrator] DART 수집 실패: {e}")
        return {"success": False, "report_path": None,
                "reason": f"DART 데이터 수집 실패: {e}"}

    disclosures = raw.get("disclosures", [])

    # === 2. 정량 지표 계산 (결정론적, LLM 없음) ===
    try:
        metrics = financial_metrics.compute(raw)
    except Exception as e:
        wiki_utils.log_event(f"[orchestrator] 지표 계산 실패: {e}")
        return {"success": False, "report_path": None,
                "reason": f"재무 지표 계산 실패: {e}"}


    # === 3. 데이터 게이트 (IF-ELSE): 핵심 지표 없으면 LLM 미호출 ===
    if metrics.get("grade") in (None, "", "N/A"):
        wiki_utils.log_event("[orchestrator] 핵심 지표 부족 — LLM 단계 생략")
        return {"success": False, "report_path": None,
                "reason": "핵심 재무 지표 부족으로 분석 중단 (LLM 미호출)"}

    # === 4. 분석 에이전트 호출 (순차, 각자 위키에 기고) ===
    financial_agent.run(metrics)
    risk_agent.run(metrics, disclosures)
    macro_agent.run(metrics, macro, sector=sector)

    # === 5. PM 종합 + 일관성 게이트 ===
    report_path = pm_agent.run(metrics)

    wiki_utils.log_event("[orchestrator] 파이프라인 완료")
    return {"success": True, "report_path": report_path,
            "reason": "정상 완료", "metrics": metrics}
