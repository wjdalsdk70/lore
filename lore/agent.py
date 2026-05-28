# Claude API 대화 로직
import time

import anthropic

from . import tools
from .config import INDEX_PATH, MODEL_CHAT

client = anthropic.Anthropic()

SYSTEM = """\
당신은 Brain Wiki 사서입니다. 개발자 이정민의 기술 지식 베이스를 관리합니다.

출력 규칙 (절대 지킬 것):
- 볼드(**), 이탤릭(*), 이모지 사용 금지
- 한국어, 간결하게

역할:
- wiki 내용을 검색하고 질문에 답합니다
- 요청하면 wiki 페이지를 업데이트합니다
- 세션 기록을 분석해서 중요한 내용을 wiki에 저장합니다

기록 기준: 기술 결정+이유, 비자명한 제약, 버그 원인, 반복 패턴
기록 제외: 코드/README 내용, 단순 질답, 일시적 상태\
"""

history: list[dict] = []


def _system() -> str:
    index = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
    return SYSTEM + f"\n\n## Wiki 인덱스\n{index[:2500]}"


def chat(user_message: str, on_tool_call=None) -> str:
    history.append({"role": "user", "content": user_message})

    while True:
        resp = client.messages.create(
            model=MODEL_CHAT,
            max_tokens=2000,
            system=_system(),
            tools=tools.DEFINITIONS,
            messages=history,
        )

        if resp.stop_reason == "tool_use":
            history.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                t0 = time.time()
                result = tools.run(block.name, block.input)
                elapsed = time.time() - t0
                if on_tool_call:
                    on_tool_call(block.name, block.input, elapsed)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
            history.append({"role": "user", "content": results})
            continue

        text = "\n".join(b.text for b in resp.content if hasattr(b, "text"))
        history.append({"role": "assistant", "content": text})

        if len(history) > 24:
            history[:] = history[-20:]

        return text


def clear_history():
    history.clear()
