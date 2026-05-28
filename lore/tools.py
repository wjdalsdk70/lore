# wiki 도구 정의 및 실행
import re
from datetime import date
from pathlib import Path

from .config import VAULT_DIR, WIKI_DIR, LOG_PATH, INDEX_PATH

DEFINITIONS = [
    {
        "name": "wiki_read",
        "description": "wiki 페이지 전체 읽기",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "wiki 경로 (예: wiki/projects/cm/CareNote/CareNote-BE)"}
            },
            "required": ["path"],
        },
    },
    {
        "name": "wiki_search",
        "description": "wiki 키워드 검색 — 관련 페이지 목록 반환",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "wiki_append",
        "description": "wiki 페이지 섹션에 내용 추가. section 없으면 파일 끝에 추가.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string"},
                "section": {"type": "string", "description": "추가할 섹션 제목 (예: ## 주요 결정사항)"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "wiki_create",
        "description": "새 wiki 페이지 생성 + index.md에 자동 등록. 기존 페이지가 없을 때만 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":        {"type": "string", "description": "wiki 경로 (예: wiki/projects/cm/NewProject)"},
                "title":       {"type": "string", "description": "페이지 제목"},
                "content":     {"type": "string", "description": "초기 내용"},
                "index_desc":  {"type": "string", "description": "index.md에 등록할 한 줄 설명"},
                "index_section": {
                    "type": "string",
                    "description": "index.md 섹션 (개념, 프로젝트, How-to 중 하나)",
                    "enum": ["개념", "프로젝트", "How-to"],
                },
            },
            "required": ["path", "title", "content", "index_desc", "index_section"],
        },
    },
    {
        "name": "wiki_list",
        "description": "wiki 파일 전체 목록",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "log_append",
        "description": "log.md에 작업 기록 추가",
        "input_schema": {
            "type": "object",
            "properties": {"entry": {"type": "string", "description": "작업 | 대상 | 요약 형식"}},
            "required": ["entry"],
        },
    },
]


def _resolve(path: str) -> Path:
    path = path.lstrip("/")
    if not path.endswith(".md"):
        path += ".md"
    direct = VAULT_DIR / path
    if direct.exists():
        return direct
    under_wiki = VAULT_DIR / "wiki" / path
    return under_wiki if under_wiki.exists() else direct


def run(name: str, inputs: dict) -> str:
    if name == "wiki_read":
        p = _resolve(inputs["path"])
        return p.read_text(encoding="utf-8") if p.exists() else f"파일 없음: {inputs['path']}"

    if name == "wiki_search":
        words = re.findall(r'[가-힣a-zA-Z]{2,}', inputs.get("query", ""))
        if not words:
            return "검색어 없음"
        pat = re.compile("|".join(re.escape(w) for w in words[:10]), re.IGNORECASE)
        results = []
        for f in WIKI_DIR.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                hits = len(pat.findall(content))
                if hits:
                    sample = next(
                        (l.strip() for l in content.splitlines() if pat.search(l) and l.strip()),
                        ""
                    )
                    results.append((hits, str(f.relative_to(VAULT_DIR)), sample[:80]))
            except Exception:
                continue
        results.sort(key=lambda x: -x[0])
        return "\n".join(f"{h}회  {p}" for h, p, _ in results[:10]) if results else "검색 결과 없음"

    if name == "wiki_append":
        p = _resolve(inputs["path"])
        if not p.exists():
            return f"파일 없음: {inputs['path']}"
        content = p.read_text(encoding="utf-8")
        section = inputs.get("section", "").strip()
        append_text = inputs["content"].strip()
        if section and section in content:
            idx = content.index(section)
            m = re.search(r"\n## ", content[idx + 1:])
            insert_at = idx + 1 + m.start() if m else len(content)
            updated = content[:insert_at].rstrip() + "\n" + append_text + "\n" + content[insert_at:]
        else:
            header = f"\n\n{section}\n" if section else "\n\n"
            updated = content.rstrip() + header + append_text + "\n"
        p.write_text(updated, encoding="utf-8")
        return f"완료: {p.relative_to(VAULT_DIR)}"

    if name == "wiki_create":
        path = inputs["path"].lstrip("/")
        if not path.endswith(".md"):
            path += ".md"
        p = VAULT_DIR / path
        if p.exists():
            return f"이미 존재: {path} — wiki_append 사용"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {inputs['title']}\n\n{inputs['content'].strip()}\n", encoding="utf-8")

        # index.md 자동 등록
        section_map = {
            "개념":   "## 개념 (wiki/concepts/)",
            "프로젝트": "## 프로젝트 (wiki/projects/)",
            "How-to": "## How-to (wiki/howto/)",
        }
        section_header = section_map.get(inputs.get("index_section", "프로젝트"), "## 프로젝트 (wiki/projects/)")
        new_entry = f"- [[{path[:-3]}]] — {inputs['index_desc']}"

        if INDEX_PATH.exists():
            index = INDEX_PATH.read_text(encoding="utf-8")
            if section_header in index:
                idx = index.index(section_header)
                # 섹션 끝 (다음 --- 또는 ## 전)
                end = re.search(r"\n---|\n## ", index[idx + 1:])
                insert_at = idx + 1 + end.start() if end else len(index)
                # 기존 마지막 항목 뒤에 삽입
                block = index[idx:insert_at]
                last_entry = block.rfind("\n- ")
                if last_entry != -1:
                    insert_at = idx + last_entry + 1 + len(block[last_entry + 1:].split("\n")[0]) + 1
                updated = index[:insert_at].rstrip() + "\n" + new_entry + "\n" + index[insert_at:]
                # 총 페이지 수 업데이트
                total = len(list(WIKI_DIR.rglob("*.md")))
                updated = re.sub(r"\*\*총 페이지 수:\*\* \d+", f"**총 페이지 수:** {total}", updated)
                INDEX_PATH.write_text(updated, encoding="utf-8")

        rel = str(p.relative_to(VAULT_DIR))
        return f"생성 완료: {rel}\nindex.md 등록: {new_entry}"

    if name == "wiki_list":
        return "\n".join(sorted(str(f.relative_to(VAULT_DIR)) for f in WIKI_DIR.rglob("*.md")))

    if name == "log_append":
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n## [{date.today()}] {inputs['entry'].strip()}")
        return "기록 완료"

    return f"알 수 없는 도구: {name}"
