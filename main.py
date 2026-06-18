# main.py
"""
여신 심사 멀티에이전트 시스템 진입점.
사용법: 
  - 대화형 실행: python main.py
  - CLI 인자 실행: python main.py --company 현대차 --year 2023 --sector 자동차
"""
import sys
import argparse
import config
from orchestrator import run_pipeline
from tools import wiki_utils, pdf_export, macro_collector


def get_user_input() -> dict:
    """사용자로부터 분석 대상 정보를 입력받는다."""
    company_name = input("분석할 회사명을 입력하세요: ").strip()
    if not company_name:
        raise ValueError("회사명은 필수입니다.")

    year_str = input("사업연도를 입력하세요 (기본 2023): ").strip()
    year = int(year_str) if year_str else 2023

    sector = input("업종을 입력하세요 (비우면 미지정): ").strip()

    return {"company_name": company_name, "year": year, "sector": sector}


def main():
    config.validate()

    # 인자가 주어지면 argparse 사용, 없으면 get_user_input 대화형 사용
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="여신 심사 멀티에이전트 시스템")
        parser.add_argument("--company", required=True, help="분석 대상 기업명")
        parser.add_argument("--year", type=int, required=True, help="분석 대상 사업연도")
        parser.add_argument("--sector", default="", help="기업 업종")
        args = parser.parse_args()
        
        company_name = args.company
        year = args.year
        sector = args.sector
    else:
        params = get_user_input()
        company_name = params["company_name"]
        year = params["year"]
        sector = params["sector"]

    # 업종 기반 매크로 정보 분기 설정(삼성전자 테스트)
    macro = macro_collector.collect_macro(base_rate="3.50%")
    if not sector:
        sector = "일반"

    print(f"\n=== 여신 심사 시작: {company_name} ({year}) ===")
    print(f"  - 업종: {sector}")
    print(f"  - 거시 지표: {macro}")

    result = run_pipeline(
        company_name,
        year,
        sector=sector,
        macro=macro,
    )

    if not result["success"]:
        print(f"[중단] {result['reason']}")
        return

    report_md = wiki_utils.read_page("overview")
    pdf_path = pdf_export.export(report_md, company_name, year)
    print(f"[완료] 최종 보고서: {pdf_path}")
    print(f"[완료] 총 LLM 호출 수: {getattr(__import__('llm_client'), 'call_count', 'N/A')}")


if __name__ == "__main__":
    main()
