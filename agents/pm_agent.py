# agents/pm_agent.py
"""
최종 종합 보고서 에이전트 (PM).
위키의 모든 하위 보고서(재무, 매크로, 리스크)를 수집하여 일관성 있는 최종 심사 보고서를 작성하고 wiki/overview.md로 저장한다.
"""
from pathlib import Path
import config
import llm_client
from tools import wiki_utils

def _load_prompt() -> str:
    return (config.PROMPTS_DIR / "pm_prompt.md").read_text(encoding="utf-8")

def _format_verdict(metrics: dict) -> str:
    """코드 확정 지표들을 프롬프트용 텍스트로 변환."""
    signals = metrics.get("risk_signals", [])
    return (
        f"- 기업명: {metrics.get('company_name', 'N/A')}\n"
        f"- 사업연도: {metrics.get('year', 'N/A')}\n"
        f"- 추정 등급: {metrics.get('grade', 'N/A')}\n"
        f"- 종합 의견: {metrics.get('opinion', 'N/A')}\n"
        f"- 총점: {metrics.get('total_score', 'N/A')} / 12점\n"
        f"- 위험 신호: {', '.join(signals) if signals else '없음'}"
    )

def run(metrics: dict) -> Path:
    """
    metrics: 3단계 financial_metrics.compute() 결과 dict
    반환: 작성된 overview.md 경로
    """
    prompt_template = _load_prompt()
    
    verdict_block = _format_verdict(metrics)
    wiki_block = wiki_utils.read_all_pages()
    
    # 프롬프트 바인딩
    prompt = prompt_template.format(
        verdict_block=verdict_block,
        wiki_block=wiki_block
    )
    
    wiki_utils.log_event("[pm_agent] 최종 종합 보고서(overview) 작성 시작")
    body = llm_client.generate(prompt)
    
    # === 코드 게이트: 확정 정보 박기 ===
    verified_header = _build_verified_header(metrics)
    final_content = verified_header + "\n\n" + body.strip()
    
    path = wiki_utils.write_page("overview", final_content, agent_name="pm_agent")
    wiki_utils.log_event("[pm_agent] 최종 종합 보고서(overview.md) 작성 완료")
    return path

def _build_verified_header(metrics: dict) -> str:
    """최종 보고서 상단에 코드 확정 의견을 고정."""
    signals = metrics.get("risk_signals", [])
    return (
        f"# 종합 여신 심사 보고서 — {metrics.get('company_name', 'N/A')} "
        f"({metrics.get('year', 'N/A')})\n\n"
        f"> **[코드 확정 사실 — 변경 불가]**\n"
        f"> 등급: {metrics.get('grade', 'N/A')} | "
        f"총점: {metrics.get('total_score', 'N/A')}/12 | "
        f"의견: {metrics.get('opinion', 'N/A')} | "
        f"위험 신호: {', '.join(signals) if signals else '없음'}\n"
        f"> (출처: 심사 오케스트레이터 최종 검증)"
    )
