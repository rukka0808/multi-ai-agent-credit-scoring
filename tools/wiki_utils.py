# tools/wiki_utils.py
"""
공유 markdown 위키를 읽고 쓰는 유틸리티.
LLM 호출 없음. 순수 파일 I/O와 로깅만 담당.
"""
import datetime
from pathlib import Path
import config


def _ensure_wiki_dir() -> Path:
    """wiki 디렉터리가 없으면 생성하고 경로 반환."""
    config.WIKI_DIR.mkdir(parents=True, exist_ok=True)
    return config.WIKI_DIR


def write_page(page_name: str, content: str, agent_name: str = "system") -> Path:
    """
    위키 페이지를 통째로 작성/덮어쓴다.
    page_name: 확장자 없는 이름 (예: 'financials')
    """
    _ensure_wiki_dir()
    path = config.WIKI_DIR / f"{page_name}.md"
    path.write_text(content, encoding="utf-8")
    log_event(f"[{agent_name}] '{page_name}.md' 작성 ({len(content)}자)")
    _update_index()
    return path


def read_page(page_name: str) -> str:
    """위키 페이지 내용을 읽는다. 없으면 빈 문자열."""
    path = config.WIKI_DIR / f"{page_name}.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_all_pages() -> str:
    """
    index/log를 제외한 모든 위키 페이지를 하나의 문자열로 합친다.
    PM 에이전트가 위키 전체를 query할 때 사용.
    """
    _ensure_wiki_dir()
    skip = {"index", "log"}
    chunks = []
    for path in sorted(config.WIKI_DIR.glob("*.md")):
        if path.stem in skip:
            continue
        chunks.append(f"# ===== {path.stem}.md =====\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def log_event(message: str) -> None:
    """log.md에 타임스탬프와 함께 이벤트를 누적 기록한다."""
    _ensure_wiki_dir()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"- {ts} | {message}\n"
    log_path = config.WIKI_DIR / "log.md"
    if not log_path.exists():
        log_path.write_text("# 작업 로그\n\n", encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def _update_index() -> None:
    """현재 위키에 존재하는 페이지 목록으로 index.md를 갱신한다."""
    skip = {"index", "log"}
    lines = ["# 위키 인덱스\n"]
    for path in sorted(config.WIKI_DIR.glob("*.md")):
        if path.stem in skip:
            continue
        lines.append(f"- [{path.stem}]({path.name})")
    (config.WIKI_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def reset_wiki() -> None:
    """새 분석 시작 시 위키를 초기화한다 (이전 기업 데이터 제거)."""
    _ensure_wiki_dir()
    for path in config.WIKI_DIR.glob("*.md"):
        path.unlink()
    log_event("위키 초기화")
