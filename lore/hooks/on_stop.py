#!/usr/bin/env python3
# Stop hook: 세션 종료 시 lore queue에 분석 요청 등록

import json
import sys
from pathlib import Path

QUEUE_DIR = Path("/Users/minty/JM/brain/queue")


def main():
    try:
        data = json.load(sys.stdin)
        transcript_path = data.get('transcript_path', '')
        session_id = data.get('session_id', '')

        if not transcript_path or not Path(transcript_path).exists():
            return

        QUEUE_DIR.mkdir(exist_ok=True)
        queue_file = QUEUE_DIR / f"{session_id}.json"

        if queue_file.exists():
            return

        queue_file.write_text(json.dumps({
            'session_id': session_id,
            'transcript_path': transcript_path,
        }, ensure_ascii=False))

    except Exception:
        pass


if __name__ == '__main__':
    main()
