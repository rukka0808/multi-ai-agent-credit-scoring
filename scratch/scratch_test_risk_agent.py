# scratch_test_risk_agent.py
from tools import wiki_utils, financial_metrics, dart_collector
from agents import financial_agent, risk_agent

print("1) 위키 초기화...")
wiki_utils.reset_wiki()

print("2) 삼성전자 DART 데이터 수집...")
raw = dart_collector.collect("삼성전자", 2023)
if not raw.get("success"):
    raise RuntimeError(f"DART 데이터 수집 실패: {raw.get('error')}")

print("3) 재무 지표 계산...")
metrics = financial_metrics.compute(raw)
disclosures = raw.get("disclosures", {}).get("list", [])

print("4) Financial 에이전트 실행 및 financials.md 기록...")
financial_agent.run(metrics)

print("5) Risk 에이전트 실행 및 risk.md 기록...")
risk_agent.run(metrics, disclosures)

print("\n=== index.md ===")
print(wiki_utils.read_page("index"))

print("\n=== risk.md ===")
print(wiki_utils.read_page("risk"))
