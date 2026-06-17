# scratch_test_macro_agent.py
import json
from pathlib import Path
from tools import wiki_utils, financial_metrics
from agents import macro_agent

wiki_utils.reset_wiki()

# 3단계 결과 불러오기
raw_path = Path("raw/삼성전자_2023.json")
if not raw_path.exists():
    raise FileNotFoundError(
        f"'{raw_path}'가 존재하지 않습니다. 먼저 tools.dart_collector를 실행해 주세요."
    )

with open(raw_path, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

metrics = financial_metrics.compute(raw_data)

# 거시 지표는 외부 입력(코드 상수). LLM이 지어내지 않도록 코드가 제공.
macro = {
    "기준금리": "3.50%",
    "원/달러 환율": "약 1,330원",
    "반도체 업황": "메모리 가격 회복 국면",
}

macro_agent.run(metrics, macro, sector="반도체")

print("=== macro.md ===")
print(wiki_utils.read_page("macro"))
