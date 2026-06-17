# agents/risk_agent.py
"""
리스크 및 이상공시 분석 에이전트.
공시 목록과 재무 지표를 받아 위험 요인을 식별하고 위키를 lint(교차 검증)한다.
"""
from pathlib import Path
import config
import llm_client
from tools import wiki_utils

def _load_prompt() -> str:
    return (config.PROMPTS_DIR / "risk_prompt.md").read_text(encoding="utf-8")

def _load_schema() -> str:
    return (config.PROMPTS_DIR / "schema.md").read_text(encoding="utf-8")

def _format_metrics(metrics: dict) -> str:
    """3단계 financial_metrics 결과 dict를 프롬프트용 텍스트로 변환."""
    lines = [
        f"- 기업명: {metrics.get('company_name', 'N/A')}",
        f"- 사업연도: {metrics.get('year', 'N/A')}",
        f"- 추정 등급: {metrics.get('grade', 'N/A')}",
        f"- 종합 의견: {metrics.get('opinion', 'N/A')}",
        f"- 총점: {metrics.get('total_score', 'N/A')} / 12점",
        "",
        "세부 지표:",
    ]
    for item in metrics.get("details", []):
        lines.append(
            f"  - {item['name']}: {item['value']} "
            f"({item['score']}점 / 가중치 {item['weight']})"
        )
    signals = metrics.get("risk_signals", [])
    lines.append("")
    lines.append(f"위험 신호: {', '.join(signals) if signals else '없음'}")
    return "\n".join(lines)

def _format_disclosures(disclosures) -> str:
    """공시 목록 리스트를 프롬프트용 텍스트로 변환."""
    if isinstance(disclosures, dict):
        disclosures_list = disclosures.get("list", [])
    elif isinstance(disclosures, list):
        disclosures_list = disclosures
    else:
        disclosures_list = []

    lines = []
    # 최신 20건만 반영하여 프롬프트 컨텍스트 제한 방어
    for item in disclosures_list[:20]:
        date = item.get("rcept_dt", "N/A")
        name = item.get("report_nm", "N/A")
        flr = item.get("flr_nm", "N/A")
        lines.append(f"  - [{date}] {name} (공시제출인: {flr})")
    return "\n".join(lines) if lines else "  - 최근 공시 목록 없음"


def run(metrics: dict, disclosures: list) -> Path:
    """
    metrics: 3단계 financial_metrics.compute() 결과 dict
    disclosures: 수집된 공시 목록 list (raw.get("disclosures", {}).get("list", []))
    반환: 작성된 risk.md 경로
    """
    prompt_template = _load_prompt()
    schema = _load_schema()
    
    metrics_block = _format_metrics(metrics)
    disclosures_block = _format_disclosures(disclosures)
    
    # 프롬프트 바인딩
    prompt = prompt_template.format(
        schema=schema,
        metrics_block=metrics_block,
        disclosures_block=disclosures_block
    )
    
    wiki_utils.log_event("[risk_agent] 리스크 분석 및 위키 검증(Lint) 시작")
    body = llm_client.generate(prompt)
    
    # === 코드 게이트: 확정 정보 박기 ===
    verified_header = _build_verified_header(metrics)
    final_content = verified_header + "\n\n" + body.strip()
    
    path = wiki_utils.write_page("risk", final_content, agent_name="risk_agent")
    wiki_utils.log_event("[risk_agent] risk.md 작성 완료")
    return path

def _build_verified_header(metrics: dict) -> str:
    """코드 확정 사실을 상단에 고정."""
    signals = metrics.get("risk_signals", [])
    return (
        f"# 리스크 및 이상공시 분석 — {metrics.get('company_name', 'N/A')} "
        f"({metrics.get('year', 'N/A')})\n\n"
        f"> **[코드 확정 사실 — 변경 불가]**\n"
        f"> 등급: {metrics.get('grade', 'N/A')} | "
        f"총점: {metrics.get('total_score', 'N/A')}/12 | "
        f"의견: {metrics.get('opinion', 'N/A')} | "
        f"위험 신호: {', '.join(signals) if signals else '없음'}\n"
        f"> (출처: 리스크 에이전트 코드 검증)"
    )
