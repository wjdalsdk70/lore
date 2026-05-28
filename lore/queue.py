# 백그라운드 세션 자동 분석 및 wiki 업데이트
import json
import time

import anthropic

from . import tools
from .config import INDEX_PATH, MODEL_AUTO, QUEUE_DIR

client = anthropic.Anthropic()

AUTO_PROMPT = """\
아래 대화를 분석해서 wiki에 기록할 내용이 있으면 wiki_append 도구로 저장하세요.
기록 기준: 기술 결정+이유, 비자명 제약, 버그 원인, 반복 패턴.
기록 제외: 코드/README 내용, 단순 질답.
없으면 응답 없이 종료.\
"""

_SYSTEM = """\
당신은 Brain Wiki 사서입니다. 개발자 이정민의 기술 지식 베이스를 관리합니다.
기록 기준: 기술 결정+이유, 비자명한 제약, 버그 원인, 반복 패턴.
기록 제외: 코드/README 내용, 단순 질답, 일시적 상태.\
"""

# 현재 처리 중인 세션 상태 (None = 대기 중)
_active: dict | None = None


def get_active() -> dict | None:
    return _active


def _read_transcript(path: str) -> str:
    msgs = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    t = obj.get("type")
                    if t == "user":
                        c = obj.get("message", {}).get("content", "")
                        clean = c.split("## Brain Wiki")[0].strip() if isinstance(c, str) else ""
                        if clean and len(clean) > 5:
                            msgs.append(f"U: {clean[:300]}")
                    elif t == "assistant":
                        c = obj.get("message", {}).get("content", [])
                        text = " ".join(
                            x.get("text", "") for x in c
                            if isinstance(x, dict) and x.get("type") == "text"
                        ) if isinstance(c, list) else str(c)
                        if text.strip():
                            msgs.append(f"A: {text.strip()[:400]}")
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        pass
    return "\n\n".join(msgs[-30:])


def analyze(transcript_path: str):
    global _active
    convo = _read_transcript(transcript_path)
    if len(convo.strip()) < 100:
        return

    index = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
    system = _SYSTEM + f"\n\n## Wiki 인덱스\n{index[:2500]}"
    msgs = [{"role": "user", "content": AUTO_PROMPT + f"\n\n---\n\n{convo}"}]

    while True:
        resp = client.messages.create(
            model=MODEL_AUTO,
            max_tokens=1500,
            system=system,
            tools=tools.DEFINITIONS,
            messages=msgs,
        )
        if resp.stop_reason != "tool_use":
            break

        msgs.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            result = tools.run(block.name, block.input)
            if block.name == "wiki_append" and _active is not None:
                _active["records"].append(block.input.get("path", ""))
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})
        msgs.append({"role": "user", "content": results})


def loop():
    global _active
    QUEUE_DIR.mkdir(exist_ok=True)
    while True:
        for qf in list(QUEUE_DIR.glob("*.json")):
            try:
                data = json.loads(qf.read_text(encoding="utf-8"))
                sid = data.get("session_id", "")
                _active = {"session_id": sid, "records": []}
                analyze(data.get("transcript_path", ""))
                qf.unlink()
            except Exception:
                try:
                    qf.rename(qf.with_suffix(".failed"))
                except Exception:
                    pass
            finally:
                _active = None
        time.sleep(10)
