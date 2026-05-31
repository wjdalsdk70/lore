# Lore

개인 로컬 지식 베이스. Claude가 읽고 저장하는 도서관입니다.

평소 작업하던 디렉터리에서 Claude Code로 대화하면, 세션이 끝날 때마다 그 안의 기술 결정과 맥락이 자동으로 wiki에 기록됩니다. 다음 세션에서는 질문과 관련된 wiki 내용이 자동으로 컨텍스트에 주입됩니다. 별도로 정리하지 않아도 지식이 쌓이고 다시 꺼내집니다.

## 동작 방식

```
                  ┌──────────────────────────────┐
   질문 입력 ───▶ │  UserPromptSubmit hook        │
                  │  wiki 검색 → 관련 컨텍스트 주입 │
                  └──────────────────────────────┘
                                 │
                  ┌──────────────────────────────┐
   세션 종료 ───▶ │  Stop hook                    │
                  │  queue/ 에 분석 요청 등록      │
                  └──────────────────────────────┘
                                 │
                  ┌──────────────────────────────┐
   백그라운드 ──▶ │  queue 루프 (lore CLI)         │
                  │  대화 분석 → wiki 자동 업데이트 │
                  └──────────────────────────────┘
```

기록 기준은 기술 결정과 이유, 비자명한 제약, 버그 원인, 반복 패턴입니다. 단순 질답이나 코드에 이미 있는 내용은 기록하지 않습니다.

## 구성

```
lore/
├── cli.py      대화 루프, 명령어, prompt_toolkit UI
├── agent.py    Claude API 대화 로직 (도구 호출 루프)
├── tools.py    wiki 도구 정의 및 실행
├── queue.py    백그라운드 세션 분석 → wiki 자동 기록
├── config.py   경로 상수, 설정 파일, API 키 관리
└── hooks/
    ├── on_prompt.py   질문 시 wiki 컨텍스트 주입
    └── on_stop.py     세션 종료 시 분석 큐 등록
```

vault 디렉터리 구조입니다.

```
brain/
├── wiki/
│   ├── projects/   프로젝트 노트
│   ├── concepts/   기술 개념·패턴
│   └── howto/      반복 작업 절차
├── queue/          분석 대기 세션
├── index.md        전체 wiki 인덱스 (system prompt에 주입)
└── log.md          작업 기록
```

## 설치

```bash
pip install -e .
```

의존성은 `anthropic`, `questionary`, `tavily-python`, `prompt-toolkit`이며 Python 3.11 이상이 필요합니다.

## 초기 설정

```bash
lore init
```

vault 경로와 API 키(`TAVILY_API_KEY`, `ANTHROPIC_API_KEY`)를 입력하면 설정이 `~/.config/lore/config.json`에 저장되고, vault 디렉터리 구조가 생성됩니다.

Claude Code hook 연동은 `~/.claude/settings.json`에 다음을 추가합니다.

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "python3 -m lore.hooks.on_prompt" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "python3 -m lore.hooks.on_stop" }] }
    ]
  }
}
```

## 사용

```bash
lore
```

대화창에서 wiki 내용을 묻거나 페이지 업데이트를 요청합니다. 명령어는 다음과 같습니다.

| 명령어 | 설명 |
|--------|------|
| `/help` | 명령어 목록 |
| `/status` | wiki 상태 (페이지 수, 큐, 분석 진행 상황) |
| `/log [n]` | 최근 기록 n개 (기본 5) |
| `/model [name]` | 모델 조회 / 변경 (haiku, sonnet, opus) |
| `/search` | 웹 검색 도구 변경 (tavily, anthropic, none) |
| `/clear` | 화면 + 대화 초기화 |
| `/quit` | 종료 |

## 도구

Claude가 대화 중 호출하는 wiki 도구입니다.

| 도구 | 역할 |
|------|------|
| `wiki_read` | 페이지 전체 읽기 |
| `wiki_search` | 키워드 검색 |
| `wiki_append` | 섹션에 내용 추가 |
| `wiki_create` | 새 페이지 생성 + index.md 자동 등록 |
| `wiki_list` | 전체 파일 목록 |
| `web_search` | 웹 검색 (Tavily 또는 Anthropic) |
| `log_append` | log.md에 작업 기록 추가 |

## 모델

대화는 `claude-sonnet-4-6`, 백그라운드 자동 분석은 `claude-haiku-4-5`를 기본으로 사용합니다.
