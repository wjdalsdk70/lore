#!/usr/bin/env python3
# UserPromptSubmit hook: wiki 검색 후 관련 컨텍스트를 system-reminder로 주입

import json
import re
import sys
from pathlib import Path

VAULT_DIR = Path("/Users/minty/JM/brain")
WIKI_DIR  = VAULT_DIR / "wiki"

MAX_RESULT_PAGES = 3
MAX_LINES_PER_PAGE = 25

STOP_WORDS = {
    'the','a','an','is','are','was','were','be','been','have','has','had',
    'do','does','did','will','would','could','should','may','might','can',
    'this','that','these','those','it','its','what','how','why','when',
    '이','가','을','를','은','는','에','의','로','으로','와','과','도','만',
    '그','것','들','에서','에게','이것','저것','어떻게','왜','언제','뭐','좀',
    '있어','없어','해줘','해봐','알려줘','하면','되는','되나','할','수','있',
}


def extract_keywords(text: str) -> list[str]:
    words = re.findall(r'[가-힣]{2,}|[a-zA-Z][a-zA-Z0-9]{2,}', text)
    seen, result = set(), []
    for w in words:
        lw = w.lower()
        if lw not in STOP_WORDS and lw not in seen:
            seen.add(lw)
            result.append(w)
    return result[:12]


def search_wiki(keywords: list[str]) -> list[tuple[int, Path, str]]:
    if not keywords:
        return []
    pattern = re.compile('|'.join(re.escape(k) for k in keywords), re.IGNORECASE)
    results = []
    for f in WIKI_DIR.rglob("*.md"):
        try:
            content = f.read_text(encoding='utf-8')
            hits = len(pattern.findall(content))
            if hits:
                results.append((hits, f, content))
        except Exception:
            continue
    results.sort(key=lambda x: -x[0])
    return results[:MAX_RESULT_PAGES]


def extract_relevant_sections(content: str, pattern: re.Pattern) -> str:
    lines = content.split('\n')
    selected, i = [], 0
    while i < len(lines) and len(selected) < MAX_LINES_PER_PAGE:
        if pattern.search(lines[i]):
            section_start = i
            for j in range(i, -1, -1):
                if lines[j].startswith('#'):
                    section_start = j
                    break
            chunk = lines[max(section_start, i - 1):min(len(lines), i + 6)]
            if chunk not in selected:
                selected.extend(chunk)
                selected.append('')
        i += 1
    return '\n'.join(selected).strip()


def main():
    try:
        data = json.load(sys.stdin)
        prompt = data.get('prompt', '')
        if not prompt or len(prompt.strip()) < 5:
            return

        keywords = extract_keywords(prompt)
        if not keywords:
            return

        results = search_wiki(keywords)
        if not results:
            return

        pattern = re.compile('|'.join(re.escape(k) for k in keywords), re.IGNORECASE)
        parts = []
        for _, f, content in results:
            section = extract_relevant_sections(content, pattern)
            if section:
                parts.append(f"**{f.relative_to(VAULT_DIR)}**\n{section}")

        if parts:
            print("## Lore — 관련 컨텍스트\n\n" + "\n\n---\n\n".join(parts))

    except Exception:
        pass


if __name__ == '__main__':
    main()
