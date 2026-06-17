"""DART 데이터 수집 모듈.
원문 Dify 워크플로의 urllib 로직을 이식하되:
  - SSL 검증은 켠다 (원문의 ssl.CERT_NONE 제거 — 일반 환경에서는 불필요/위험)
  - API 키는 config에서 가져온다 (하드코딩 금지)
완전일치→부분일치, 11011→11012, CFS→OFS 폴백 체인 유지.
"""
import io
import json
import zipfile
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import config

DART_BASE = "https://opendart.fss.or.kr/api"

# 보고서 코드 폴백: 사업보고서 → 반기보고서
REPRT_CODES = ["11011", "11012"]
# 재무제표 구분 폴백: 연결 → 별도
FS_DIVS = ["CFS", "OFS"]

# corpCode.xml은 매번 받으면 느리니 캐싱
_CORP_CODE_CACHE = config.BASE_DIR / "raw" / "_corpcode_cache.xml"


def _http_get(url: str, params: dict = None) -> bytes:
    """SSL 검증을 켠 상태로 GET. 바이트를 그대로 반환."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "dart-advisor/1.0"})
    # ssl 컨텍스트를 따로 안 넘기면 기본(검증 켜짐) 사용 — 원문과 다른 핵심 지점
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# ──────────────────────────────────────────────
# 1) 기업명 → corp_code
# ──────────────────────────────────────────────
def _load_corp_code_xml() -> bytes:
    """corpCode.xml(ZIP) 다운로드 후 압축 해제. 캐시 있으면 재사용."""
    if _CORP_CODE_CACHE.exists():
        return _CORP_CODE_CACHE.read_bytes()

    zip_bytes = _http_get(
        f"{DART_BASE}/corpCode.xml",
        {"crtfc_key": config.DART_API_KEY},
    )
    # 응답이 ZIP이 아니면 보통 키 에러 JSON임 → 확인
    if not zip_bytes[:2] == b"PK":
        raise RuntimeError(
            f"corpCode 응답이 ZIP이 아닙니다. 키/한도 확인 필요: "
            f"{zip_bytes[:200].decode('utf-8', 'ignore')}"
        )
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        xml_bytes = zf.read("CORPCODE.xml")
    _CORP_CODE_CACHE.write_bytes(xml_bytes)
    return xml_bytes


def find_corp_code(company_name: str) -> dict:
    """기업명으로 corp_code 조회. 완전일치 우선, 없으면 부분일치 첫 상장사."""
    xml_bytes = _load_corp_code_xml()
    root = ET.fromstring(xml_bytes)

    exact, partial = [], []
    for item in root.iter("list"):
        name = (item.findtext("corp_name") or "").strip()
        code = (item.findtext("corp_code") or "").strip()
        stock = (item.findtext("stock_code") or "").strip()
        if not code:
            continue
        entry = {"corp_name": name, "corp_code": code, "stock_code": stock}
        if name == company_name:
            exact.append(entry)
        elif company_name in name:
            partial.append(entry)

    # 완전일치 중 상장사(stock_code 있음) 우선
    for pool in (exact, partial):
        listed = [e for e in pool if e["stock_code"]]
        if listed:
            return listed[0]
        if pool:
            return pool[0]
    return None


# ──────────────────────────────────────────────
# 2) 재무제표 3개년 (폴백 체인)
# ──────────────────────────────────────────────
def fetch_financials(corp_code: str, year: int) -> dict:
    """fnlttSinglAcntAll 호출. reprt_code/fs_div 폴백을 순서대로 시도."""
    for reprt in REPRT_CODES:
        for fs in FS_DIVS:
            params = {
                "crtfc_key": config.DART_API_KEY,
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": reprt,
                "fs_div": fs,
            }
            raw = _http_get(f"{DART_BASE}/fnlttSinglAcntAll.json", params)
            data = json.loads(raw)
            if data.get("status") == "000" and data.get("list"):
                data["_meta"] = {"reprt_code": reprt, "fs_div": fs}
                return data
            # status 013 = 데이터 없음 → 다음 폴백 시도
    return None


# ──────────────────────────────────────────────
# 3) 최근 공시목록 (이상공시 탐지용)
# ──────────────────────────────────────────────
def fetch_disclosures(corp_code: str, year: int) -> dict:
    """최근 3개년 공시목록."""
    params = {
        "crtfc_key": config.DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": f"{year - 2}0101",
        "end_de": f"{year}1231",
        "page_count": "100",
    }
    raw = _http_get(f"{DART_BASE}/list.json", params)
    return json.loads(raw)

def fetch_company_profile(corp_code: str) -> dict:
    """기업개황 API로 업종명 등 기본 정보를 가져온다."""
    url = (
        "https://opendart.fss.or.kr/api/company.json"
        f"?crtfc_key={config.DART_API_KEY}&corp_code={corp_code}"
    )
    data = _http_get_json(url)  # 기존 GET 헬퍼 재사용
    if data.get("status") != "000":
        return {}
    return {
        "corp_name": data.get("corp_name"),
        "induty_code": data.get("induty_code"),  # 업종 코드
        "sector": data.get("induty_code"),        # 코드뿐이라 매핑 필요할 수 있음
        "ceo_nm": data.get("ceo_nm"),
        "est_dt": data.get("est_dt"),
    }


# ──────────────────────────────────────────────
# 통합 진입점
# ──────────────────────────────────────────────
def collect(company_name: str, year: int) -> dict:
    """오케스트레이터가 부르는 함수.
    성공 시 {success: True, ...}, 실패 시 {success: False, error: ...}."""
    try:
        corp = find_corp_code(company_name)
    except Exception as e:
        return {"success": False, "error": f"기업코드 조회 실패: {e}"}

    if not corp:
        return {"success": False,
                "error": f"'{company_name}' 기업을 DART에서 찾을 수 없습니다."}

    fin = fetch_financials(corp["corp_code"], year)
    if not fin:
        return {"success": False,
                "error": f"'{company_name}'의 {year}년 재무제표를 조회할 수 없습니다. "
                         f"(비상장 PDF 제출 기업일 수 있음 — XBRL 미제출)"}

    try:
        disc = fetch_disclosures(corp["corp_code"], year)
    except Exception:
        disc = {"list": []}  # 공시목록은 실패해도 치명적이지 않음

    result = {
        "success": True,
        "company": corp,
        "year": year,
        "financials": fin,
        "disclosures": disc,
        "meta": fin.get("_meta", {}),
    }

    # raw 보존 (감사 추적 + 디버깅)
    raw_path = config.RAW_DIR / f"{company_name}_{year}.json"
    raw_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return result


# ──────────────────────────────────────────────
# 단독 테스트
# ──────────────────────────────────────────────
if __name__ == "__main__":
    r = collect("삼성전자", 2023)
    if r["success"]:
        print(f"성공: {r['company']['corp_name']} "
              f"(corp_code={r['company']['corp_code']}, "
              f"stock={r['company']['stock_code']})")
        print(f"메타: {r['meta']}")
        print(f"재무 계정 수: {len(r['financials']['list'])}")
        print(f"공시 건수: {len(r['disclosures'].get('list', []))}")
        # 계정 몇 개 샘플 출력
        for acc in r["financials"]["list"][:5]:
            print(f"  - {acc.get('account_nm')}: "
                  f"당기 {acc.get('thstrm_amount')}")
    else:
        print(f"실패: {r['error']}")
