# tools/pdf_export.py
"""
최종 markdown 보고서를 세련된 PDF/HTML로 변환한다.
의존성: pip install markdown weasyprint
weasyprint 실패 시 HTML로 폴백(브라우저에서 'PDF로 인쇄' 가능).
"""
import re
from pathlib import Path
import markdown as md
import config


# 등급별 색상(토스 톤)
GRADE_COLORS = {
    "A": "#15803d",  # green
    "B": "#3182f6",  # blue
    "C": "#f59e0b",  # amber
    "D": "#f97316",  # orange
    "E": "#ef4444",  # red
}


def _normalize_markdown(text: str) -> str:
    """LLM이 쓴 '* ' / '*   ' 불릿을 표준 '- '로 정규화."""
    return re.sub(r'(?m)^\s*\*\s+', '- ', text)


def _extract_verdict(report_md: str) -> dict:
    """보고서 상단 인용 블록에서 등급/총점/의견/신호를 파싱.
    헤더 카드로 예쁘게 렌더링하기 위함."""
    grade = score = opinion = signals = None
    m = re.search(r"등급:\s*([A-E])", report_md)
    if m: grade = m.group(1)
    m = re.search(r"총점:\s*(-?\d+/\d+)", report_md)
    if m: score = m.group(1)
    m = re.search(r"의견:\s*([^\n|]+)", report_md)
    if m: opinion = m.group(1).strip()
    m = re.search(r"위험 신호:\s*([^\n]+)", report_md)
    if m: signals = m.group(1).strip().rstrip(")")
    return {"grade": grade, "score": score, "opinion": opinion, "signals": signals}


def _build_header_card(verdict: dict, company: str, year: int) -> str:
    """등급을 큰 배지로 보여주는 헤더 카드 HTML."""
    grade = verdict.get("grade") or "N/A"
    color = GRADE_COLORS.get(grade, "#8b95a1")
    score = verdict.get("score") or "-"
    opinion = verdict.get("opinion") or "-"
    signals = verdict.get("signals") or "없음"
    sig_danger = signals not in ("없음", "", None)

    return f"""
<div class="verdict-card">
  <div class="verdict-left">
    <div class="company">{company}</div>
    <div class="year">{year} 사업연도 · 여신 심사</div>
    <div class="opinion">{opinion}</div>
  </div>
  <div class="verdict-grade" style="background:{color}">
    <div class="grade-label">등급</div>
    <div class="grade-value">{grade}</div>
    <div class="grade-score">{score}</div>
  </div>
</div>
<div class="signal-bar {'danger' if sig_danger else 'safe'}">
  <span class="signal-icon">{'⚠' if sig_danger else '✓'}</span>
  위험 신호: {signals}
</div>
"""


# ── 헤더 카드 추출 후 본문에서 원래 인용 블록 제거용 ──
def _strip_verdict_block(report_md: str) -> str:
    """상단 '코드 확정 사실' 인용 블록을 본문에서 제거(카드로 대체)."""
    # 첫 번째 markdown 제목과 인용(>) 블록을 제거
    lines = report_md.splitlines()
    out, skipping = [], False
    for ln in lines:
        if ln.strip().startswith("> ") or "코드 확정" in ln:
            skipping = True
            continue
        if skipping and ln.strip() == "":
            skipping = False
            continue
        out.append(ln)
    return "\n".join(out)


CSS = """
@page { size: A4; margin: 22mm 18mm; }
* { box-sizing: border-box; }
body {
  font-family: 'Pretendard', -apple-system, BlinkMacSystemFont,
               'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  color: #191f28; line-height: 1.7; font-size: 10.5pt;
  -webkit-font-smoothing: antialiased;
}

/* 상단 등급 카드 */
.verdict-card {
  display: flex; justify-content: space-between; align-items: stretch;
  border: 1px solid #e5e8eb; border-radius: 16px;
  padding: 22px 24px; margin-bottom: 12px;
  background: #fff;
}
.verdict-left { display: flex; flex-direction: column; justify-content: center; }
.company { font-size: 22pt; font-weight: 800; letter-spacing: -0.5px; }
.year { color: #8b95a1; font-size: 10pt; margin-top: 2px; }
.opinion { margin-top: 12px; font-size: 13pt; font-weight: 700; color: #191f28; }
.verdict-grade {
  color: #fff; border-radius: 14px; padding: 14px 22px;
  text-align: center; min-width: 110px;
  display: flex; flex-direction: column; justify-content: center;
}
.grade-label { font-size: 9pt; opacity: 0.85; }
.grade-value { font-size: 38pt; font-weight: 800; line-height: 1; margin: 2px 0; }
.grade-score { font-size: 10pt; opacity: 0.9; }

/* 위험 신호 바 */
.signal-bar {
  border-radius: 10px; padding: 10px 16px; font-size: 10pt; font-weight: 600;
  margin-bottom: 26px;
}
.signal-bar.safe { background: #e8f7ee; color: #15803d; }
.signal-bar.danger { background: #fdeded; color: #d92d20; }
.signal-icon { margin-right: 6px; font-weight: 700; }

/* 섹션 제목 */
h1, h2, h3 { letter-spacing: -0.3px; }
h2 {
  font-size: 14pt; font-weight: 700; margin: 26px 0 10px;
  padding-left: 10px; border-left: 4px solid #3182f6;
}
h3 { font-size: 12pt; font-weight: 700; margin: 18px 0 8px; }

/* 본문 */
p { margin: 8px 0; }
strong { color: #0b1320; font-weight: 700; }

/* 리스트 */
ul { margin: 8px 0; padding-left: 0; list-style: none; }
li {
  position: relative; padding-left: 18px; margin: 6px 0;
}
li::before {
  content: ""; position: absolute; left: 4px; top: 0.62em;
  width: 5px; height: 5px; border-radius: 50%; background: #3182f6;
}

/* 인용/유의사항 */
blockquote {
  background: #f8f9fb; border-left: 3px solid #c4cdd6;
  border-radius: 8px; padding: 10px 16px; margin: 12px 0;
  color: #4e5968; font-size: 9.5pt;
}

/* 푸터 */
.footer {
  margin-top: 30px; padding-top: 12px; border-top: 1px solid #e5e8eb;
  color: #b0b8c1; font-size: 8.5pt; text-align: center;
}
"""


def export(report_md: str, company_name: str, year: int) -> Path:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    verdict = _extract_verdict(report_md)
    body_md = _normalize_markdown(_strip_verdict_block(report_md))
    # 본문 첫 줄에 남은 큰 제목(중복) 제거
    body_md = re.sub(r'(?m)^#\s+.*여신 심사 보고서.*$', '', body_md, count=1)

    html_body = md.markdown(body_md, extensions=["tables", "fenced_code", "nl2br"])
    header_card = _build_header_card(verdict, company_name, year)

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
{header_card}
{html_body}
<div class="footer">
  본 보고서는 데모 목적의 자동 생성 결과이며, 실제 여신·투자 판단의 근거가 될 수 없습니다.<br>
  AI 여신 심사 시스템 · DART 공시 데이터 기반
</div>
</body></html>"""

    out_path = config.OUTPUT_DIR / f"여신심사보고서_{company_name}_{year}.pdf"
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(out_path))
    except Exception as e:
        out_path = out_path.with_suffix(".html")
        out_path.write_text(html, encoding="utf-8")
        print(f"[경고] PDF 변환 실패({e}). HTML로 저장: {out_path}")
    return out_path
