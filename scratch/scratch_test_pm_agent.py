# scratch_test_pm_agent.py
import json
from pathlib import Path
from tools import wiki_utils, financial_metrics, dart_collector
from agents import financial_agent, risk_agent, macro_agent, pm_agent

print("1) 위키 초기화...")
wiki_utils.reset_wiki()

print("2) 삼성전자 DART 데이터 수집...")
raw = dart_collector.collect("삼성전자", 2023)
if not raw.get("success"):
    raise RuntimeError(f"DART 데이터 수집 실패: {raw.get('error')}")

print("3) 재무 지표 계산...")
metrics = financial_metrics.compute(raw)
disclosures = raw.get("disclosures", {}).get("list", [])
macro = {
    "기준금리": "3.50%", 
    "원/달러 환율": "약 1,330원",
    "반도체 업황": "메모리 가격 회복 국면"
}

print("4) Financial 에이전트 실행...")
financial_agent.run(metrics)

print("5) Risk 에이전트 실행...")
risk_agent.run(metrics, disclosures)

print("6) Macro 에이전트 실행...")
macro_agent.run(metrics, macro, sector="반도체")

print("7) PM 에이전트 실행...")
pm_agent.run(metrics)

print("\n=== overview.md (최종 보고서) ===")
print(wiki_utils.read_page("overview"))

print("\n=== log.md (일관성 경고 확인) ===")
print(wiki_utils.read_page("log"))
