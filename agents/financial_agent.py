# agents/financial_agent.py
"""
재무 분석 에이전트.
코드가 계산한 metrics를 받아 LLM으로 해석 글을 생성하고 위키에 기록한다.
숫자/등급/신호는 LLM이 바꿀 수 없도록 코드 게이트로 강제한다.
"""
from pathlib import Path
import config
import llm_client
from tools import wiki_utils


def _load_prompt() -> str:
    return (config.PROMPTS_DIR / "financial_prompt.md").read_text(encoding="utf-8")


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


def run(metrics: dict) -> Path:
    """
    metrics: 3단계 financial_metrics.compute() 결과 dict
    반환: 작성된 financials.md 경로
    """
    prompt_template = _load_prompt()
    schema = _load_schema()
    metrics_block = _format_metrics(metrics)

    prompt = prompt_template.format(schema=schema, metrics_block=metrics_block)

    wiki_utils.log_event("[financial_agent] LLM 해석 생성 시작")
    body = llm_client.generate(prompt)

    # === 코드 게이트: LLM이 등급/신호를 바꿔도 헤더로 사실을 고정 ===
    verified_header = _build_verified_header(metrics)
    final_content = verified_header + "\n\n" + body.strip()

    path = wiki_utils.write_page("financials", final_content, agent_name="financial_agent")
    wiki_utils.log_event("[financial_agent] financials.md 작성 완료")
    return path


def _build_verified_header(metrics: dict) -> str:
    """
    LLM 출력 위에 코드가 확정한 사실을 '검증 블록'으로 박아 넣는다.
    뒤따르는 LLM 해석이 무엇을 말하든, 이 블록이 단일 진실 소스(SSOT)다.
    """
    signals = metrics.get("risk_signals", [])
    return (
        f"# 재무 분석 — {metrics.get('company_name', 'N/A')} "
        f"({metrics.get('year', 'N/A')})\n\n"
        f"> **[코드 확정 사실 — 변경 불가]**\n"
        f"> 등급: {metrics.get('grade', 'N/A')} | "
        f"총점: {metrics.get('total_score', 'N/A')}/12 | "
        f"의견: {metrics.get('opinion', 'N/A')} | "
        f"위험 신호: {', '.join(signals) if signals else '없음'}\n"
        f"> (출처: 재무 에이전트 코드 계산)"
    )
