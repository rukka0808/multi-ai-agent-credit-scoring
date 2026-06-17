# agents/macro_agent.py
"""
거시 및 산업 환경 분석 에이전트.
주어진 거시 지표와 기업 재무 상태를 바탕으로 외부 환경이 미치는 영향을 서술한다.
"""
from pathlib import Path
import config
import llm_client
from tools import wiki_utils

def _load_prompt() -> str:
    return (config.PROMPTS_DIR / "macro_prompt.md").read_text(encoding="utf-8")

def _load_schema() -> str:
    return (config.PROMPTS_DIR / "schema.md").read_text(encoding="utf-8")

def run(metrics: dict, macro: dict, sector: str = "N/A") -> Path:
    """
    metrics: 3단계 financial_metrics.compute() 결과 dict
    macro: 거시 경제 지표 dict (예: {"기준금리": "3.50%", ...})
    sector: 대상 기업 업종/섹터 (예: "반도체")
    반환: 작성된 macro.md 경로
    """
    prompt_template = _load_prompt()
    schema = _load_schema()
    
    company_block = (
        f"- 기업명: {metrics.get('company_name', 'N/A')}\n"
        f"- 사업연도: {metrics.get('year', 'N/A')}\n"
        f"- 추정 등급: {metrics.get('grade', 'N/A')}\n"
        f"- 총점: {metrics.get('total_score', 'N/A')} / 12점\n"
        f"- 업종: {sector}"
    )
    
    macro_lines = []
    for k, v in macro.items():
        macro_lines.append(f"- {k}: {v}")
    macro_block = "\n".join(macro_lines) if macro_lines else "- 거시 지표 없음"
    
    # 프롬프트 바인딩
    prompt = prompt_template.format(
        schema=schema,
        company_block=company_block,
        macro_block=macro_block
    )
    
    wiki_utils.log_event("[macro_agent] 거시 및 산업 분석 시작")
    body = llm_client.generate(prompt)
    
    # === 코드 게이트: 확정 지표 박기 ===
    verified_header = _build_verified_header(metrics, macro, sector)
    final_content = verified_header + "\n\n" + body.strip()
    
    path = wiki_utils.write_page("macro", final_content, agent_name="macro_agent")
    wiki_utils.log_event("[macro_agent] macro.md 작성 완료")
    return path

def _build_verified_header(metrics: dict, macro: dict, sector: str) -> str:
    """거시 분석 코드 확정 사실 고정."""
    macro_details = " | ".join(f"{k}: {v}" for k, v in macro.items())
    return (
        f"# 거시·산업 분석 — {metrics.get('company_name', 'N/A')} "
        f"({metrics.get('year', 'N/A')})\n\n"
        f"> **[참고 — 거시 수치는 외부 입력값이며 모델 추정이 아님]**\n"
        f"> 업종: 회사명 기반 추론 (본문 '업종 판단' 참조)\n"
        f"> (출처: 코드/사용자 제공 거시 지표)"
    )

def _format_company(metrics: dict, sector: str) -> str:
    if sector:
        sector_line = f"- 업종(참고): {sector}"
    else:
        sector_line = "- 업종: 미지정 (회사명으로부터 판단할 것)"
    return (
        f"- 기업명: {metrics.get('company_name', 'N/A')}\n"
        f"{sector_line}\n"
        f"- 재무 등급(참고): {metrics.get('grade', 'N/A')}"
    )