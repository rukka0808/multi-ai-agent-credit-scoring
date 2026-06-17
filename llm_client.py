"""Gemini 호출 래퍼. 무료티어 대응(대기/재시도) + JSON 파싱 방어 + 호출 로깅."""
import time
import json
import re
from google import genai
from google.genai import errors as genai_errors

import config


class LLMClient:
    def __init__(self, model: str = None):
        config.validate()
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model = model or config.GEMINI_MODEL
        self.call_count = 0       # 호출 횟수 추적 (보고서용 통계)
        self._last_call_time = 0.0

    def _throttle(self):
        """직전 호출로부터 LLM_REQUEST_DELAY초가 안 지났으면 대기."""
        elapsed = time.time() - self._last_call_time
        wait = config.LLM_REQUEST_DELAY - elapsed
        if wait > 0:
            time.sleep(wait)

    def generate(self, prompt: str, system: str = None) -> str:
        """텍스트 생성. 429면 지수 백오프로 재시도."""
        self._throttle()

        contents = prompt
        cfg = None
        if system:
            from google.genai import types
            cfg = types.GenerateContentConfig(system_instruction=system)

        last_err = None
        for attempt in range(config.LLM_MAX_RETRIES):
            try:
                resp = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=cfg,
                )
                self.call_count += 1
                self._last_call_time = time.time()
                return (resp.text or "").strip()

            except genai_errors.APIError as e:
                last_err = e
                # 429(한도초과)나 503(과부하)이면 기다렸다 재시도
                code = getattr(e, "code", None)
                if code in (429, 503):
                    delay = config.LLM_RETRY_BASE_DELAY * (2 ** attempt)
                    print(f"  [LLM] {code} 한도/과부하. {delay:.0f}초 대기 후 재시도 "
                          f"({attempt + 1}/{config.LLM_MAX_RETRIES})")
                    time.sleep(delay)
                    continue
                raise  # 다른 에러는 그대로 던짐

        raise RuntimeError(f"LLM 호출 {config.LLM_MAX_RETRIES}회 모두 실패: {last_err}")

    def generate_json(self, prompt: str, system: str = None) -> dict:
        """JSON 응답 전용. 코드펜스/잡텍스트를 벗겨내고 파싱. 실패 시 1회 재요청."""
        for attempt in range(2):
            raw = self.generate(prompt, system=system)
            parsed = self._extract_json(raw)
            if parsed is not None:
                return parsed
            # 첫 시도 실패 시, 형식을 더 강하게 지시해 재요청
            prompt = (
                prompt
                + "\n\n반드시 유효한 JSON 객체만 출력하세요. "
                  "설명 문장이나 ```코드펜스``` 없이 { 로 시작해 } 로 끝나야 합니다."
            )
        raise ValueError(f"JSON 파싱 실패. 마지막 응답:\n{raw[:500]}")

    @staticmethod
    def _extract_json(text: str):
        """코드펜스 제거 후 첫 { ... } 블록을 파싱 시도."""
        # ```json ... ``` 펜스 제거
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(),
                      flags=re.MULTILINE)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 본문 어딘가의 { ... } 추출 시도
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


# Module-level facade functions to allow calling directly as llm_client.generate()
_default_client = None

def generate(prompt: str, system: str = None) -> str:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client.generate(prompt, system)

def generate_json(prompt: str, system: str = None) -> dict:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client.generate_json(prompt, system)


def __getattr__(name: str):
    if name == "call_count":
        return _default_client.call_count if _default_client else 0
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


