# scratch_test_wiki.py (임시 테스트용, 나중에 삭제)
from tools import wiki_utils

wiki_utils.reset_wiki()

sample = """# 재무 분석 — 삼성전자 (2023)

## 결론
- 추정 등급: A (승인 권고) (출처: 재무 에이전트 계산)
- 총점: 8 / 12점

## 세부 지표
- 이자보상배율(ICR): 7.77배 (3점)
- 부채비율: 25.4% (2점)
- 3개년 수익성: 전부 흑자 (2점)
- 매출성장률: -14.3% (-1점)
- 유동비율: 258.8% (1점)
- 차입금의존도: 2.8% (1점)
- EBITDA: 데이터 없음(N/A) — 감가상각비 미수집

## 위험 신호
- RED/YELLOW 신호 없음 (출처: 재무 에이전트 계산)
"""

wiki_utils.write_page("financials", sample, agent_name="financial_agent")

print("=== index.md ===")
print(wiki_utils.read_page("index"))
print("=== log.md ===")
print(wiki_utils.read_page("log"))
print("=== read_all_pages() ===")
print(wiki_utils.read_all_pages())
