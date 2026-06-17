"""
실시간 거시 지표(환율) 수집 도구. LLM 미사용.
Frankfurter API(키 불필요, ECB 데이터 기반)로 원/달러 환율을 가져온다.
네트워크 실패 시 안전한 기본값으로 폴백한다.
"""
import json
import ssl
import urllib.request
from urllib.error import URLError, HTTPError

# 네트워크 실패 시 사용할 폴백 값(분석 중단을 막기 위함)
_FALLBACK = {
    "원/달러 환율": "데이터 조회 실패 (N/A)",
    "기준금리": "3.50%",  # 금리는 별도 API가 없어 수동 설정값 유지
}


def _http_get_json(url: str, timeout: int = 10) -> dict:
    ctx = ssl.create_default_context()  # SSL 검증 활성화 (CERT_NONE 사용 안 함)
    req = urllib.request.Request(url, headers={"User-Agent": "dart-loan-review/1.0"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_usd_krw() -> dict:
    """
    USD/KRW 환율을 조회한다.
    Frankfurter는 EUR 기준이므로 EUR->USD, EUR->KRW로 USD/KRW를 환산한다.
    반환: {'rate': float|None, 'date': str|None, 'source': str}
    """
    url = "https://api.frankfurter.dev/v1/latest?base=EUR&symbols=USD,KRW"
    try:
        data = _http_get_json(url)
        rates = data.get("rates", {})
        eur_usd = rates.get("USD")
        eur_krw = rates.get("KRW")
        if not eur_usd or not eur_krw:
            return {"rate": None, "date": None, "source": "frankfurter(불완전)"}
        usd_krw = eur_krw / eur_usd
        return {
            "rate": round(usd_krw, 2),
            "date": data.get("date"),
            "source": "Frankfurter (ECB)",
        }
    except (URLError, HTTPError, TimeoutError, ValueError) as e:
        return {"rate": None, "date": None, "source": f"조회 실패: {e}"}


def collect_macro(base_rate: str = "3.50%") -> dict:
    """
    매크로 에이전트에 넘길 거시 지표 dict를 구성한다.
    환율은 실시간 조회, 기준금리는 인자로 받은 값(별도 무료 API 부재).
    """
    fx = fetch_usd_krw()
    if fx["rate"] is not None:
        fx_str = f"약 {fx['rate']:,.0f}원 (기준일 {fx['date']}, 출처 {fx['source']})"
    else:
        fx_str = _FALLBACK["원/달러 환율"]

    return {
        "기준금리": base_rate,
        "원/달러 환율": fx_str,
    }


if __name__ == "__main__":
    print(fetch_usd_krw())
    print(collect_macro())
