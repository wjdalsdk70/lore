# CLI 진입점: 대화 루프, 명령어, readline
import readline
import shutil
import sys
import threading
import time
import unicodedata
from datetime import date

from . import agent, queue
from .config import HISTORY_FILE, QUEUE_DIR, WIKI_DIR, LOG_PATH, VAULT_DIR, save_config


# ── ANSI ──────────────────────────────────────────────────────────

class C:
    RESET = "\033[0m"
    BOLD  = "\033[1m"
    DIM   = "\033[2m"
    CYAN  = "\033[36m"
    GREEN = "\033[32m"
    GRAY  = "\033[90m"
    RED   = "\033[31m"

def bold(s):  return f"{C.BOLD}{s}{C.RESET}"
def cyan(s):  return f"{C.CYAN}{s}{C.RESET}"
def green(s): return f"{C.GREEN}{s}{C.RESET}"
def gray(s):  return f"{C.GRAY}{s}{C.RESET}"
def red(s):   return f"{C.RED}{s}{C.RESET}"
def dim(s):   return f"{C.DIM}{s}{C.RESET}"
def gold(s):  return f"\033[38;5;214m{s}{C.RESET}"

def divider(width: int | None = None) -> str:
    w = width or min(shutil.get_terminal_size().columns, 48)
    return gray("  " + "─" * (w - 2))


# ── 웰컴 패널 ──────────────────────────────────────────────────────

_LORE_BANNER = [
    "▓▓      ▓▓▓▓▓   ▓▓▓▓▓    ▓▓▓▓▓▓▓",
    "▓▓     ▓▓   ▓▓  ▓▓  ▓▓   ▓▓     ",
    "▓▓     ▓▓   ▓▓  ▓▓▓▓▓    ▓▓▓▓▓▓ ",
    "▓▓     ▓▓   ▓▓  ▓▓  ▓▓   ▓▓     ",
    "▓▓▓▓▓   ▓▓▓▓▓   ▓▓   ▓▓  ▓▓▓▓▓▓▓",
]
_BANNER_GRAD = [130, 136, 172, 214, 220]

_SHELF = [
    r"  ┌─────────────┐  ",
    r"  │▐█▌▐█▌▐█▌▐█▌ │  ",
    r"  │▐█▌▐█▌▐█▌▐█▌ │  ",
    r"  ├─────────────┤  ",
    r"  │▐█▌▐█▌▐█▌▐█▌ │  ",
    r"  │▐█▌▐█▌▐█▌▐█▌ │  ",
    r"  ├─────────────┤  ",
    r"  │▐█▌▐█▌▐█▌▐█▌ │  ",
    r"  │▐█▌▐█▌▐█▌▐█▌ │  ",
    r"  └─────────────┘  ",
]
_SHELF_W = max(len(line) for line in _SHELF)


def _ansi_len(s: str) -> int:
    n, esc = 0, False
    for ch in s:
        if ch == "\033":
            esc = True
        elif esc:
            if ch == "m":
                esc = False
        else:
            n += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return n


def _welcome_panel(pages: int, pending: int) -> str:
    w       = min(shutil.get_terminal_size().columns, 90)
    inner   = w - 4
    gap     = 2
    right_w = max(20, inner - _SHELF_W - gap)

    def _banner_row(line: str, code: int) -> str:
        pad = max(0, (w - len(line)) // 2)
        if sys.stdout.isatty():
            return f"\033[38;5;{code}m{' ' * pad}{line}\033[0m"
        return " " * pad + line

    def _rule(kind: str = "mid") -> str:
        if kind == "top":    l, m, r = "┌", "─", "┐"
        elif kind == "bottom": l, m, r = "└", "─", "┘"
        else:                  l, m, r = "├", "─", "┤"
        return gray(l + m * (w - 2) + r)

    def _row(content: str) -> str:
        pad = max(0, inner - _ansi_len(content))
        return gray("│") + " " + content + " " * pad + " " + gray("│")

    def _combined(shelf_line: str, right_content: str) -> str:
        lpad = " " * (_SHELF_W - len(shelf_line))
        rpad = " " * max(0, right_w - _ansi_len(right_content))
        return (
            gray("│") + " "
            + gold(shelf_line) + lpad + " " * gap
            + right_content + rpad
            + " " + gray("│")
        )

    q_text = cyan(f"{pending} queued") if pending else gray("0 queued")
    stat_rows = [
        f"{gray('pages')}   {bold(str(pages))}",
        f"{gray('queue')}   {q_text}",
        "",
        f"{bold('Lore')}  {gray('personal wiki')}",
        gray("claude-haiku  ·  brain/"),
    ]
    n_shelf = len(_SHELF)
    n_stat  = len(stat_rows)
    pad_top = (n_shelf - n_stat) // 2
    right_rows = [""] * pad_top + stat_rows + [""] * (n_shelf - n_stat - pad_top)

    combined = [_combined(_SHELF[i], right_rows[i]) for i in range(n_shelf)]

    hint = (
        f"{gold('/help')} 명령어"
        f"  {gray('·')}  {gold('/status')} 상태"
        f"  {gray('·')}  {gold('/clear')} 초기화"
        f"  {gray('·')}  {gold('/quit')} 종료"
    )

    lines = (
        [""]
        + [_banner_row(ln, _BANNER_GRAD[i]) for i, ln in enumerate(_LORE_BANNER)]
        + [""]
        + [_rule("top")]
        + combined
        + [_rule("mid")]
        + [_row(hint)]
        + [_rule("bottom")]
    )
    return "\n".join(lines)


# ── 명령어 ────────────────────────────────────────────────────────

def cmd_help():
    rows = [
        ("/help",      "명령어 목록"),
        ("/status",    "wiki 상태"),
        ("/log [n]",   "최근 기록 n개 (기본 5)"),
        ("/clear",     "화면 + 대화 초기화"),
        ("/quit",      "종료"),
    ]
    print()
    for cmd, desc in rows:
        print(f"  {cyan(cmd):<24} {gray(desc)}")
    print()


def cmd_status():
    pages   = len(list(WIKI_DIR.rglob("*.md")))
    pending = len(list(QUEUE_DIR.glob("*.json"))) if QUEUE_DIR.exists() else 0
    log_text = LOG_PATH.read_text(encoding="utf-8") if LOG_PATH.exists() else ""
    total   = log_text.count("\n## [")
    today   = log_text.count(str(date.today()))
    active  = queue.get_active()

    print()
    print(f"  {gray('pages')}   {bold(str(pages))}")
    print(f"  {gray('queue')}   {bold(str(pending))}")
    if active:
        sid = active["session_id"][:8]
        print(f"  {gray('active')}  {dim(sid)}  {gray('분석 중')}")
        for rec in active["records"]:
            print(f"    {green('●')} {gray(rec)}")
    print(f"  {gray('records')} {bold(str(total))}  {gray(f'today {today}')}")
    print()


def cmd_log(n: int = 5):
    if not LOG_PATH.exists():
        print(f"\n  {gray('로그 없음')}\n")
        return
    text = LOG_PATH.read_text(encoding="utf-8")
    raw = [e for e in text.split("\n## [") if e.strip()]
    recent = raw[-n:]
    print()
    for entry in recent:
        try:
            date_end = entry.index("]")
            date  = entry[:date_end]
            parts = [p.strip() for p in entry[date_end + 1:].strip().split("|")]
            kind    = parts[0] if parts else ""
            target  = parts[1] if len(parts) > 1 else ""
            summary = parts[2][:60] if len(parts) > 2 else ""
            print(f"  {gray(date)}  {cyan(kind):<16} {dim(target):<28} {gray(summary)}")
        except Exception:
            continue
    print()


def cmd_clear():
    agent.clear_history()
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    pages   = len(list(WIKI_DIR.rglob("*.md")))
    pending = len(list(QUEUE_DIR.glob("*.json"))) if QUEUE_DIR.exists() else 0
    print(_welcome_panel(pages, pending))
    print()


COMMANDS: dict[str, callable] = {
    "/help":   cmd_help,
    "/status": cmd_status,
    "/clear":  cmd_clear,
}


# ── init ──────────────────────────────────────────────────────────

def _cmd_init():
    from pathlib import Path
    from .config import _CONFIG_FILE

    print()
    print(f"  {bold('Lore Init')}  {gray('brain 디렉터리 설정')}")
    print()

    default = str(VAULT_DIR)
    try:
        raw = input(f"  {gray('brain 경로')} [{cyan(default)}]  ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {gray('취소됨')}\n")
        return

    brain_dir = Path(raw).expanduser() if raw else Path(default)

    subdirs = [
        brain_dir / "wiki" / "projects",
        brain_dir / "wiki" / "concepts",
        brain_dir / "wiki" / "howto",
        brain_dir / "queue",
        brain_dir / "raw",
    ]
    for d in subdirs:
        d.mkdir(parents=True, exist_ok=True)

    index_path = brain_dir / "index.md"
    if not index_path.exists():
        index_path.write_text(
            "# Brain Wiki Index\n\n## Projects\n\n## Concepts\n\n## Howto\n",
            encoding="utf-8",
        )

    log_path = brain_dir / "log.md"
    if not log_path.exists():
        log_path.write_text("# Log\n\n", encoding="utf-8")

    save_config(brain_dir)

    print()
    print(f"  {green('✓')} {bold(str(brain_dir))}")
    print()
    print(f"  {gray('Obsidian 연결:')}  {dim('Vault → Open folder as vault → 위 경로 선택')}")
    print()
    print(f"  {gray('설정 파일:')}  {dim(str(_CONFIG_FILE))}")
    print()


# ── 콜백 ──────────────────────────────────────────────────────────

def _on_tool_call(name: str, inputs: dict, elapsed: float):
    label = str(list(inputs.values())[0])[:40] if inputs else ""
    print(f"    {gray('·')} {gray(name)}  {dim(label)}  {gray(f'{elapsed:.1f}s')}")


# ── 메인 ──────────────────────────────────────────────────────────

def _startup() -> tuple[int, int]:
    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    pages, pending = 0, 0

    def _count():
        nonlocal pages, pending
        pages   = len(list(WIKI_DIR.rglob("*.md")))
        pending = len(list(QUEUE_DIR.glob("*.json"))) if QUEUE_DIR.exists() else 0

    t = threading.Thread(target=_count)
    t.start()

    sys.stdout.write("\n")
    i = 0
    while t.is_alive() or i < 10:
        ch = SPINNER[i % len(SPINNER)]
        sys.stdout.write(f"\r  {cyan(ch)}  {gray('초기화 중')}")
        sys.stdout.flush()
        time.sleep(0.06)
        i += 1
    t.join()

    sys.stdout.write("\r\033[2K")
    sys.stdout.flush()
    return pages, pending


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        _cmd_init()
        return

    QUEUE_DIR.mkdir(exist_ok=True)

    try:
        readline.read_history_file(HISTORY_FILE)
    except Exception:
        pass
    readline.set_history_length(500)

    threading.Thread(target=queue.loop, daemon=True).start()

    pages, pending = _startup()
    print(_welcome_panel(pages, pending))
    print()

    try:
        while True:
            try:
                user_input = input(f"  {cyan('❯')} ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input in ("/quit", "/q"):
                break

            if user_input.startswith("/log"):
                parts = user_input.split()
                n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
                cmd_log(n)
                continue

            if user_input in COMMANDS:
                COMMANDS[user_input]()
                continue

            if user_input.startswith("/"):
                print(f"\n  {gray('알 수 없는 명령어  /help')}\n")
                continue

            print()
            response = agent.chat(user_input, on_tool_call=_on_tool_call)
            print(f"\n  {response.replace(chr(10), chr(10) + '  ')}\n")

    except KeyboardInterrupt:
        pass
    finally:
        readline.write_history_file(HISTORY_FILE)
        print(f"\n  {gray('bye')}\n")
