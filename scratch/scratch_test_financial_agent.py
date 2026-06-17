import json
from pathlib import Path
from tools import wiki_utils, financial_metrics
from agents import financial_agent

wiki_utils.reset_wiki()

# 3단계 결과 불러오기 (DART 수집 원본 로드 후 계산)
raw_path = Path("raw/삼성전자_2023.json")
if not raw_path.exists():
    raise FileNotFoundError(
        f"'{raw_path}'가 존재하지 않습니다. 먼저 tools.dart_collector를 실행해 주세요."
    )

with open(raw_path, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# Compute metrics
metrics = financial_metrics.compute(raw_data)

# Run agent to write financials.md using Gemini LLM
financial_agent.run(metrics)

print("=== financials.md ===")
print(wiki_utils.read_page("financials"))
