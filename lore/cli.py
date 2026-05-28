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
def white(s): return f"\033[97m{s}{C.RESET}"

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
    w     = min(shutil.get_terminal_size().columns, 96)
    inner = w - 4
    gap   = 2

    mid_w = max(20, inner - _SHELF_W * 2 - gap * 2)

    def _banner_row(line: str, code: int) -> str:
        pad = max(0, (w - len(line)) // 2)
        if sys.stdout.isatty():
            return f"\033[38;5;{code}m{' ' * pad}{line}\033[0m"
        return " " * pad + line

    def _rule(kind: str = "mid") -> str:
        if kind == "top":      l, m, r = "┌", "─", "┐"
        elif kind == "bottom": l, m, r = "└", "─", "┘"
        else:                  l, m, r = "├", "─", "┤"
        return gray(l + m * (w - 2) + r)

    def _row(content: str) -> str:
        pad = max(0, inner - _ansi_len(content))
        return gray("│") + " " + content + " " * pad + " " + gray("│")

    def _combined(left: str, mid_content: str, right: str) -> str:
        lpad = " " * (_SHELF_W - len(left))
        mpad = " " * max(0, mid_w - _ansi_len(mid_content))
        rpad = " " * (_SHELF_W - len(right))
        return (
            gray("│") + " "
            + gold(left) + lpad + " " * gap
            + mid_content + mpad + " " * gap
            + gold(right) + rpad
            + " " + gray("│")
        )

    import os
    from datetime import date as _date
    from .config import SEARCH_PROVIDER

    _search_labels = {"tavily": gold("tavily"), "anthropic": gold("anthropic"), "none": gray("─")}
    search_text = _search_labels.get(SEARCH_PROVIDER, gray(SEARCH_PROVIDER))

    log_text  = LOG_PATH.read_text(encoding="utf-8") if LOG_PATH.exists() else ""
    today_str = str(_date.today())
    today_cnt = log_text.count(today_str)

    model_full = agent.model

    q_text = cyan(f"{pending} queued") if pending else gray("─")
    stat_rows = [
        f"{white('pages')}   {bold(str(pages))}  {gray(f'+{today_cnt} today')}",
        f"{white('queue')}   {q_text}",
        f"{white('search')}  {search_text}",
        "",
        f"{bold('Lore')}  {white(str(VAULT_DIR))}",
        f"{white(model_full)}",
    ]
    n_shelf = len(_SHELF)
    n_stat  = len(stat_rows)
    pad_top = (n_shelf - n_stat) // 2
    mid_rows = [""] * pad_top + stat_rows + [""] * (n_shelf - n_stat - pad_top)

    combined = [_combined(_SHELF[i], mid_rows[i], _SHELF[i]) for i in range(n_shelf)]

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
        ("/help",         "명령어 목록"),
        ("/status",       "wiki 상태"),
        ("/log [n]",      "최근 기록 n개 (기본 5)"),
        ("/model [name]", "현재 모델 조회 / 변경"),
        ("/search",       "웹 서치 도구 변경"),
        ("/clear",        "화면 + 대화 초기화"),
        ("/quit",         "종료"),
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


_MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-7",
}


def cmd_model(arg: str | None = None):
    if arg and arg != "list":
        model_id = _MODELS.get(arg, arg)
        agent.set_model(model_id)
        print(f"\n  {green('✓')} {gray('model')}  {bold(model_id)}\n")
        return

    import questionary
    from questionary import Style

    style = Style([
        ("qmark",        "fg:#d97706 bold"),
        ("question",     "fg:#d4d4d4 bold"),
        ("answer",       "fg:#d97706 bold"),
        ("pointer",      "fg:#d97706 bold"),
        ("highlighted",  "fg:#fbbf24 bold"),
        ("selected",     "fg:#d97706"),
        ("instruction",  "fg:#525252"),
        ("text",         "fg:#a3a3a3"),
    ])

    choices = []
    for alias, mid in _MODELS.items():
        active = mid == agent.model
        label = f"{'▶ ' if active else '  '}{alias:<8}  {mid}"
        choices.append(questionary.Choice(label, value=mid))

    current = next((c for c in choices if c.value == agent.model), choices[0])
    print()
    try:
        result = questionary.select(
            "model",
            choices=choices,
            default=current,
            style=style,
            instruction="(↑↓ 이동  enter 선택  esc 취소)",
        ).unsafe_ask()
    except (KeyboardInterrupt, EOFError):
        result = None
    print()
    if result:
        agent.set_model(result)
        alias = next((k for k, v in _MODELS.items() if v == result), result)
        print(f"  {green('✓')} {gold(alias)}  {gray(result)}\n")


_SEARCH_PROVIDERS = {
    "tavily":    "Tavily API  (무료 1000 req/월)",
    "anthropic": "Anthropic SDK  (sonnet 이상 필요)",
    "none":      "웹 검색 비활성화",
}


def cmd_search():
    import questionary
    from questionary import Style
    from .config import SEARCH_PROVIDER, set_search_provider

    style = Style([
        ("qmark",       "fg:#d97706 bold"),
        ("question",    "fg:#d4d4d4 bold"),
        ("answer",      "fg:#d97706 bold"),
        ("pointer",     "fg:#d97706 bold"),
        ("highlighted", "fg:#fbbf24 bold"),
        ("selected",    "fg:#d97706"),
        ("instruction", "fg:#525252"),
        ("text",        "fg:#a3a3a3"),
    ])

    choices = []
    for key, desc in _SEARCH_PROVIDERS.items():
        active = key == SEARCH_PROVIDER
        label = f"{'▶ ' if active else '  '}{key:<12}  {desc}"
        choices.append(questionary.Choice(label, value=key))

    current = next((c for c in choices if c.value == SEARCH_PROVIDER), choices[0])
    print()
    try:
        result = questionary.select(
            "search provider",
            choices=choices,
            default=current,
            style=style,
            instruction="(↑↓ 이동  enter 선택  ctrl-c 취소)",
        ).ask()
    except (KeyboardInterrupt, EOFError):
        result = None
    print()
    if result:
        set_search_provider(result)
        print(f"  {green('✓')} {gold(result)}  {gray(_SEARCH_PROVIDERS[result])}\n")


COMMANDS: dict[str, callable] = {
    "/help":   cmd_help,
    "/status": cmd_status,
    "/clear":  cmd_clear,
    "/search": cmd_search,
}


# ── init ──────────────────────────────────────────────────────────

def _cmd_init():
    import os
    from pathlib import Path
    from .config import _CONFIG_FILE, _load_config

    print()
    print(f"  {bold('Lore Init')}  {gray('초기 설정')}")
    print()

    def _prompt(label: str, default: str, secret: bool = False) -> str:
        shown_default = ("*" * 8) if (secret and default) else (cyan(default) if default else gray("없음"))
        hint = gray("  (enter = 건너뜀)") if default else ""
        sys.stdout.write(f"  {gray(label)} [{shown_default}]{hint}  ")
        sys.stdout.flush()
        try:
            if secret:
                import getpass
                raw = getpass.getpass(prompt="")
            else:
                raw = input().strip()
        except (EOFError, KeyboardInterrupt):
            raise
        return raw.strip() if raw.strip() else default

    existing = _load_config()

    try:
        vault_raw   = _prompt("vault 경로",    existing.get("brain_dir", str(VAULT_DIR)))
        tavily_key  = _prompt("TAVILY_API_KEY", existing.get("TAVILY_API_KEY", os.environ.get("TAVILY_API_KEY", "")), secret=True)
        anthropic_key = _prompt("ANTHROPIC_API_KEY", existing.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", "")), secret=True)
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {gray('취소됨')}\n")
        return

    brain_dir = Path(vault_raw).expanduser()

    for d in [
        brain_dir / "wiki" / "projects",
        brain_dir / "wiki" / "concepts",
        brain_dir / "wiki" / "howto",
        brain_dir / "queue",
        brain_dir / "raw",
    ]:
        d.mkdir(parents=True, exist_ok=True)

    if not (brain_dir / "index.md").exists():
        (brain_dir / "index.md").write_text(
            "# Brain Wiki Index\n\n## Projects\n\n## Concepts\n\n## Howto\n",
            encoding="utf-8",
        )
    if not (brain_dir / "log.md").exists():
        (brain_dir / "log.md").write_text("# Log\n\n", encoding="utf-8")

    save_config(brain_dir, TAVILY_API_KEY=tavily_key, ANTHROPIC_API_KEY=anthropic_key)

    print()
    print(f"  {green('✓')} vault     {bold(str(brain_dir))}")
    if tavily_key:
        print(f"  {green('✓')} Tavily    {dim(tavily_key[:8] + '...')}")
    if anthropic_key:
        print(f"  {green('✓')} Anthropic {dim(anthropic_key[:8] + '...')}")
    print()
    print(f"  {gray('설정 파일:')}  {dim(str(_CONFIG_FILE))}")
    print()
    print(f"  {gray('Obsidian:')}  {dim('Open folder as vault → 위 경로 선택')}")
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

    _all_cmds = list(COMMANDS.keys()) + ["/log", "/model", "/search", "/quit", "/q"]

    def _completer(text: str, state: int):
        matches = [c for c in _all_cmds if c.startswith(text)]
        return matches[state] if state < len(matches) else None

    readline.set_completer(_completer)
    readline.parse_and_bind("tab: complete")

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

            if user_input.startswith("/model"):
                parts = user_input.split(maxsplit=1)
                cmd_model(parts[1] if len(parts) > 1 else None)
                continue

            if user_input in COMMANDS:
                COMMANDS[user_input]()
                continue

            if user_input == "/":
                cmd_help()
                continue

            if user_input.startswith("/"):
                matches = [c for c in _all_cmds if c.startswith(user_input)]
                if matches:
                    print(f"\n  {gray('  '.join(matches))}\n")
                else:
                    print(f"\n  {gray('알 수 없는 명령어')}\n")
                continue

            print()
            response = agent.chat(user_input, on_tool_call=_on_tool_call)
            print(f"\n  {response.replace(chr(10), chr(10) + '  ')}\n")

    except KeyboardInterrupt:
        pass
    finally:
        readline.write_history_file(HISTORY_FILE)
        print(f"\n  {gray('bye')}\n")
